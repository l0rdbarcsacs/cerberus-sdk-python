"""Tests for ``cerberus_compliance.resources.copilot``.

Covers the non-streaming ask/ask-public JSON contract, the SSE streaming
surfaces (parsed into :class:`CopilotStreamEvent`), the multipart document
upload, the upload-status lookup, error mapping, and the internal SSE decoder.
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.errors import NotFoundError, ServerError, ValidationError
from cerberus_compliance.resources.copilot import (
    AsyncCopilotResource,
    CopilotResource,
    CopilotStreamEvent,
    _build_ask_body,
    _event_from_frame,
    _SSEDecoder,
)

_GROUNDED_ANSWER = {
    "answer": "La NCG 461 exige un reporte de sostenibilidad anual.",
    "citations": [
        {
            "source_table": "regulations",
            "source_row_id": "r-1",
            "score": 0.91,
            "snippet": "reporte de sostenibilidad",
            "title": "NCG 461",
        }
    ],
    "refused": False,
    "kind": "grounded",
}

_REFUSAL_ANSWER = {
    "answer": "No encontré fundamento.",
    "citations": [],
    "refused": True,
    "kind": "refusal",
}

_SSE_GROUNDED = (
    ": keepalive\n\n"
    "event: status\n"
    'data: {"stage": "retrieving"}\n\n'
    "event: citations\n"
    'data: {"citations": [{"source_table": "regulations", "source_row_id": "r-1",'
    ' "score": 0.91, "snippet": "x", "title": "NCG 461"}]}\n\n'
    "event: delta\n"
    'data: {"text": "La "}\n\n'
    "event: delta\n"
    'data: {"text": "NCG 461..."}\n\n'
    "event: answer\n"
    f"data: {json.dumps(_GROUNDED_ANSWER)}\n\n"
    "event: done\n"
    "data: {}\n\n"
)


# --------------------------------------------------------------------------- #
# Pure helpers                                                                 #
# --------------------------------------------------------------------------- #


class TestBuildAskBody:
    def test_minimal_body(self) -> None:
        assert _build_ask_body("hola mundo", 6, None, None) == {
            "question": "hola mundo",
            "top_k": 6,
        }

    def test_history_and_uploads_included(self) -> None:
        body = _build_ask_body(
            "q?",
            4,
            [{"role": "user", "content": "previo"}],
            ["u-1", "u-2"],
        )
        assert body == {
            "question": "q?",
            "top_k": 4,
            "history": [{"role": "user", "content": "previo"}],
            "upload_ids": ["u-1", "u-2"],
        }

    def test_empty_history_and_uploads_omitted(self) -> None:
        body = _build_ask_body("q?", 6, [], [])
        assert body == {"question": "q?", "top_k": 6}


class TestEventFromFrame:
    def test_parses_dict(self) -> None:
        ev = _event_from_frame("delta", '{"text": "hi"}')
        assert ev == CopilotStreamEvent(event="delta", data={"text": "hi"})

    def test_empty_data_is_empty_dict(self) -> None:
        assert _event_from_frame("done", "") == CopilotStreamEvent(event="done", data={})

    def test_non_dict_payload_collapses_to_empty(self) -> None:
        assert _event_from_frame("x", "[1, 2, 3]").data == {}


class TestSSEDecoder:
    def test_full_frame(self) -> None:
        d = _SSEDecoder()
        assert d.feed("event: status") is None
        assert d.feed('data: {"stage": "x"}') is None
        assert d.feed("") == ("status", '{"stage": "x"}')

    def test_comment_line_ignored(self) -> None:
        d = _SSEDecoder()
        assert d.feed(": keepalive") is None

    def test_blank_without_data_yields_nothing(self) -> None:
        d = _SSEDecoder()
        assert d.feed("") is None

    def test_default_event_is_message(self) -> None:
        d = _SSEDecoder()
        d.feed("data: payload")
        assert d.feed("") == ("message", "payload")

    def test_multiline_data_joined(self) -> None:
        d = _SSEDecoder()
        d.feed("data: line1")
        d.feed("data: line2")
        assert d.feed("") == ("message", "line1\nline2")


# --------------------------------------------------------------------------- #
# Sync                                                                         #
# --------------------------------------------------------------------------- #


class TestCopilotSync:
    def test_ask(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        route = respx_mock.post("/copilot/ask").mock(
            return_value=httpx.Response(200, json=_GROUNDED_ANSWER)
        )
        res = CopilotResource(sync_client)
        out = res.ask(
            "¿Qué exige la NCG 461?", top_k=4, history=[{"role": "user", "content": "hola"}]
        )
        assert out["kind"] == "grounded"
        assert out["citations"][0]["source_table"] == "regulations"
        body = json.loads(route.calls.last.request.content)
        assert body == {
            "question": "¿Qué exige la NCG 461?",
            "top_k": 4,
            "history": [{"role": "user", "content": "hola"}],
        }

    def test_ask_public(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        route = respx_mock.post("/copilot/ask-public").mock(
            return_value=httpx.Response(200, json=_REFUSAL_ANSWER)
        )
        res = CopilotResource(sync_client)
        out = res.ask_public("pregunta pública")
        assert out["refused"] is True
        assert route.called

    def test_ask_maps_errors(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.post("/copilot/ask").mock(
            return_value=httpx.Response(422, json={"title": "Unprocessable", "status": 422})
        )
        res = CopilotResource(sync_client)
        with pytest.raises(ValidationError):
            res.ask("xx")

    def test_ask_stream(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        respx_mock.post("/copilot/ask/stream").mock(
            return_value=httpx.Response(
                200, text=_SSE_GROUNDED, headers={"content-type": "text/event-stream"}
            )
        )
        res = CopilotResource(sync_client)
        events = list(res.ask_stream("¿NCG 461?"))
        kinds = [e.event for e in events]
        assert kinds == ["status", "citations", "delta", "delta", "answer", "done"]
        answer_ev = next(e for e in events if e.event == "answer")
        assert answer_ev.data["kind"] == "grounded"
        deltas = "".join(e.data["text"] for e in events if e.event == "delta")
        assert deltas == "La NCG 461..."

    def test_ask_public_stream(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.post("/copilot/ask-public/stream").mock(
            return_value=httpx.Response(
                200, text=_SSE_GROUNDED, headers={"content-type": "text/event-stream"}
            )
        )
        res = CopilotResource(sync_client)
        events = list(res.ask_public_stream("pública"))
        assert events[-1].event == "done"

    def test_stream_http_error_raises(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.post("/copilot/ask/stream").mock(
            return_value=httpx.Response(503, json={"title": "Unavailable", "status": 503})
        )
        res = CopilotResource(sync_client)
        with pytest.raises(ServerError):
            list(res.ask_stream("x"))

    def test_upload_document(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        payload = {
            "id": "doc-1",
            "status": "ready",
            "filename": "informe.pdf",
            "token_count": 1200,
            "preview": "Informe...",
            "expires_at": "2026-07-07T00:00:00Z",
        }
        route = respx_mock.post("/copilot/uploads").mock(
            return_value=httpx.Response(201, json=payload)
        )
        res = CopilotResource(sync_client)
        out = res.upload_document(content=b"%PDF-1.4 ...", filename="informe.pdf")
        assert out["id"] == "doc-1"
        assert route.called
        sent = route.calls.last.request.content
        assert b"informe.pdf" in sent
        assert b"true" in sent

    def test_upload_document_error(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.post("/copilot/uploads").mock(
            return_value=httpx.Response(415, json={"title": "Unsupported", "status": 415})
        )
        res = CopilotResource(sync_client)
        with pytest.raises(Exception):  # noqa: B017 - any CerberusAPIError subclass
            res.upload_document(
                content=b"x", filename="x.bin", content_type="application/octet-stream"
            )

    def test_get_document(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        respx_mock.get("/copilot/uploads/doc-1").mock(
            return_value=httpx.Response(200, json={"id": "doc-1", "status": "ready"})
        )
        res = CopilotResource(sync_client)
        assert res.get_document("doc-1")["status"] == "ready"

    def test_get_document_404(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/copilot/uploads/missing").mock(
            return_value=httpx.Response(404, json={"title": "Not found", "status": 404})
        )
        res = CopilotResource(sync_client)
        with pytest.raises(NotFoundError):
            res.get_document("missing")


# --------------------------------------------------------------------------- #
# Async                                                                        #
# --------------------------------------------------------------------------- #


class TestCopilotAsync:
    async def test_ask(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.post("/copilot/ask").mock(
            return_value=httpx.Response(200, json=_GROUNDED_ANSWER)
        )
        res = AsyncCopilotResource(async_client)
        out = await res.ask("¿NCG 461?", upload_ids=["u-1"])
        assert out["kind"] == "grounded"

    async def test_ask_public(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.post("/copilot/ask-public").mock(
            return_value=httpx.Response(200, json=_REFUSAL_ANSWER)
        )
        res = AsyncCopilotResource(async_client)
        out = await res.ask_public("q")
        assert out["refused"] is True

    async def test_ask_stream(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.post("/copilot/ask/stream").mock(
            return_value=httpx.Response(
                200, text=_SSE_GROUNDED, headers={"content-type": "text/event-stream"}
            )
        )
        res = AsyncCopilotResource(async_client)
        events = [ev async for ev in res.ask_stream("¿NCG 461?")]
        assert [e.event for e in events] == [
            "status",
            "citations",
            "delta",
            "delta",
            "answer",
            "done",
        ]

    async def test_ask_public_stream(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.post("/copilot/ask-public/stream").mock(
            return_value=httpx.Response(
                200, text=_SSE_GROUNDED, headers={"content-type": "text/event-stream"}
            )
        )
        res = AsyncCopilotResource(async_client)
        events = [ev async for ev in res.ask_public_stream("q")]
        assert events[-1].event == "done"

    async def test_stream_http_error_raises(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.post("/copilot/ask/stream").mock(
            return_value=httpx.Response(503, json={"title": "Unavailable", "status": 503})
        )
        res = AsyncCopilotResource(async_client)
        with pytest.raises(ServerError):
            [ev async for ev in res.ask_stream("x")]

    async def test_upload_document(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.post("/copilot/uploads").mock(
            return_value=httpx.Response(201, json={"id": "d", "status": "ready"})
        )
        res = AsyncCopilotResource(async_client)
        out = await res.upload_document(
            content=b"hola", filename="n.txt", content_type="text/plain"
        )
        assert out["id"] == "d"

    async def test_upload_document_error(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.post("/copilot/uploads").mock(
            return_value=httpx.Response(413, json={"title": "Too large", "status": 413})
        )
        res = AsyncCopilotResource(async_client)
        with pytest.raises(Exception):  # noqa: B017
            await res.upload_document(content=b"x" * 10, filename="big.pdf")

    async def test_get_document(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/copilot/uploads/d").mock(
            return_value=httpx.Response(200, json={"id": "d", "status": "processing"})
        )
        res = AsyncCopilotResource(async_client)
        out = await res.get_document("d")
        assert out["status"] == "processing"
