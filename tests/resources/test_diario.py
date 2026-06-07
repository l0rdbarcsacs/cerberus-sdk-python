"""Tests for ``cerberus_compliance.resources.diario``."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.errors import CerberusAPIError
from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource
from cerberus_compliance.resources.diario import (
    AsyncDiarioResource,
    DiarioResource,
)

# ---------------------------------------------------------------------------
# Static structural tests
# ---------------------------------------------------------------------------


class TestDiarioMeta:
    def test_sync_prefix(self) -> None:
        assert DiarioResource._path_prefix == "/diario"

    def test_async_prefix(self) -> None:
        assert AsyncDiarioResource._path_prefix == "/diario"

    def test_sync_subclass(self) -> None:
        assert issubclass(DiarioResource, BaseResource)

    def test_async_subclass(self) -> None:
        assert issubclass(AsyncDiarioResource, AsyncBaseResource)


def _evento(id_: str) -> dict[str, Any]:
    """A minimal but realistic ``DiarioEventoItem`` for fixtures."""
    return {
        "id": id_,
        "rut_canonical": "765432109",
        "razon_social": "Empresa Demo SpA",
        "tipo": "constitucion",
        "fecha_publicacion": "2026-01-15",
        "edicion_do": "44.123",
        "resumen": None,
        "pdf_url": None,
        "entity_id": None,
        "created_at": "2026-01-16T00:00:00Z",
        "sii": None,
    }


# ---------------------------------------------------------------------------
# Sync behaviour
# ---------------------------------------------------------------------------


class TestDiarioSync:
    def test_list_no_filters(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        body = {
            "items": [_evento("e1"), _evento("e2")],
            "total": 2,
            "limit": 20,
            "offset": 0,
        }
        route = respx_mock.get("/diario").mock(return_value=httpx.Response(200, json=body))
        resource = DiarioResource(sync_client)
        result = resource.list_eventos()
        assert result == body
        assert route.called
        assert route.calls.last.request.url.query == b""

    def test_list_with_all_filters(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/diario",
            params={
                "rut": "76.543.210-9",
                "tipo": "fusion",
                "desde": "2026-01-01",
                "hasta": "2026-02-01",
                "q": "banco",
                "entity_id": "11111111-1111-1111-1111-111111111111",
                "limit": "5",
                "offset": "10",
            },
        ).mock(return_value=httpx.Response(200, json={"items": [], "total": 0}))
        resource = DiarioResource(sync_client)
        resource.list_eventos(
            rut="76.543.210-9",
            tipo="fusion",
            desde="2026-01-01",
            hasta="2026-02-01",
            q="banco",
            entity_id="11111111-1111-1111-1111-111111111111",
            limit=5,
            offset=10,
        )
        assert route.called

    def test_list_with_tipo(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/diario", params={"tipo": "disolucion"}).mock(
            return_value=httpx.Response(200, json={"items": [], "total": 0})
        )
        resource = DiarioResource(sync_client)
        result = resource.list_eventos(tipo="disolucion")
        assert result == {"items": [], "total": 0}
        assert route.called

    def test_list_drops_none(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/diario").mock(
            return_value=httpx.Response(200, json={"items": [], "total": 0})
        )
        resource = DiarioResource(sync_client)
        resource.list_eventos(rut=None, tipo=None, desde=None, hasta=None, q=None)
        assert route.called
        assert route.calls.last.request.url.query == b""

    def test_iter_all_single_page(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        # One page, total matches the page contents — must stop after the
        # first request without issuing a second.
        route = respx_mock.get("/diario", params={"limit": "100", "offset": "0"}).mock(
            return_value=httpx.Response(
                200,
                json={"items": [_evento("a"), _evento("b")], "total": 2},
            )
        )
        resource = DiarioResource(sync_client)
        items = list(resource.iter_all())
        assert [it["id"] for it in items] == ["a", "b"]
        assert route.call_count == 1

    def test_iter_all_multi_page(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        # Full first page of 100, then a partial tail page; iter_all walks
        # both before stopping on offset >= total.
        page1 = [_evento(f"T{i:03d}") for i in range(100)]
        respx_mock.get("/diario", params={"limit": "100", "offset": "0"}).mock(
            return_value=httpx.Response(200, json={"items": page1, "total": 101})
        )
        respx_mock.get("/diario", params={"limit": "100", "offset": "100"}).mock(
            return_value=httpx.Response(200, json={"items": [_evento("TAIL")], "total": 101})
        )
        resource = DiarioResource(sync_client)
        items = list(resource.iter_all())
        assert len(items) == 101
        assert items[-1]["id"] == "TAIL"

    def test_iter_all_stops_on_total_with_full_page(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        # A full page of exactly `total` items must stop via the
        # `offset >= total` guard, not by waiting for a short page.
        page = [_evento(f"F{i:03d}") for i in range(100)]
        first = respx_mock.get("/diario", params={"limit": "100", "offset": "0"}).mock(
            return_value=httpx.Response(200, json={"items": page, "total": 100})
        )
        second = respx_mock.get("/diario", params={"limit": "100", "offset": "100"}).mock(
            return_value=httpx.Response(200, json={"items": [], "total": 100})
        )
        resource = DiarioResource(sync_client)
        items = list(resource.iter_all())
        assert len(items) == 100
        assert first.call_count == 1
        assert not second.called

    def test_iter_all_empty_first_page(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/diario", params={"limit": "100", "offset": "0"}).mock(
            return_value=httpx.Response(200, json={"items": [], "total": 0})
        )
        resource = DiarioResource(sync_client)
        assert list(resource.iter_all()) == []

    def test_iter_all_short_page_without_total(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        # A short page (< page_size) and a missing/non-int `total` must
        # stop via the short-page guard rather than the total guard.
        first = respx_mock.get("/diario", params={"limit": "100", "offset": "0"}).mock(
            return_value=httpx.Response(200, json={"items": [_evento("only")]})
        )
        second = respx_mock.get("/diario", params={"limit": "100", "offset": "1"}).mock(
            return_value=httpx.Response(200, json={"items": []})
        )
        resource = DiarioResource(sync_client)
        items = list(resource.iter_all())
        assert [it["id"] for it in items] == ["only"]
        assert first.call_count == 1
        assert not second.called

    def test_iter_all_forwards_filters(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/diario",
            params={"tipo": "modificacion", "rut": "1-9", "limit": "100", "offset": "0"},
        ).mock(return_value=httpx.Response(200, json={"items": [], "total": 0}))
        resource = DiarioResource(sync_client)
        assert list(resource.iter_all(tipo="modificacion", rut="1-9")) == []
        assert route.called

    def test_list_500_raises(
        self,
        sync_client: CerberusClient,
        respx_mock: respx.MockRouter,
        problem_json: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Avoid sleeping during retry budget exhaustion.
        monkeypatch.setattr("time.sleep", lambda _s: None)
        respx_mock.get("/diario").mock(
            return_value=httpx.Response(500, json=problem_json(status=500, title="Server Error"))
        )
        resource = DiarioResource(sync_client)
        with pytest.raises(CerberusAPIError):
            resource.list_eventos()


# ---------------------------------------------------------------------------
# Async behaviour
# ---------------------------------------------------------------------------


class TestDiarioAsync:
    async def test_list_no_filters(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        body = {"items": [_evento("z")], "total": 1, "limit": 20, "offset": 0}
        route = respx_mock.get("/diario").mock(return_value=httpx.Response(200, json=body))
        resource = AsyncDiarioResource(async_client)
        assert await resource.list_eventos() == body
        assert route.called
        assert route.calls.last.request.url.query == b""

    async def test_list_with_filters(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/diario", params={"tipo": "liquidacion", "q": "spa"}).mock(
            return_value=httpx.Response(200, json={"items": [], "total": 0})
        )
        resource = AsyncDiarioResource(async_client)
        await resource.list_eventos(tipo="liquidacion", q="spa")
        assert route.called

    async def test_iter_all_multi_page(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        page1 = [_evento(f"X{i:03d}") for i in range(100)]
        respx_mock.get("/diario", params={"limit": "100", "offset": "0"}).mock(
            return_value=httpx.Response(200, json={"items": page1, "total": 102})
        )
        respx_mock.get("/diario", params={"limit": "100", "offset": "100"}).mock(
            return_value=httpx.Response(200, json={"items": [_evento("LAST")], "total": 102})
        )
        resource = AsyncDiarioResource(async_client)
        out: list[dict[str, Any]] = []
        async for item in resource.iter_all():
            out.append(item)
        assert len(out) == 101
        assert out[-1]["id"] == "LAST"

    async def test_iter_all_empty_page_stops(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/diario", params={"limit": "100", "offset": "0"}).mock(
            return_value=httpx.Response(200, json={"items": [], "total": 0})
        )
        resource = AsyncDiarioResource(async_client)
        out: list[dict[str, Any]] = []
        async for item in resource.iter_all():
            out.append(item)
        assert out == []

    async def test_iter_all_stops_on_total(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        page = [_evento(f"G{i:03d}") for i in range(100)]
        first = respx_mock.get("/diario", params={"limit": "100", "offset": "0"}).mock(
            return_value=httpx.Response(200, json={"items": page, "total": 100})
        )
        second = respx_mock.get("/diario", params={"limit": "100", "offset": "100"}).mock(
            return_value=httpx.Response(200, json={"items": [], "total": 100})
        )
        resource = AsyncDiarioResource(async_client)
        out: list[dict[str, Any]] = []
        async for item in resource.iter_all():
            out.append(item)
        assert len(out) == 100
        assert first.call_count == 1
        assert not second.called

    async def test_list_500_raises(
        self,
        async_client: AsyncCerberusClient,
        respx_mock: respx.MockRouter,
        problem_json: Any,
    ) -> None:
        respx_mock.get("/diario").mock(
            return_value=httpx.Response(500, json=problem_json(status=500, title="Server Error"))
        )
        resource = AsyncDiarioResource(async_client)
        with pytest.raises(CerberusAPIError):
            await resource.list_eventos()
