"""Tests for ``cerberus_compliance.resources.hechos``."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.errors import CerberusAPIError, NotFoundError
from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource
from cerberus_compliance.resources.hechos import (
    AsyncHechosResource,
    HechosResource,
)


def _envelope(items: list[dict[str, Any]], total: int) -> dict[str, Any]:
    return {"items": items, "total": total, "limit": 100, "offset": 0}


# ---------------------------------------------------------------------------
# Static structural tests
# ---------------------------------------------------------------------------


class TestHechosMeta:
    def test_sync_prefix(self) -> None:
        assert HechosResource._path_prefix == "/hechos"

    def test_async_prefix(self) -> None:
        assert AsyncHechosResource._path_prefix == "/hechos"

    def test_sync_subclass(self) -> None:
        assert issubclass(HechosResource, BaseResource)

    def test_async_subclass(self) -> None:
        assert issubclass(AsyncHechosResource, AsyncBaseResource)


# ---------------------------------------------------------------------------
# Sync — list_hechos
# ---------------------------------------------------------------------------


class TestListHechosSync:
    def test_no_filters(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        body = _envelope([{"id": "a", "asunto": "Dividendo"}], total=1)
        route = respx_mock.get("/hechos").mock(return_value=httpx.Response(200, json=body))
        resource = HechosResource(sync_client)
        result = resource.list_hechos()
        assert result == body
        assert route.called
        assert route.calls.last.request.url.query == b""

    def test_all_filters(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        route = respx_mock.get(
            "/hechos",
            params={
                "rut": "76.543.210-9",
                "desde": "2026-01-01",
                "hasta": "2026-02-01",
                "q": "capital",
                "event_type": "dividend",
                "limit": "5",
                "offset": "10",
            },
        ).mock(return_value=httpx.Response(200, json=_envelope([], 0)))
        resource = HechosResource(sync_client)
        resource.list_hechos(
            rut="76.543.210-9",
            desde="2026-01-01",
            hasta="2026-02-01",
            q="capital",
            event_type="dividend",
            limit=5,
            offset=10,
        )
        assert route.called

    def test_drops_none(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        route = respx_mock.get("/hechos").mock(
            return_value=httpx.Response(200, json=_envelope([], 0))
        )
        resource = HechosResource(sync_client)
        resource.list_hechos(rut=None, desde=None, hasta=None, q=None, event_type=None)
        assert route.called
        assert route.calls.last.request.url.query == b""

    def test_404_raises(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter, problem_json: Any
    ) -> None:
        respx_mock.get("/hechos").mock(
            return_value=httpx.Response(404, json=problem_json(status=404, title="Not Found"))
        )
        resource = HechosResource(sync_client)
        with pytest.raises(NotFoundError):
            resource.list_hechos()

    def test_500_raises(
        self,
        sync_client: CerberusClient,
        respx_mock: respx.MockRouter,
        problem_json: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("time.sleep", lambda _s: None)
        respx_mock.get("/hechos").mock(
            return_value=httpx.Response(500, json=problem_json(status=500, title="Boom"))
        )
        resource = HechosResource(sync_client)
        with pytest.raises(CerberusAPIError):
            resource.list_hechos()


# ---------------------------------------------------------------------------
# Sync — iter_all
# ---------------------------------------------------------------------------


class TestIterAllSync:
    def test_single_page_stops_on_total(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/hechos", params={"limit": "100", "offset": "0"}).mock(
            return_value=httpx.Response(200, json=_envelope([{"id": "a"}, {"id": "b"}], total=2))
        )
        resource = HechosResource(sync_client)
        items = list(resource.iter_all())
        assert items == [{"id": "a"}, {"id": "b"}]
        assert route.call_count == 1

    def test_multi_page(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        page1 = [{"id": f"r{i:03d}"} for i in range(100)]
        respx_mock.get("/hechos", params={"limit": "100", "offset": "0"}).mock(
            return_value=httpx.Response(200, json={"items": page1, "total": 101})
        )
        respx_mock.get("/hechos", params={"limit": "100", "offset": "100"}).mock(
            return_value=httpx.Response(200, json={"items": [{"id": "TAIL"}], "total": 101})
        )
        resource = HechosResource(sync_client)
        items = list(resource.iter_all())
        assert len(items) == 101
        assert items[-1] == {"id": "TAIL"}

    def test_empty_page_stops(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/hechos", params={"limit": "100", "offset": "0"}).mock(
            return_value=httpx.Response(200, json=_envelope([], 0))
        )
        resource = HechosResource(sync_client)
        assert list(resource.iter_all()) == []

    def test_stops_when_page_shorter_than_size_without_total(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        # No usable ``total`` field — fall back to the short-page guard.
        route = respx_mock.get("/hechos", params={"limit": "100", "offset": "0"}).mock(
            return_value=httpx.Response(200, json={"items": [{"id": "x"}], "total": None})
        )
        resource = HechosResource(sync_client)
        assert list(resource.iter_all()) == [{"id": "x"}]
        assert route.call_count == 1

    def test_forwards_filters(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/hechos",
            params={
                "rut": "1-9",
                "desde": "2026-01-01",
                "hasta": "2026-06-01",
                "q": "fusion",
                "event_type": "m_and_a",
                "limit": "100",
                "offset": "0",
            },
        ).mock(return_value=httpx.Response(200, json=_envelope([], 0)))
        resource = HechosResource(sync_client)
        assert (
            list(
                resource.iter_all(
                    rut="1-9",
                    desde="2026-01-01",
                    hasta="2026-06-01",
                    q="fusion",
                    event_type="m_and_a",
                )
            )
            == []
        )
        assert route.called


# ---------------------------------------------------------------------------
# Sync — event-types, bancos, otros
# ---------------------------------------------------------------------------


class TestEventTypesSync:
    def test_no_filters(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        body = {"total": 3, "buckets": [{"event_type": "dividend", "count": 3}]}
        route = respx_mock.get("/hechos/event-types").mock(
            return_value=httpx.Response(200, json=body)
        )
        resource = HechosResource(sync_client)
        assert resource.hechos_event_type_distribution() == body
        assert route.called
        assert route.calls.last.request.url.query == b""

    def test_with_dates(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        route = respx_mock.get(
            "/hechos/event-types", params={"desde": "2026-01-01", "hasta": "2026-02-01"}
        ).mock(return_value=httpx.Response(200, json={"total": 0, "buckets": []}))
        resource = HechosResource(sync_client)
        resource.hechos_event_type_distribution(desde="2026-01-01", hasta="2026-02-01")
        assert route.called


class TestBancosSync:
    def test_no_filters(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        body = _envelope([{"id": "b1", "documento_url": "u"}], total=1)
        route = respx_mock.get("/hechos/bancos").mock(return_value=httpx.Response(200, json=body))
        resource = HechosResource(sync_client)
        assert resource.list_hechos_bancos() == body
        assert route.called
        assert route.calls.last.request.url.query == b""

    def test_all_filters(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        route = respx_mock.get(
            "/hechos/bancos",
            params={
                "entity_id": "11111111-1111-1111-1111-111111111111",
                "rut": "97.000.000-1",
                "nombre": "banco",
                "desde": "2026-01-01",
                "hasta": "2026-02-01",
                "q": "asunto",
                "limit": "7",
                "offset": "3",
            },
        ).mock(return_value=httpx.Response(200, json=_envelope([], 0)))
        resource = HechosResource(sync_client)
        resource.list_hechos_bancos(
            entity_id="11111111-1111-1111-1111-111111111111",
            rut="97.000.000-1",
            nombre="banco",
            desde="2026-01-01",
            hasta="2026-02-01",
            q="asunto",
            limit=7,
            offset=3,
        )
        assert route.called

    def test_422_raises(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter, problem_json: Any
    ) -> None:
        respx_mock.get("/hechos/bancos").mock(
            return_value=httpx.Response(422, json=problem_json(status=422, title="Unprocessable"))
        )
        resource = HechosResource(sync_client)
        with pytest.raises(CerberusAPIError):
            resource.list_hechos_bancos(entity_id="not-a-uuid")


class TestOtrosSync:
    def test_no_filters(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        body = _envelope([{"id": "o1", "entity_kind": "aseguradora"}], total=1)
        route = respx_mock.get("/hechos/otros").mock(return_value=httpx.Response(200, json=body))
        resource = HechosResource(sync_client)
        assert resource.list_hechos_otros() == body
        assert route.called
        assert route.calls.last.request.url.query == b""

    def test_all_filters(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        route = respx_mock.get(
            "/hechos/otros",
            params={
                "rut": "76.000.000-0",
                "entity_kind": "agf",
                "desde": "2026-01-01",
                "hasta": "2026-02-01",
                "q": "nombre",
                "entity_id": "22222222-2222-2222-2222-222222222222",
                "limit": "9",
                "offset": "4",
            },
        ).mock(return_value=httpx.Response(200, json=_envelope([], 0)))
        resource = HechosResource(sync_client)
        resource.list_hechos_otros(
            rut="76.000.000-0",
            entity_kind="agf",
            desde="2026-01-01",
            hasta="2026-02-01",
            q="nombre",
            entity_id="22222222-2222-2222-2222-222222222222",
            limit=9,
            offset=4,
        )
        assert route.called


# ---------------------------------------------------------------------------
# Async behaviour
# ---------------------------------------------------------------------------


class TestHechosAsync:
    async def test_list_hechos(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        body = _envelope([{"id": "a"}], total=1)
        route = respx_mock.get("/hechos", params={"event_type": "litigation"}).mock(
            return_value=httpx.Response(200, json=body)
        )
        resource = AsyncHechosResource(async_client)
        assert await resource.list_hechos(event_type="litigation") == body
        assert route.called

    async def test_list_hechos_all_filters(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/hechos",
            params={
                "rut": "1-9",
                "desde": "2026-01-01",
                "hasta": "2026-02-01",
                "q": "capital",
                "event_type": "dividend",
                "limit": "5",
                "offset": "10",
            },
        ).mock(return_value=httpx.Response(200, json=_envelope([], 0)))
        resource = AsyncHechosResource(async_client)
        await resource.list_hechos(
            rut="1-9",
            desde="2026-01-01",
            hasta="2026-02-01",
            q="capital",
            event_type="dividend",
            limit=5,
            offset=10,
        )
        assert route.called

    async def test_iter_all_forwards_filters(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/hechos",
            params={
                "rut": "1-9",
                "desde": "2026-01-01",
                "hasta": "2026-06-01",
                "q": "fusion",
                "event_type": "m_and_a",
                "limit": "100",
                "offset": "0",
            },
        ).mock(return_value=httpx.Response(200, json=_envelope([], 0)))
        resource = AsyncHechosResource(async_client)
        out: list[dict[str, Any]] = []
        async for item in resource.iter_all(
            rut="1-9",
            desde="2026-01-01",
            hasta="2026-06-01",
            q="fusion",
            event_type="m_and_a",
        ):
            out.append(item)
        assert out == []
        assert route.called

    async def test_list_hechos_404(
        self,
        async_client: AsyncCerberusClient,
        respx_mock: respx.MockRouter,
        problem_json: Any,
    ) -> None:
        respx_mock.get("/hechos").mock(
            return_value=httpx.Response(404, json=problem_json(status=404, title="Not Found"))
        )
        resource = AsyncHechosResource(async_client)
        with pytest.raises(NotFoundError):
            await resource.list_hechos()

    async def test_iter_all_multi_page(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        page1 = [{"id": f"x{i:03d}"} for i in range(100)]
        respx_mock.get("/hechos", params={"limit": "100", "offset": "0"}).mock(
            return_value=httpx.Response(200, json={"items": page1, "total": 101})
        )
        respx_mock.get("/hechos", params={"limit": "100", "offset": "100"}).mock(
            return_value=httpx.Response(200, json={"items": [{"id": "LAST"}], "total": 101})
        )
        resource = AsyncHechosResource(async_client)
        out: list[dict[str, Any]] = []
        async for item in resource.iter_all():
            out.append(item)
        assert len(out) == 101
        assert out[-1] == {"id": "LAST"}

    async def test_iter_all_empty_stops(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/hechos", params={"limit": "100", "offset": "0"}).mock(
            return_value=httpx.Response(200, json=_envelope([], 0))
        )
        resource = AsyncHechosResource(async_client)
        out: list[dict[str, Any]] = []
        async for item in resource.iter_all(q="x"):
            out.append(item)
        assert out == []

    async def test_iter_all_short_page_without_total(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/hechos", params={"limit": "100", "offset": "0"}).mock(
            return_value=httpx.Response(200, json={"items": [{"id": "x"}], "total": None})
        )
        resource = AsyncHechosResource(async_client)
        out: list[dict[str, Any]] = []
        async for item in resource.iter_all():
            out.append(item)
        assert out == [{"id": "x"}]

    async def test_event_type_distribution(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        body = {"total": 1, "buckets": [{"event_type": None, "count": 1}]}
        route = respx_mock.get(
            "/hechos/event-types", params={"desde": "2026-01-01", "hasta": "2026-02-01"}
        ).mock(return_value=httpx.Response(200, json=body))
        resource = AsyncHechosResource(async_client)
        assert (
            await resource.hechos_event_type_distribution(desde="2026-01-01", hasta="2026-02-01")
            == body
        )
        assert route.called

    async def test_event_type_distribution_no_filters(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/hechos/event-types").mock(
            return_value=httpx.Response(200, json={"total": 0, "buckets": []})
        )
        resource = AsyncHechosResource(async_client)
        await resource.hechos_event_type_distribution()
        assert route.calls.last.request.url.query == b""

    async def test_list_bancos(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        body = _envelope([{"id": "b"}], total=1)
        route = respx_mock.get("/hechos/bancos", params={"nombre": "banco"}).mock(
            return_value=httpx.Response(200, json=body)
        )
        resource = AsyncHechosResource(async_client)
        assert await resource.list_hechos_bancos(nombre="banco") == body
        assert route.called

    async def test_list_bancos_all_filters(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/hechos/bancos",
            params={
                "entity_id": "11111111-1111-1111-1111-111111111111",
                "rut": "97.000.000-1",
                "nombre": "banco",
                "desde": "2026-01-01",
                "hasta": "2026-02-01",
                "q": "asunto",
                "limit": "7",
                "offset": "3",
            },
        ).mock(return_value=httpx.Response(200, json=_envelope([], 0)))
        resource = AsyncHechosResource(async_client)
        await resource.list_hechos_bancos(
            entity_id="11111111-1111-1111-1111-111111111111",
            rut="97.000.000-1",
            nombre="banco",
            desde="2026-01-01",
            hasta="2026-02-01",
            q="asunto",
            limit=7,
            offset=3,
        )
        assert route.called

    async def test_list_bancos_no_filters(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/hechos/bancos").mock(
            return_value=httpx.Response(200, json=_envelope([], 0))
        )
        resource = AsyncHechosResource(async_client)
        await resource.list_hechos_bancos()
        assert route.calls.last.request.url.query == b""

    async def test_list_otros(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        body = _envelope([{"id": "o"}], total=1)
        route = respx_mock.get("/hechos/otros", params={"entity_kind": "corredor_bolsa"}).mock(
            return_value=httpx.Response(200, json=body)
        )
        resource = AsyncHechosResource(async_client)
        assert await resource.list_hechos_otros(entity_kind="corredor_bolsa") == body
        assert route.called

    async def test_list_otros_all_filters(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/hechos/otros",
            params={
                "rut": "76.000.000-0",
                "entity_kind": "agf",
                "desde": "2026-01-01",
                "hasta": "2026-02-01",
                "q": "nombre",
                "entity_id": "22222222-2222-2222-2222-222222222222",
                "limit": "9",
                "offset": "4",
            },
        ).mock(return_value=httpx.Response(200, json=_envelope([], 0)))
        resource = AsyncHechosResource(async_client)
        await resource.list_hechos_otros(
            rut="76.000.000-0",
            entity_kind="agf",
            desde="2026-01-01",
            hasta="2026-02-01",
            q="nombre",
            entity_id="22222222-2222-2222-2222-222222222222",
            limit=9,
            offset=4,
        )
        assert route.called

    async def test_list_otros_no_filters(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/hechos/otros").mock(
            return_value=httpx.Response(200, json=_envelope([], 0))
        )
        resource = AsyncHechosResource(async_client)
        await resource.list_hechos_otros()
        assert route.calls.last.request.url.query == b""
