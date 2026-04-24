"""HTTP client implementation for the Cerberus Compliance SDK.

Provides synchronous (:class:`CerberusClient`) and asynchronous
(:class:`AsyncCerberusClient`) entry points. Both share an identical
public surface:

* Construction by API key (defaulting to the ``CERBERUS_API_KEY`` env var).
* Configurable base URL, timeout, and :class:`~cerberus_compliance.retry.RetryConfig`.
* A ``_request`` method used by sub-resource modules. Handles JSON
  encoding/decoding, retries on transient failures, and maps non-2xx
  responses to the appropriate :class:`~cerberus_compliance.errors.CerberusAPIError`
  subclass.
* Context-manager and explicit ``close`` semantics that release the
  underlying ``httpx`` client cleanly.

The literal insertion marker appears exactly once in each ``__init__``
body and is used by the resource subagents as a marker for surgical
insertion of sub-resource attributes — do not move or rephrase it.
"""

from __future__ import annotations

import asyncio
import logging
import time
from types import TracebackType
from typing import Any, Final

import httpx

from cerberus_compliance.auth import ApiKeyAuth, resolve_api_key
from cerberus_compliance.errors import CerberusAPIError
from cerberus_compliance.resources.entities import (
    AsyncEntitiesResource,
    EntitiesResource,
)
from cerberus_compliance.resources.kyb import (
    AsyncKYBResource,
    KYBResource,
)
from cerberus_compliance.resources.material_events import (
    AsyncMaterialEventsResource,
    MaterialEventsResource,
)
from cerberus_compliance.resources.normativa import (
    AsyncNormativaResource,
    NormativaResource,
)
from cerberus_compliance.resources.persons import (
    AsyncPersonsResource,
    PersonsResource,
)
from cerberus_compliance.resources.registries import (
    AsyncRegistriesResource,
    RegistriesResource,
)
from cerberus_compliance.resources.regulations import (
    AsyncRegulationsResource,
    RegulationsResource,
)
from cerberus_compliance.resources.rpsf import (
    AsyncRPSFResource,
    RPSFResource,
)
from cerberus_compliance.resources.sanctions import (
    AsyncSanctionsResource,
    SanctionsResource,
)
from cerberus_compliance.retry import RetryConfig, backoff_seconds, should_retry

__all__ = [
    "DEFAULT_BASE_URL",
    "DEFAULT_TIMEOUT_SECONDS",
    "AsyncCerberusClient",
    "CerberusClient",
]

DEFAULT_BASE_URL: Final[str] = "https://compliance.cerberus.cl/v1"
DEFAULT_TIMEOUT_SECONDS: Final[float] = 30.0

# Treat transport-layer failures the same as a 503 for retry-decision purposes.
_NETWORK_ERROR_STATUS: Final[int] = 503


def _fix_insecure_redirect_location(response: httpx.Response) -> None:
    """Rewrite ``Location: http://…`` to ``https://…`` on redirect responses.

    The Cerberus Compliance API is fronted by Cloudflare + an ingress that
    terminates TLS before forwarding to FastAPI on plain HTTP. When FastAPI
    issues a ``307 Temporary Redirect`` for a missing trailing slash
    (``/v1/entities`` → ``/v1/entities/``), it emits the redirect with the
    scheme it sees locally (``http://``), even though the original request
    arrived over ``https://``.

    httpx treats ``https → http`` as a cross-origin security downgrade and
    strips the ``Authorization`` header before following the redirect,
    which then fails with ``401 Missing authentication``. We rewrite the
    ``Location`` header in-flight so httpx sees a same-origin
    ``https → https`` redirect and preserves the auth headers.

    No-op for any response that is not a redirect, or whose original
    request was not over HTTPS, or whose ``Location`` is relative or
    already ``https://``. The rewrite is a string prefix swap — we do not
    touch the path, query, or fragment.
    """
    if response.status_code not in {301, 302, 303, 307, 308}:
        return
    location = response.headers.get("location")
    if not location or not location.startswith("http://"):
        return
    if response.request.url.scheme != "https":
        return
    response.headers["location"] = "https://" + location[len("http://") :]


async def _fix_insecure_redirect_location_async(response: httpx.Response) -> None:
    """Async mirror of :func:`_fix_insecure_redirect_location`.

    httpx dispatches event hooks via ``await`` when the client is async, so
    the hook callable itself must be ``async``. The body just delegates to
    the sync helper — there's no I/O to await.
    """
    _fix_insecure_redirect_location(response)


def _retry_after_to_float(header_value: str | None) -> float | None:
    """Best-effort numeric parse of a ``Retry-After`` header.

    Only the numeric form is parsed here — the HTTP-date form is left to
    :class:`~cerberus_compliance.errors.RateLimitError` parsing inside
    ``CerberusAPIError.from_response``. This helper exists so the retry
    loop can pass a sleep hint to :func:`backoff_seconds`.
    """
    if header_value is None:
        return None
    stripped = header_value.strip()
    if not stripped:
        return None
    try:
        return float(stripped)
    except ValueError:
        return None


class CerberusClient:
    """Synchronous client for the Cerberus Compliance API.

    Use as a context manager or call :meth:`close` explicitly to release
    the underlying ``httpx.Client``.

    Example::

        with CerberusClient(api_key="ck_live_...") as client:
            entity = client._request("GET", "/entities/76123456-7")
    """

    api_key: str
    base_url: str
    timeout: float
    retry: RetryConfig
    entities: EntitiesResource
    kyb: KYBResource
    normativa: NormativaResource
    persons: PersonsResource
    rpsf: RPSFResource
    sanctions: SanctionsResource
    registries: RegistriesResource
    regulations: RegulationsResource
    material_events: MaterialEventsResource

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        retry: RetryConfig | None = None,
        logger: logging.Logger | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.api_key = resolve_api_key(api_key)
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout
        self.retry = retry or RetryConfig()
        self._logger = logger or logging.getLogger("cerberus_compliance")
        # ``follow_redirects=True``: the real API serves collection endpoints
        # with a trailing slash (e.g. ``GET /v1/entities/``). FastAPI responds
        # with a ``307 Temporary Redirect`` when the trailing slash is missing;
        # 307 preserves the HTTP method and body, so following it is safe for
        # GET/POST alike. This spares every resource module from hardcoding
        # per-endpoint slash conventions.
        #
        # The ``response`` event hook rewrites ``Location: http://…`` to
        # ``https://…`` on redirects — see
        # :func:`_fix_insecure_redirect_location` for the full rationale.
        self._http = http_client or httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            auth=ApiKeyAuth(self.api_key),
            follow_redirects=True,
            event_hooks={"response": [_fix_insecure_redirect_location]},
        )
        self.entities = EntitiesResource(self)
        self.kyb = KYBResource(self)
        self.persons = PersonsResource(self)
        self.material_events = MaterialEventsResource(self)
        self.sanctions = SanctionsResource(self)
        self.registries = RegistriesResource(self)
        self.regulations = RegulationsResource(self)
        self.rpsf = RPSFResource(self)
        self.normativa = NormativaResource(self)
        # Sub-resources are wired above by Instances B/C — keep this exact marker:
        # INSERT RESOURCES HERE

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute an HTTP request with retry + error mapping.

        Args:
            method: HTTP method (``GET``, ``POST``, ``DELETE``, ...).
            path: Path joined to ``base_url``. A leading ``/`` is fine.
            params: Optional query parameters.
            json: Optional JSON body (encoded as ``application/json``).

        Returns:
            The parsed JSON body on success. ``{}`` for ``204 No Content``.

        Raises:
            CerberusAPIError: On non-retryable HTTP errors or after retries
                are exhausted. Concrete subclass depends on the status code.
            httpx.TransportError: When all retry attempts on a transport
                failure are exhausted.
        """
        attempt = 0

        while True:
            attempt += 1
            self._logger.debug(
                "cerberus.request",
                extra={"method": method, "path": path, "attempt": attempt},
            )

            try:
                response = self._http.request(method, path, params=params, json=json)
            except httpx.TransportError:
                if should_retry(status=_NETWORK_ERROR_STATUS, attempt=attempt, cfg=self.retry):
                    delay = backoff_seconds(attempt, self.retry)
                    self._logger.warning(
                        "cerberus.retry",
                        extra={
                            "status": _NETWORK_ERROR_STATUS,
                            "attempt": attempt,
                            "delay_s": delay,
                            "reason": "transport_error",
                        },
                    )
                    time.sleep(delay)
                    continue
                raise

            status = response.status_code

            if 200 <= status < 300:
                if status == 204 or not response.content:
                    return {}
                parsed: Any = response.json()
                if not isinstance(parsed, dict):
                    # Defensive: if the API returns a list/scalar at the
                    # top level, wrap it under "data" so callers always
                    # get a dict.
                    return {"data": parsed}
                return parsed

            if should_retry(status=status, attempt=attempt, cfg=self.retry):
                retry_after_header = response.headers.get("retry-after")
                delay = backoff_seconds(
                    attempt,
                    self.retry,
                    retry_after=_retry_after_to_float(retry_after_header),
                )
                self._logger.warning(
                    "cerberus.retry",
                    extra={"status": status, "attempt": attempt, "delay_s": delay},
                )
                time.sleep(delay)
                continue

            # Non-retryable or budget exhausted -> raise.
            raise CerberusAPIError.from_response(
                status=status,
                body=response.content,
                request_id=response.headers.get("x-request-id"),
                retry_after=response.headers.get("retry-after"),
            )

    def close(self) -> None:
        """Release the underlying HTTP client."""
        self._http.close()

    def __enter__(self) -> CerberusClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()


class AsyncCerberusClient:
    """Asynchronous client for the Cerberus Compliance API.

    Mirror of :class:`CerberusClient` with ``async`` ``_request`` and
    ``close``. Use as an async context manager or call :meth:`close`.

    Example::

        async with AsyncCerberusClient(api_key="ck_live_...") as client:
            entity = await client._request("GET", "/entities/76123456-7")
    """

    api_key: str
    base_url: str
    timeout: float
    retry: RetryConfig
    entities: AsyncEntitiesResource
    kyb: AsyncKYBResource
    normativa: AsyncNormativaResource
    persons: AsyncPersonsResource
    rpsf: AsyncRPSFResource
    sanctions: AsyncSanctionsResource
    registries: AsyncRegistriesResource
    regulations: AsyncRegulationsResource
    material_events: AsyncMaterialEventsResource

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        retry: RetryConfig | None = None,
        logger: logging.Logger | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_key = resolve_api_key(api_key)
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout
        self.retry = retry or RetryConfig()
        self._logger = logger or logging.getLogger("cerberus_compliance")
        # See :class:`CerberusClient` for why ``follow_redirects=True`` and the
        # response hook. The async hook is a thin ``async`` wrapper because
        # httpx awaits event hooks on async clients.
        self._http = http_client or httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            auth=ApiKeyAuth(self.api_key),
            follow_redirects=True,
            event_hooks={"response": [_fix_insecure_redirect_location_async]},
        )
        self.entities = AsyncEntitiesResource(self)
        self.kyb = AsyncKYBResource(self)
        self.persons = AsyncPersonsResource(self)
        self.material_events = AsyncMaterialEventsResource(self)
        self.sanctions = AsyncSanctionsResource(self)
        self.registries = AsyncRegistriesResource(self)
        self.regulations = AsyncRegulationsResource(self)
        self.rpsf = AsyncRPSFResource(self)
        self.normativa = AsyncNormativaResource(self)
        # Sub-resources are wired above by Instances B/C — keep this exact marker:
        # INSERT RESOURCES HERE

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute an HTTP request with retry + error mapping (async).

        See :meth:`CerberusClient._request` for full semantics.
        """
        attempt = 0

        while True:
            attempt += 1
            self._logger.debug(
                "cerberus.request",
                extra={"method": method, "path": path, "attempt": attempt},
            )

            try:
                response = await self._http.request(method, path, params=params, json=json)
            except httpx.TransportError:
                if should_retry(status=_NETWORK_ERROR_STATUS, attempt=attempt, cfg=self.retry):
                    delay = backoff_seconds(attempt, self.retry)
                    self._logger.warning(
                        "cerberus.retry",
                        extra={
                            "status": _NETWORK_ERROR_STATUS,
                            "attempt": attempt,
                            "delay_s": delay,
                            "reason": "transport_error",
                        },
                    )
                    await asyncio.sleep(delay)
                    continue
                raise

            status = response.status_code

            if 200 <= status < 300:
                if status == 204 or not response.content:
                    return {}
                parsed: Any = response.json()
                if not isinstance(parsed, dict):
                    return {"data": parsed}
                return parsed

            if should_retry(status=status, attempt=attempt, cfg=self.retry):
                retry_after_header = response.headers.get("retry-after")
                delay = backoff_seconds(
                    attempt,
                    self.retry,
                    retry_after=_retry_after_to_float(retry_after_header),
                )
                self._logger.warning(
                    "cerberus.retry",
                    extra={"status": status, "attempt": attempt, "delay_s": delay},
                )
                await asyncio.sleep(delay)
                continue

            raise CerberusAPIError.from_response(
                status=status,
                body=response.content,
                request_id=response.headers.get("x-request-id"),
                retry_after=response.headers.get("retry-after"),
            )

    async def close(self) -> None:
        """Release the underlying async HTTP client."""
        await self._http.aclose()

    @classmethod
    def async_(cls, **kwargs: Any) -> AsyncCerberusClient:
        """Convenience constructor mirroring the documented ergonomics example."""
        return cls(**kwargs)

    async def __aenter__(self) -> AsyncCerberusClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()
