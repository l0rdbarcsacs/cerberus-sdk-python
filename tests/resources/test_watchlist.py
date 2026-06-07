"""Tests for ``cerberus_compliance.resources.watchlist``."""

from __future__ import annotations

import json as _json

import httpx
import pytest
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.errors import NotFoundError, ValidationError
from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource
from cerberus_compliance.resources.watchlist import (
    AsyncWatchlistResource,
    WatchlistResource,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_ENTRY = {
    "id": "11111111-1111-1111-1111-111111111111",
    "rut": "76.275.453-3",
    "rut_canonical": "76275453-3",
    "label": "Proveedor estratégico",
    "last_screened_at": None,
    "match_count": 0,
    "created_at": "2026-06-07T12:00:00Z",
}

_DETAIL = {
    **_ENTRY,
    "match_count": 1,
    "matches": [
        {
            "match_source": "OFAC",
            "match_external_id": "SDN-12345",
            "match_name": "ACME SpA",
            "score": 0.92,
            "first_seen_at": "2026-06-01T00:00:00Z",
            "last_seen_at": "2026-06-07T00:00:00Z",
        }
    ],
}


# ---------------------------------------------------------------------------
# Static structural tests
# ---------------------------------------------------------------------------


class TestWatchlistMeta:
    def test_sync_prefix(self) -> None:
        assert WatchlistResource._path_prefix == "/watchlist"

    def test_async_prefix(self) -> None:
        assert AsyncWatchlistResource._path_prefix == "/watchlist"

    def test_sync_subclass(self) -> None:
        assert issubclass(WatchlistResource, BaseResource)

    def test_async_subclass(self) -> None:
        assert issubclass(AsyncWatchlistResource, AsyncBaseResource)


# ---------------------------------------------------------------------------
# Sync behaviour
# ---------------------------------------------------------------------------


class TestWatchlistSync:
    def test_create(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        route = respx_mock.post("/watchlist").mock(return_value=httpx.Response(201, json=_ENTRY))
        resource = WatchlistResource(sync_client)
        result = resource.create(rut="76.275.453-3", label="Proveedor estratégico")
        assert result == _ENTRY
        sent = _json.loads(route.calls.last.request.content)
        assert sent == {"rut": "76.275.453-3", "label": "Proveedor estratégico"}

    def test_create_omits_none_label(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.post("/watchlist").mock(return_value=httpx.Response(201, json=_ENTRY))
        resource = WatchlistResource(sync_client)
        resource.create(rut="76.275.453-3")
        sent = _json.loads(route.calls.last.request.content)
        assert sent == {"rut": "76.275.453-3"}
        assert "label" not in sent

    def test_create_invalid_rut_422(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.post("/watchlist").mock(
            return_value=httpx.Response(
                422,
                json={
                    "title": "Unprocessable Entity",
                    "status": 422,
                    "detail": "Invalid RUT: cannot be canonicalised",
                },
            )
        )
        resource = WatchlistResource(sync_client)
        with pytest.raises(ValidationError):
            resource.create(rut="not-a-rut")

    def test_list(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        body = {"entries": [_ENTRY], "total": 1}
        respx_mock.get("/watchlist").mock(return_value=httpx.Response(200, json=body))
        resource = WatchlistResource(sync_client)
        result = resource.list()
        assert result == body
        assert result["total"] == len(result["entries"])

    def test_list_empty(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        body = {"entries": [], "total": 0}
        respx_mock.get("/watchlist").mock(return_value=httpx.Response(200, json=body))
        resource = WatchlistResource(sync_client)
        assert resource.list() == body

    def test_get(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        entry_id = _ENTRY["id"]
        respx_mock.get(f"/watchlist/{entry_id}").mock(
            return_value=httpx.Response(200, json=_DETAIL)
        )
        resource = WatchlistResource(sync_client)
        result = resource.get(entry_id)
        assert result == _DETAIL
        assert result["match_count"] == len(result["matches"])

    def test_get_404(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        respx_mock.get("/watchlist/missing").mock(
            return_value=httpx.Response(
                404, json={"title": "Watchlist entry not found", "status": 404}
            )
        )
        resource = WatchlistResource(sync_client)
        with pytest.raises(NotFoundError):
            resource.get("missing")

    def test_get_encodes_id(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        # A traversal-style id must be percent-encoded, never escape the prefix.
        route = respx_mock.get("/watchlist/%2E%2E%2Fadmin").mock(
            return_value=httpx.Response(200, json=_DETAIL)
        )
        resource = WatchlistResource(sync_client)
        resource.get("../admin")
        assert route.called

    def test_delete(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        entry_id = _ENTRY["id"]
        route = respx_mock.delete(f"/watchlist/{entry_id}").mock(return_value=httpx.Response(204))
        resource = WatchlistResource(sync_client)
        assert resource.delete(entry_id) is None
        assert route.called

    def test_delete_encodes_id(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.delete("/watchlist/%2E%2E%2Fadmin").mock(
            return_value=httpx.Response(204)
        )
        resource = WatchlistResource(sync_client)
        resource.delete("../admin")
        assert route.called

    def test_delete_404(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        respx_mock.delete("/watchlist/missing").mock(
            return_value=httpx.Response(
                404, json={"title": "Watchlist entry not found", "status": 404}
            )
        )
        resource = WatchlistResource(sync_client)
        with pytest.raises(NotFoundError):
            resource.delete("missing")


# ---------------------------------------------------------------------------
# Async behaviour
# ---------------------------------------------------------------------------


class TestWatchlistAsync:
    async def test_create(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.post("/watchlist").mock(return_value=httpx.Response(201, json=_ENTRY))
        resource = AsyncWatchlistResource(async_client)
        result = await resource.create(rut="76.275.453-3", label="L")
        assert result == _ENTRY
        sent = _json.loads(route.calls.last.request.content)
        assert sent == {"rut": "76.275.453-3", "label": "L"}

    async def test_create_omits_none_label(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.post("/watchlist").mock(return_value=httpx.Response(201, json=_ENTRY))
        resource = AsyncWatchlistResource(async_client)
        await resource.create(rut="76.275.453-3")
        sent = _json.loads(route.calls.last.request.content)
        assert sent == {"rut": "76.275.453-3"}

    async def test_list(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        body = {"entries": [], "total": 0}
        respx_mock.get("/watchlist").mock(return_value=httpx.Response(200, json=body))
        resource = AsyncWatchlistResource(async_client)
        assert await resource.list() == body

    async def test_get(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        entry_id = _ENTRY["id"]
        respx_mock.get(f"/watchlist/{entry_id}").mock(
            return_value=httpx.Response(200, json=_DETAIL)
        )
        resource = AsyncWatchlistResource(async_client)
        assert await resource.get(entry_id) == _DETAIL

    async def test_get_404(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/watchlist/missing").mock(
            return_value=httpx.Response(
                404, json={"title": "Watchlist entry not found", "status": 404}
            )
        )
        resource = AsyncWatchlistResource(async_client)
        with pytest.raises(NotFoundError):
            await resource.get("missing")

    async def test_delete(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        entry_id = _ENTRY["id"]
        route = respx_mock.delete(f"/watchlist/{entry_id}").mock(return_value=httpx.Response(204))
        resource = AsyncWatchlistResource(async_client)
        assert await resource.delete(entry_id) is None
        assert route.called

    async def test_delete_encodes_id(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.delete("/watchlist/%2E%2E%2Fadmin").mock(
            return_value=httpx.Response(204)
        )
        resource = AsyncWatchlistResource(async_client)
        await resource.delete("../admin")
        assert route.called
