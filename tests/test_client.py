"""TDD tests for `cerberus_compliance.client`.

Covers:
- Sync + async client construction and context-manager semantics.
- `_request` happy-paths (GET / POST / 204).
- Auth header is plumbed through.
- Retry on 5xx and 429 (with Retry-After).
- Final-failure mapping to the right :class:`CerberusAPIError` subclass.
- ``request_id`` propagation from ``X-Request-Id``.
- Network errors (httpx.TransportError) retried then re-raised.
- The ``# INSERT RESOURCES HERE`` marker appears exactly twice.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
import pytest
import respx

from cerberus_compliance.client import (
    DEFAULT_BASE_URL,
    DEFAULT_TIMEOUT_SECONDS,
    AsyncCerberusClient,
    CerberusClient,
)
from cerberus_compliance.errors import (
    AuthError,
    CerberusAPIError,
    NotFoundError,
    QuotaError,
    RateLimitError,
    ServerError,
    ValidationError,
)

if TYPE_CHECKING:
    from collections.abc import Callable


# ---------------------------------------------------------------------------
# Construction / defaults
# ---------------------------------------------------------------------------


class TestSyncClientConstruction:
    def test_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CERBERUS_API_KEY", "ck_env")
        c = CerberusClient()
        try:
            assert c.api_key == "ck_env"
            assert c.base_url == DEFAULT_BASE_URL
            assert c.timeout == DEFAULT_TIMEOUT_SECONDS
        finally:
            c.close()

    def test_explicit_overrides(self) -> None:
        c = CerberusClient(api_key="ck_x", base_url="https://example.test/v1/", timeout=5.0)
        try:
            assert c.api_key == "ck_x"
            # trailing slash stripped
            assert c.base_url == "https://example.test/v1"
            assert c.timeout == 5.0
        finally:
            c.close()

    def test_context_manager_closes_http(self) -> None:
        underlying = httpx.Client(base_url="https://mock.test/v1")
        with CerberusClient(api_key="ck_cm", http_client=underlying) as c:
            assert c is not None
        assert underlying.is_closed is True


class TestAsyncClientConstruction:
    async def test_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CERBERUS_API_KEY", "ck_env_async")
        c = AsyncCerberusClient()
        try:
            assert c.api_key == "ck_env_async"
            assert c.base_url == DEFAULT_BASE_URL
        finally:
            await c.close()

    async def test_async_alt_constructor(self) -> None:
        c = AsyncCerberusClient.async_(api_key="ck_y")
        try:
            assert isinstance(c, AsyncCerberusClient)
            assert c.api_key == "ck_y"
        finally:
            await c.close()

    async def test_context_manager_closes_http(self) -> None:
        underlying = httpx.AsyncClient(base_url="https://mock.test/v1")
        async with AsyncCerberusClient(api_key="ck_cm", http_client=underlying) as c:
            assert c is not None
        assert underlying.is_closed is True


# ---------------------------------------------------------------------------
# Sync _request happy paths
# ---------------------------------------------------------------------------


class TestSyncRequestHappyPath:
    def test_get_returns_parsed_dict(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/things/abc").mock(
            return_value=httpx.Response(200, json={"id": "abc", "name": "n"})
        )
        result = sync_client._request("GET", "/things/abc")
        assert result == {"id": "abc", "name": "n"}

    def test_post_sends_json_body(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.post("/things").mock(
            return_value=httpx.Response(201, json={"id": "new"})
        )
        result = sync_client._request("POST", "/things", json={"name": "n"})
        assert result == {"id": "new"}
        assert route.called
        sent = json.loads(route.calls.last.request.content.decode("utf-8"))
        assert sent == {"name": "n"}

    def test_get_forwards_query_params(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/things", params={"limit": "10"}).mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        sync_client._request("GET", "/things", params={"limit": 10})
        assert route.called

    def test_204_returns_empty_dict(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.delete("/things/abc").mock(return_value=httpx.Response(204))
        result = sync_client._request("DELETE", "/things/abc")
        assert result == {}

    def test_authorization_header_present(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter, api_key: str
    ) -> None:
        route = respx_mock.get("/ping").mock(return_value=httpx.Response(200, json={"ok": True}))
        sync_client._request("GET", "/ping")
        sent_auth = route.calls.last.request.headers.get("authorization")
        assert sent_auth == f"Bearer {api_key}"


# ---------------------------------------------------------------------------
# Sync _request error mapping
# ---------------------------------------------------------------------------


class TestSyncRequestErrorMapping:
    def test_401_raises_auth_error(
        self,
        sync_client: CerberusClient,
        respx_mock: respx.MockRouter,
        problem_json: Callable[..., dict[str, Any]],
    ) -> None:
        respx_mock.get("/p").mock(
            return_value=httpx.Response(401, json=problem_json(status=401, title="Unauthorized"))
        )
        with pytest.raises(AuthError) as exc:
            sync_client._request("GET", "/p")
        assert exc.value.status == 401

    def test_403_raises_auth_error(
        self,
        sync_client: CerberusClient,
        respx_mock: respx.MockRouter,
        problem_json: Callable[..., dict[str, Any]],
    ) -> None:
        respx_mock.get("/p").mock(
            return_value=httpx.Response(403, json=problem_json(status=403, title="Forbidden"))
        )
        with pytest.raises(AuthError):
            sync_client._request("GET", "/p")

    def test_402_raises_quota_error(
        self,
        sync_client: CerberusClient,
        respx_mock: respx.MockRouter,
        problem_json: Callable[..., dict[str, Any]],
    ) -> None:
        respx_mock.get("/p").mock(
            return_value=httpx.Response(402, json=problem_json(status=402, title="Payment"))
        )
        with pytest.raises(QuotaError):
            sync_client._request("GET", "/p")

    def test_422_raises_validation_error(
        self,
        sync_client: CerberusClient,
        respx_mock: respx.MockRouter,
        problem_json: Callable[..., dict[str, Any]],
    ) -> None:
        respx_mock.post("/p").mock(
            return_value=httpx.Response(
                422,
                json=problem_json(status=422, title="Unprocessable", errors=[{"field": "rut"}]),
            )
        )
        with pytest.raises(ValidationError):
            sync_client._request("POST", "/p", json={})

    def test_request_id_header_propagated(
        self,
        sync_client: CerberusClient,
        respx_mock: respx.MockRouter,
        problem_json: Callable[..., dict[str, Any]],
    ) -> None:
        respx_mock.get("/p").mock(
            return_value=httpx.Response(
                401,
                json=problem_json(status=401, title="Unauthorized"),
                headers={"X-Request-Id": "req-123"},
            )
        )
        with pytest.raises(AuthError) as exc:
            sync_client._request("GET", "/p")
        assert exc.value.request_id == "req-123"

    def test_404_raises_not_found_error(
        self,
        sync_client: CerberusClient,
        respx_mock: respx.MockRouter,
        problem_json: Callable[..., dict[str, Any]],
    ) -> None:
        respx_mock.get("/p").mock(
            return_value=httpx.Response(404, json=problem_json(status=404, title="Not Found"))
        )
        with pytest.raises(NotFoundError) as exc:
            sync_client._request("GET", "/p")
        # NotFoundError subclasses CerberusAPIError so broad handlers still catch it.
        assert isinstance(exc.value, CerberusAPIError)
        assert exc.value.status == 404


# ---------------------------------------------------------------------------
# Sync retries
# ---------------------------------------------------------------------------


class TestSyncRetries:
    def test_retries_503_then_succeeds(
        self,
        sync_client: CerberusClient,
        respx_mock: respx.MockRouter,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # No real sleeping in tests.
        monkeypatch.setattr("time.sleep", lambda _seconds: None)
        route = respx_mock.get("/r").mock(
            side_effect=[
                httpx.Response(503),
                httpx.Response(503),
                httpx.Response(200, json={"ok": True}),
            ]
        )
        result = sync_client._request("GET", "/r")
        assert result == {"ok": True}
        assert route.call_count == 3

    def test_retries_exhausted_raises_server_error(
        self,
        sync_client: CerberusClient,
        respx_mock: respx.MockRouter,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("time.sleep", lambda _s: None)
        respx_mock.get("/r").mock(
            side_effect=[httpx.Response(500), httpx.Response(500), httpx.Response(500)]
        )
        with pytest.raises(ServerError) as exc:
            sync_client._request("GET", "/r")
        assert exc.value.status == 500

    def test_429_retry_after_passed_to_backoff(
        self,
        sync_client: CerberusClient,
        respx_mock: respx.MockRouter,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        sleeps: list[float] = []
        captured_retry_afters: list[float | None] = []

        def fake_sleep(seconds: float) -> None:
            sleeps.append(seconds)

        import cerberus_compliance.client as client_mod

        original_backoff = client_mod.backoff_seconds

        def fake_backoff(attempt: int, cfg: Any, *, retry_after: float | None = None) -> float:
            captured_retry_afters.append(retry_after)
            return original_backoff(attempt, cfg, retry_after=retry_after)

        monkeypatch.setattr("time.sleep", fake_sleep)
        monkeypatch.setattr(client_mod, "backoff_seconds", fake_backoff)

        respx_mock.get("/r").mock(
            side_effect=[
                httpx.Response(429, headers={"Retry-After": "0"}),
                httpx.Response(200, json={"ok": True}),
            ]
        )
        result = sync_client._request("GET", "/r")
        assert result == {"ok": True}
        # One retry => one backoff call, with retry_after parsed as 0.0 float
        assert captured_retry_afters == [0.0]
        # Real time.sleep was patched, so 0.0 (or whatever backoff returned) was passed
        assert len(sleeps) == 1

    def test_429_exhausted_raises_rate_limit_error(
        self,
        sync_client: CerberusClient,
        respx_mock: respx.MockRouter,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("time.sleep", lambda _s: None)
        respx_mock.get("/r").mock(
            side_effect=[
                httpx.Response(429, headers={"Retry-After": "0"}),
                httpx.Response(429, headers={"Retry-After": "0"}),
                httpx.Response(429, headers={"Retry-After": "0"}),
            ]
        )
        with pytest.raises(RateLimitError) as exc:
            sync_client._request("GET", "/r")
        assert exc.value.retry_after == 0.0

    def test_logs_retry_warning(
        self,
        sync_client: CerberusClient,
        respx_mock: respx.MockRouter,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        monkeypatch.setattr("time.sleep", lambda _s: None)
        respx_mock.get("/r").mock(
            side_effect=[httpx.Response(503), httpx.Response(200, json={"ok": True})]
        )
        with caplog.at_level(logging.WARNING, logger="cerberus_compliance"):
            sync_client._request("GET", "/r")
        assert any("cerberus.retry" in rec.message for rec in caplog.records)


# ---------------------------------------------------------------------------
# Sync network-error retries
# ---------------------------------------------------------------------------


class TestSyncNetworkErrors:
    def test_network_error_retried_then_succeeds(
        self,
        sync_client: CerberusClient,
        respx_mock: respx.MockRouter,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("time.sleep", lambda _s: None)
        respx_mock.get("/r").mock(
            side_effect=[
                httpx.ConnectError("boom"),
                httpx.ConnectError("boom"),
                httpx.Response(200, json={"ok": True}),
            ]
        )
        result = sync_client._request("GET", "/r")
        assert result == {"ok": True}

    def test_network_error_exhausted_reraises(
        self,
        sync_client: CerberusClient,
        respx_mock: respx.MockRouter,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("time.sleep", lambda _s: None)
        respx_mock.get("/r").mock(
            side_effect=[
                httpx.ConnectError("boom1"),
                httpx.ConnectError("boom2"),
                httpx.ConnectError("boom3"),
            ]
        )
        with pytest.raises(httpx.TransportError):
            sync_client._request("GET", "/r")


# ---------------------------------------------------------------------------
# Async _request — mirror of sync battery (subset of behaviors that matter)
# ---------------------------------------------------------------------------


class TestAsyncRequest:
    async def test_get_returns_parsed_dict(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/things/abc").mock(return_value=httpx.Response(200, json={"id": "abc"}))
        result = await async_client._request("GET", "/things/abc")
        assert result == {"id": "abc"}

    async def test_post_sends_json(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.post("/things").mock(return_value=httpx.Response(201, json={"id": "x"}))
        await async_client._request("POST", "/things", json={"name": "n"})
        sent = json.loads(route.calls.last.request.content.decode("utf-8"))
        assert sent == {"name": "n"}

    async def test_204_returns_empty(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.delete("/x").mock(return_value=httpx.Response(204))
        assert await async_client._request("DELETE", "/x") == {}

    async def test_auth_header(
        self,
        async_client: AsyncCerberusClient,
        respx_mock: respx.MockRouter,
        api_key: str,
    ) -> None:
        route = respx_mock.get("/p").mock(return_value=httpx.Response(200, json={}))
        await async_client._request("GET", "/p")
        assert route.calls.last.request.headers["authorization"] == f"Bearer {api_key}"

    async def test_401_raises_auth_error(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/p").mock(return_value=httpx.Response(401, json={"title": "u"}))
        with pytest.raises(AuthError):
            await async_client._request("GET", "/p")

    async def test_retry_503_then_success(
        self,
        async_client: AsyncCerberusClient,
        respx_mock: respx.MockRouter,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        async def fake_sleep(_seconds: float) -> None:
            return None

        monkeypatch.setattr(asyncio, "sleep", fake_sleep)
        respx_mock.get("/r").mock(
            side_effect=[
                httpx.Response(503),
                httpx.Response(200, json={"ok": True}),
            ]
        )
        assert await async_client._request("GET", "/r") == {"ok": True}

    async def test_retry_exhausted_server_error(
        self,
        async_client: AsyncCerberusClient,
        respx_mock: respx.MockRouter,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        async def fake_sleep(_seconds: float) -> None:
            return None

        monkeypatch.setattr(asyncio, "sleep", fake_sleep)
        respx_mock.get("/r").mock(
            side_effect=[httpx.Response(500), httpx.Response(500), httpx.Response(500)]
        )
        with pytest.raises(ServerError):
            await async_client._request("GET", "/r")

    async def test_request_id_propagated(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/p").mock(
            return_value=httpx.Response(401, json={"title": "u"}, headers={"X-Request-Id": "rA"})
        )
        with pytest.raises(AuthError) as exc:
            await async_client._request("GET", "/p")
        assert exc.value.request_id == "rA"

    async def test_network_error_retried(
        self,
        async_client: AsyncCerberusClient,
        respx_mock: respx.MockRouter,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        async def fake_sleep(_seconds: float) -> None:
            return None

        monkeypatch.setattr(asyncio, "sleep", fake_sleep)
        respx_mock.get("/r").mock(
            side_effect=[
                httpx.ConnectError("x"),
                httpx.Response(200, json={"ok": True}),
            ]
        )
        assert await async_client._request("GET", "/r") == {"ok": True}

    async def test_network_error_exhausted_reraises(
        self,
        async_client: AsyncCerberusClient,
        respx_mock: respx.MockRouter,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        async def fake_sleep(_seconds: float) -> None:
            return None

        monkeypatch.setattr(asyncio, "sleep", fake_sleep)
        respx_mock.get("/r").mock(
            side_effect=[
                httpx.ConnectError("x"),
                httpx.ConnectError("x"),
                httpx.ConnectError("x"),
            ]
        )
        with pytest.raises(httpx.TransportError):
            await async_client._request("GET", "/r")


# ---------------------------------------------------------------------------
# Internal helpers + branch coverage
# ---------------------------------------------------------------------------


class TestRetryAfterHelper:
    """Coverage for ``_retry_after_to_float`` edge cases."""

    def test_none_returns_none(self) -> None:
        from cerberus_compliance.client import _retry_after_to_float

        assert _retry_after_to_float(None) is None

    def test_empty_string_returns_none(self) -> None:
        from cerberus_compliance.client import _retry_after_to_float

        assert _retry_after_to_float("   ") is None

    def test_malformed_returns_none(self) -> None:
        from cerberus_compliance.client import _retry_after_to_float

        # Not numeric and not a date-like — the HTTP-date form is parsed
        # by the error module, so here we just expect a graceful None.
        assert _retry_after_to_float("banana-pancakes") is None

    def test_numeric_parsed(self) -> None:
        from cerberus_compliance.client import _retry_after_to_float

        assert _retry_after_to_float("42") == 42.0
        assert _retry_after_to_float("1.5") == 1.5


class TestTopLevelListResponse:
    """When the API returns a JSON list at the top level, wrap it."""

    def test_sync_list_response_is_wrapped(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/items").mock(return_value=httpx.Response(200, json=[1, 2, 3]))
        assert sync_client._request("GET", "/items") == {"data": [1, 2, 3]}

    async def test_async_list_response_is_wrapped(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/items").mock(return_value=httpx.Response(200, json=[1, 2, 3]))
        assert await async_client._request("GET", "/items") == {"data": [1, 2, 3]}


# ---------------------------------------------------------------------------
# Marker test
# ---------------------------------------------------------------------------


def test_insert_resources_marker_appears_exactly_twice() -> None:
    """The literal `# INSERT RESOURCES HERE` marker must appear exactly twice
    in client.py (once per ``__init__``, sync + async). Resources subagents
    rely on this marker for surgical insertion.
    """
    src = Path(__file__).resolve().parent.parent / "cerberus_compliance" / "client.py"
    content = src.read_text(encoding="utf-8")
    occurrences = content.count("# INSERT RESOURCES HERE")
    assert occurrences == 2, f"Expected exactly 2 markers, found {occurrences}"
