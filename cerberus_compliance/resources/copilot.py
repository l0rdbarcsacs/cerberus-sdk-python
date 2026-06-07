"""Typed accessor for the Cerberus Compliance ``/copilot`` resource.

The copilot answers natural-language questions over the CMF corpus under a
strict *cite-or-refuse* contract: every grounded answer carries at least one
:class:`Citation`; when the retrieval layer finds nothing relevant the copilot
refuses (``refused=True``, ``citations=[]``) rather than inventing an answer.

Two answering surfaces share the request/response contract:

* ``ask`` / ``ask_stream`` (``POST /copilot/ask*``, scope ``copilot:read``)
  ground over the whole indexed corpus.
* ``ask_public`` / ``ask_public_stream``
  (``POST /copilot/ask-public*``, scope ``regulations:read``) ground ONLY over
  public normativa, so no per-named private data reaches an anonymous-tier
  answer.

The non-streaming methods return the canonical answer ``dict`` (shape:
``answer`` / ``citations`` / ``refused`` / ``kind``). The streaming methods
yield :class:`CopilotStreamEvent` objects parsed from the Server-Sent-Events
wire; the terminal ``answer`` event carries the same canonical answer object.

``upload_document`` attaches a user PDF/TXT (multipart) whose extracted text the
copilot may ground on; the returned ``id`` is passed back via ``upload_ids`` on
a later :meth:`CopilotResource.ask`.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from cerberus_compliance.errors import CerberusAPIError
from cerberus_compliance.resources._base import (
    AsyncBaseResource,
    BaseResource,
    _encode_id,
)

__all__ = ["AsyncCopilotResource", "CopilotResource", "CopilotStreamEvent"]

_ASK_PATH = "/copilot/ask"
_ASK_PUBLIC_PATH = "/copilot/ask-public"
_ASK_STREAM_PATH = "/copilot/ask/stream"
_ASK_PUBLIC_STREAM_PATH = "/copilot/ask-public/stream"
_UPLOADS_PATH = "/copilot/uploads"


@dataclass(frozen=True)
class CopilotStreamEvent:
    """One decoded Server-Sent-Event frame from a streaming copilot call.

    Attributes:
        event: The SSE event type — one of ``status``, ``tool``, ``citations``,
            ``thinking``, ``delta``, ``rollback``, ``answer``, ``done`` or
            ``error``. The ``answer`` frame's :attr:`data` is the canonical
            answer object (same shape as :meth:`CopilotResource.ask`); ``done``
            closes the stream; ``error`` is terminal and carries
            ``status``/``slug``/``title``/``detail``.
        data: The JSON payload of the frame, already parsed to a ``dict``
            (``{}`` for an empty data line).
    """

    event: str
    data: dict[str, Any] = field(default_factory=dict)


class _SSEDecoder:
    """Incremental Server-Sent-Events line decoder.

    ``feed`` is called once per wire line (newline already stripped by
    ``httpx``'s ``iter_lines``); it returns ``(event, data)`` when a complete
    frame terminates on a blank line, else ``None``. Comment/keepalive lines
    (starting with ``:``) are ignored.
    """

    def __init__(self) -> None:
        self._event: str = "message"
        self._data: list[str] = []

    def feed(self, raw_line: str) -> tuple[str, str] | None:
        line = raw_line.rstrip("\r\n")
        if line == "":
            if not self._data:
                self._event = "message"
                return None
            frame = (self._event, "\n".join(self._data))
            self._event = "message"
            self._data = []
            return frame
        if line.startswith(":"):
            return None
        if line.startswith("event:"):
            self._event = line[len("event:") :].strip()
        elif line.startswith("data:"):
            self._data.append(line[len("data:") :].lstrip())
        return None


def _build_ask_body(
    question: str,
    top_k: int,
    history: Sequence[Mapping[str, str]] | None,
    upload_ids: Sequence[str] | None,
) -> dict[str, Any]:
    """Assemble the JSON body for an ``ask`` / ``ask-public`` request.

    Optional ``history`` and ``upload_ids`` are omitted when empty so the wire
    payload stays minimal and the server applies its own defaults.
    """
    body: dict[str, Any] = {"question": question, "top_k": top_k}
    if history:
        body["history"] = [{"role": turn["role"], "content": turn["content"]} for turn in history]
    if upload_ids:
        body["upload_ids"] = list(upload_ids)
    return body


def _event_from_frame(event_type: str, data_str: str) -> CopilotStreamEvent:
    """Build a :class:`CopilotStreamEvent` from a raw SSE frame."""
    parsed: Any = json.loads(data_str) if data_str else {}
    return CopilotStreamEvent(event=event_type, data=parsed if isinstance(parsed, dict) else {})


class CopilotResource(BaseResource):
    """Synchronous accessor for the ``/copilot`` endpoint family."""

    _path_prefix = "/copilot"

    def ask(
        self,
        question: str,
        *,
        top_k: int = 6,
        history: Sequence[Mapping[str, str]] | None = None,
        upload_ids: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        """Ask a grounded question over the whole indexed corpus.

        Issues ``POST /copilot/ask`` (scope ``copilot:read``). Returns the
        canonical answer ``dict`` with ``answer``, ``citations``, ``refused``
        and ``kind`` (``grounded`` | ``refusal`` | ``conversational``). A
        refusal is a normal ``200`` response, not an error.

        Args:
            question: The natural-language question (3-2000 chars).
            top_k: Number of grounding chunks (1-12; default 6).
            history: Prior conversation turns (``{"role", "content"}``;
                ``role`` is ``"user"`` or ``"assistant"``). Resolves references
                in retrieval; never itself a citable source.
            upload_ids: Up to 3 document ids from :meth:`upload_document`.
        """
        body = _build_ask_body(question, top_k, history, upload_ids)
        return self._client._request("POST", _ASK_PATH, json=body)

    def ask_public(
        self,
        question: str,
        *,
        top_k: int = 6,
        history: Sequence[Mapping[str, str]] | None = None,
        upload_ids: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        """Ask a grounded question over public normativa only.

        Issues ``POST /copilot/ask-public`` (scope ``regulations:read``).
        Retrieval is restricted to public normativa, so no per-named private
        data reaches the answer. Same response shape as :meth:`ask`.
        """
        body = _build_ask_body(question, top_k, history, upload_ids)
        return self._client._request("POST", _ASK_PUBLIC_PATH, json=body)

    def ask_stream(
        self,
        question: str,
        *,
        top_k: int = 6,
        history: Sequence[Mapping[str, str]] | None = None,
        upload_ids: Sequence[str] | None = None,
    ) -> Iterator[CopilotStreamEvent]:
        """Stream a grounded answer over the whole corpus as SSE events.

        Issues ``POST /copilot/ask/stream`` and yields
        :class:`CopilotStreamEvent` frames as they arrive (``status`` / ``tool``
        / ``citations`` / ``thinking`` / ``delta`` / ``rollback`` / ``answer`` /
        ``done`` / ``error``). The terminal ``answer`` frame carries the same
        canonical answer object as :meth:`ask`. Errors *before* the stream opens
        raise :class:`~cerberus_compliance.errors.CerberusAPIError`; errors
        *mid-stream* arrive as a terminal ``error`` event.
        """
        body = _build_ask_body(question, top_k, history, upload_ids)
        return self._stream(_ASK_STREAM_PATH, body)

    def ask_public_stream(
        self,
        question: str,
        *,
        top_k: int = 6,
        history: Sequence[Mapping[str, str]] | None = None,
        upload_ids: Sequence[str] | None = None,
    ) -> Iterator[CopilotStreamEvent]:
        """Stream a public-normativa answer as SSE events (see :meth:`ask_stream`)."""
        body = _build_ask_body(question, top_k, history, upload_ids)
        return self._stream(_ASK_PUBLIC_STREAM_PATH, body)

    def _stream(self, path: str, body: dict[str, Any]) -> Iterator[CopilotStreamEvent]:
        decoder = _SSEDecoder()
        with self._client._http.stream("POST", path, json=body) as response:
            if response.status_code >= 400:
                response.read()
                raise CerberusAPIError.from_response(
                    status=response.status_code,
                    body=response.content,
                    request_id=response.headers.get("x-request-id"),
                    retry_after=response.headers.get("retry-after"),
                )
            for raw_line in response.iter_lines():
                frame = decoder.feed(raw_line)
                if frame is not None:
                    yield _event_from_frame(frame[0], frame[1])

    def upload_document(
        self,
        *,
        content: bytes,
        filename: str,
        content_type: str = "application/pdf",
        consent: bool = True,
    ) -> dict[str, Any]:
        """Upload a PDF/TXT document for grounding (multipart).

        Issues ``POST /copilot/uploads`` (scope ``copilot:read``). The document
        text is extracted server-side; the returned ``id`` is passed back via
        ``upload_ids`` on a later :meth:`ask`. ``consent`` MUST be ``True`` (the
        server rejects anything but the literal ``"true"``). Accepts
        ``application/pdf`` or ``text/plain``, up to 15 MB.

        Args:
            content: Raw file bytes.
            filename: Original file name.
            content_type: MIME type — ``application/pdf`` or ``text/plain``.
            consent: Explicit retention consent; sent as ``"true"``/``"false"``.

        Returns:
            ``{"id", "status", "filename", "token_count", "preview",
            "expires_at"}``.
        """
        files = {"file": (filename, content, content_type)}
        data = {"consent": "true" if consent else "false"}
        response = self._client._http.post(_UPLOADS_PATH, files=files, data=data)
        if response.status_code >= 400:
            raise CerberusAPIError.from_response(
                status=response.status_code,
                body=response.content,
                request_id=response.headers.get("x-request-id"),
                retry_after=response.headers.get("retry-after"),
            )
        parsed: Any = response.json()
        return parsed if isinstance(parsed, dict) else {"data": parsed}

    def get_document(self, document_id: str) -> dict[str, Any]:
        """Fetch the status of one of your own uploads (``GET /copilot/uploads/{id}``).

        Returns ``404`` (as :class:`~cerberus_compliance.errors.NotFoundError`)
        when the upload expired, belongs to another tenant, or never existed.
        """
        return self._client._request("GET", f"{_UPLOADS_PATH}/{_encode_id(document_id)}")


class AsyncCopilotResource(AsyncBaseResource):
    """Asynchronous accessor for the ``/copilot`` endpoint family."""

    _path_prefix = "/copilot"

    async def ask(
        self,
        question: str,
        *,
        top_k: int = 6,
        history: Sequence[Mapping[str, str]] | None = None,
        upload_ids: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        """Async variant of :meth:`CopilotResource.ask`."""
        body = _build_ask_body(question, top_k, history, upload_ids)
        return await self._client._request("POST", _ASK_PATH, json=body)

    async def ask_public(
        self,
        question: str,
        *,
        top_k: int = 6,
        history: Sequence[Mapping[str, str]] | None = None,
        upload_ids: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        """Async variant of :meth:`CopilotResource.ask_public`."""
        body = _build_ask_body(question, top_k, history, upload_ids)
        return await self._client._request("POST", _ASK_PUBLIC_PATH, json=body)

    def ask_stream(
        self,
        question: str,
        *,
        top_k: int = 6,
        history: Sequence[Mapping[str, str]] | None = None,
        upload_ids: Sequence[str] | None = None,
    ) -> AsyncIterator[CopilotStreamEvent]:
        """Async variant of :meth:`CopilotResource.ask_stream`."""
        body = _build_ask_body(question, top_k, history, upload_ids)
        return self._stream(_ASK_STREAM_PATH, body)

    def ask_public_stream(
        self,
        question: str,
        *,
        top_k: int = 6,
        history: Sequence[Mapping[str, str]] | None = None,
        upload_ids: Sequence[str] | None = None,
    ) -> AsyncIterator[CopilotStreamEvent]:
        """Async variant of :meth:`CopilotResource.ask_public_stream`."""
        body = _build_ask_body(question, top_k, history, upload_ids)
        return self._stream(_ASK_PUBLIC_STREAM_PATH, body)

    async def _stream(self, path: str, body: dict[str, Any]) -> AsyncIterator[CopilotStreamEvent]:
        decoder = _SSEDecoder()
        async with self._client._http.stream("POST", path, json=body) as response:
            if response.status_code >= 400:
                await response.aread()
                raise CerberusAPIError.from_response(
                    status=response.status_code,
                    body=response.content,
                    request_id=response.headers.get("x-request-id"),
                    retry_after=response.headers.get("retry-after"),
                )
            async for raw_line in response.aiter_lines():
                frame = decoder.feed(raw_line)
                if frame is not None:
                    yield _event_from_frame(frame[0], frame[1])

    async def upload_document(
        self,
        *,
        content: bytes,
        filename: str,
        content_type: str = "application/pdf",
        consent: bool = True,
    ) -> dict[str, Any]:
        """Async variant of :meth:`CopilotResource.upload_document`."""
        files = {"file": (filename, content, content_type)}
        data = {"consent": "true" if consent else "false"}
        response = await self._client._http.post(_UPLOADS_PATH, files=files, data=data)
        if response.status_code >= 400:
            raise CerberusAPIError.from_response(
                status=response.status_code,
                body=response.content,
                request_id=response.headers.get("x-request-id"),
                retry_after=response.headers.get("retry-after"),
            )
        parsed: Any = response.json()
        return parsed if isinstance(parsed, dict) else {"data": parsed}

    async def get_document(self, document_id: str) -> dict[str, Any]:
        """Async variant of :meth:`CopilotResource.get_document`."""
        return await self._client._request("GET", f"{_UPLOADS_PATH}/{_encode_id(document_id)}")
