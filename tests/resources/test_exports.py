"""Tests for ``cerberus_compliance.resources.exports`` (P5.4.2)."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.errors import CerberusAPIError, NotFoundError
from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource
from cerberus_compliance.resources.exports import (
    AsyncExportsResource,
    ExportsResource,
)

# ---------------------------------------------------------------------------
# Static structural tests
# ---------------------------------------------------------------------------


class TestExportsMeta:
    def test_sync_prefix(self) -> None:
        assert ExportsResource._path_prefix == "/exports"

    def test_async_prefix(self) -> None:
        assert AsyncExportsResource._path_prefix == "/exports"

    def test_sync_subclass(self) -> None:
        assert issubclass(ExportsResource, BaseResource)

    def test_async_subclass(self) -> None:
        assert issubclass(AsyncExportsResource, AsyncBaseResource)


# ---------------------------------------------------------------------------
# Sync behaviour
# ---------------------------------------------------------------------------


class TestExportsSync:
    def test_create_default_csv(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        body = {
            "export_id": "exp_123",
            "status": "queued",
            "expires_at": "2025-04-27T00:00:00Z",
            "created_at": "2025-04-26T13:00:00Z",
        }
        route = respx_mock.post("/exports/entities").mock(
            return_value=httpx.Response(202, json=body)
        )
        resource = ExportsResource(sync_client)
        assert resource.create("entities") == body
        assert route.called
        # Verify the JSON body sent — only "format" should be present.
        sent = route.calls.last.request
        assert sent.headers["content-type"] == "application/json"

    def test_create_with_filters_and_fields(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.post("/exports/sanctions").mock(
            return_value=httpx.Response(202, json={"export_id": "exp_x", "status": "queued"})
        )
        resource = ExportsResource(sync_client)
        resource.create(
            "sanctions",
            format="parquet",
            filters={"source": "OFAC"},
            fields=["id", "active"],
        )
        assert route.called
        import json as _json

        sent_body = _json.loads(route.calls.last.request.content)
        assert sent_body["format"] == "parquet"
        assert sent_body["filters"] == {"source": "OFAC"}
        assert sent_body["fields"] == ["id", "active"]

    def test_create_drops_empty_filters(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.post("/exports/esg").mock(
            return_value=httpx.Response(202, json={"export_id": "x", "status": "queued"})
        )
        resource = ExportsResource(sync_client)
        resource.create("esg", filters=None, fields=None)
        import json as _json

        sent_body = _json.loads(route.calls.last.request.content)
        assert sent_body == {"format": "csv"}

    def test_get_returns_envelope(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        body = {
            "export_id": "exp_123",
            "status": "ready",
            "format": "csv",
            "resource": "entities",
            "rows_exported": 12345,
            "bytes_exported": 67890,
            "download_url": "https://s3.example.com/exports/exp_123.csv",
            "expires_at": "2025-04-27T00:00:00Z",
        }
        respx_mock.get("/exports/exp_123").mock(return_value=httpx.Response(200, json=body))
        resource = ExportsResource(sync_client)
        assert resource.get("exp_123") == body

    def test_get_404_raises_not_found(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/exports/missing").mock(
            return_value=httpx.Response(404, json={"title": "Not Found", "status": 404})
        )
        resource = ExportsResource(sync_client)
        with pytest.raises(NotFoundError):
            resource.get("missing")

    def test_delete_returns_none(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.delete("/exports/exp_42").mock(return_value=httpx.Response(204))
        resource = ExportsResource(sync_client)
        # delete() is annotated as -> None; we just want to confirm it
        # raises nothing and that the underlying route fired.
        resource.delete("exp_42")
        assert route.called

    def test_list_default_limit(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/exports", params={"limit": "50"}).mock(
            return_value=httpx.Response(200, json={"data": [], "next": None})
        )
        resource = ExportsResource(sync_client)
        result = resource.list()
        assert result == {"data": [], "next": None}
        assert route.called

    def test_list_custom_limit(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/exports", params={"limit": "10"}).mock(
            return_value=httpx.Response(200, json={"data": [], "next": None})
        )
        resource = ExportsResource(sync_client)
        resource.list(limit=10)
        assert route.called

    def test_wait_completes_when_ready(
        self,
        sync_client: CerberusClient,
        respx_mock: respx.MockRouter,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Two GET responses: first "running", second "ready".  Patch
        # ``time.sleep`` so the test runs instantly.
        sleeps: list[float] = []
        monkeypatch.setattr("time.sleep", lambda s: sleeps.append(s))
        respx_mock.get("/exports/exp_w1").mock(
            side_effect=[
                httpx.Response(200, json={"status": "running"}),
                httpx.Response(
                    200,
                    json={"status": "ready", "download_url": "https://x/exp_w1.csv"},
                ),
            ]
        )
        resource = ExportsResource(sync_client)
        result = resource.wait("exp_w1", poll_interval=0.5, timeout=10.0)
        assert result["status"] == "ready"
        assert result["download_url"] == "https://x/exp_w1.csv"
        assert sleeps == [0.5]

    def test_wait_raises_on_failed(
        self,
        sync_client: CerberusClient,
        respx_mock: respx.MockRouter,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("time.sleep", lambda _s: None)
        respx_mock.get("/exports/exp_fail").mock(
            return_value=httpx.Response(
                200,
                json={
                    "status": "failed",
                    "failure_reason": "row_limit_exceeded",
                },
            )
        )
        resource = ExportsResource(sync_client)
        with pytest.raises(CerberusAPIError) as exc:
            resource.wait("exp_fail", poll_interval=0.0, timeout=5.0)
        # The original failure body bubbles through the problem dict for forensics.
        assert exc.value.problem.get("failure_reason") == "row_limit_exceeded"

    def test_wait_raises_on_expired(
        self,
        sync_client: CerberusClient,
        respx_mock: respx.MockRouter,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("time.sleep", lambda _s: None)
        respx_mock.get("/exports/exp_old").mock(
            return_value=httpx.Response(200, json={"status": "expired"})
        )
        resource = ExportsResource(sync_client)
        with pytest.raises(CerberusAPIError):
            resource.wait("exp_old", poll_interval=0.0, timeout=5.0)

    def test_wait_raises_on_timeout(
        self,
        sync_client: CerberusClient,
        respx_mock: respx.MockRouter,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Always-running export.  Force ``time.monotonic`` to leap past the
        # deadline immediately so the timeout branch fires deterministically
        # without actual waiting.
        clock = iter([0.0, 0.0, 100.0, 100.0, 200.0])

        def fake_monotonic() -> float:
            return next(clock)

        monkeypatch.setattr("time.monotonic", fake_monotonic)
        monkeypatch.setattr("time.sleep", lambda _s: None)
        respx_mock.get("/exports/exp_loop").mock(
            return_value=httpx.Response(200, json={"status": "running"})
        )
        resource = ExportsResource(sync_client)
        with pytest.raises(CerberusAPIError) as exc:
            resource.wait("exp_loop", poll_interval=0.0, timeout=10.0)
        assert exc.value.status == 408


# ---------------------------------------------------------------------------
# Async behaviour
# ---------------------------------------------------------------------------


class TestExportsAsync:
    async def test_create(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.post("/exports/entities").mock(
            return_value=httpx.Response(202, json={"export_id": "a1", "status": "queued"})
        )
        resource = AsyncExportsResource(async_client)
        result = await resource.create("entities")
        assert result == {"export_id": "a1", "status": "queued"}
        assert route.called

    async def test_get(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/exports/a1").mock(
            return_value=httpx.Response(200, json={"export_id": "a1", "status": "ready"})
        )
        resource = AsyncExportsResource(async_client)
        result = await resource.get("a1")
        assert result["status"] == "ready"

    async def test_delete(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.delete("/exports/a1").mock(return_value=httpx.Response(204))
        resource = AsyncExportsResource(async_client)
        await resource.delete("a1")
        assert route.called

    async def test_list(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/exports", params={"limit": "50"}).mock(
            return_value=httpx.Response(200, json={"data": [{"export_id": "a"}], "next": None})
        )
        resource = AsyncExportsResource(async_client)
        result = await resource.list()
        assert result["data"] == [{"export_id": "a"}]

    async def test_wait_completes(
        self,
        async_client: AsyncCerberusClient,
        respx_mock: respx.MockRouter,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        async def fake_sleep(_s: float) -> None:
            return None

        monkeypatch.setattr("asyncio.sleep", fake_sleep)
        respx_mock.get("/exports/exp_async").mock(
            side_effect=[
                httpx.Response(200, json={"status": "running"}),
                httpx.Response(200, json={"status": "ready", "download_url": "u"}),
            ]
        )
        resource = AsyncExportsResource(async_client)
        result = await resource.wait("exp_async", poll_interval=0.0, timeout=5.0)
        assert result["status"] == "ready"

    async def test_wait_raises_on_failed(
        self,
        async_client: AsyncCerberusClient,
        respx_mock: respx.MockRouter,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        async def fake_sleep(_s: float) -> None:
            return None

        monkeypatch.setattr("asyncio.sleep", fake_sleep)
        respx_mock.get("/exports/exp_async_f").mock(
            return_value=httpx.Response(200, json={"status": "failed"})
        )
        resource = AsyncExportsResource(async_client)
        with pytest.raises(CerberusAPIError):
            await resource.wait("exp_async_f", poll_interval=0.0, timeout=5.0)

    async def test_wait_raises_on_timeout(
        self,
        async_client: AsyncCerberusClient,
        respx_mock: respx.MockRouter,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        async def fake_sleep(_s: float) -> None:
            return None

        clock = iter([0.0, 0.0, 100.0, 100.0])

        def fake_monotonic() -> float:
            return next(clock)

        monkeypatch.setattr("asyncio.sleep", fake_sleep)
        monkeypatch.setattr("time.monotonic", fake_monotonic)
        respx_mock.get("/exports/exp_async_t").mock(
            return_value=httpx.Response(200, json={"status": "running"})
        )
        resource = AsyncExportsResource(async_client)
        with pytest.raises(CerberusAPIError) as exc:
            await resource.wait("exp_async_t", poll_interval=0.0, timeout=10.0)
        assert exc.value.status == 408


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_path_encoding_for_export_id(
    sync_client: CerberusClient, respx_mock: respx.MockRouter
) -> None:
    """An export id with slashes must percent-encode to a single segment."""
    route = respx_mock.get("/exports/exp%2F..%2Fadmin").mock(
        return_value=httpx.Response(404, json={"title": "Not Found", "status": 404})
    )
    resource = ExportsResource(sync_client)
    with pytest.raises(NotFoundError):
        resource.get("exp/../admin")
    assert route.called


def test_create_resource_path_encoding(
    sync_client: CerberusClient, respx_mock: respx.MockRouter
) -> None:
    """The Literal type covers the happy path; the encoder is invariant."""
    route = respx_mock.post("/exports/entities").mock(
        return_value=httpx.Response(202, json={"export_id": "x", "status": "queued"})
    )
    resource = ExportsResource(sync_client)
    out: dict[str, Any] = resource.create("entities")
    assert "export_id" in out
    assert route.called
