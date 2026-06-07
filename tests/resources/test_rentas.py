"""Tests for ``cerberus_compliance.resources.rentas`` (rentas vitalicias CMF)."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.errors import CerberusAPIError
from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource
from cerberus_compliance.resources.rentas import (
    AsyncRentasResource,
    RentasResource,
)

# ---------------------------------------------------------------------------
# Static structural tests
# ---------------------------------------------------------------------------


class TestRentasMeta:
    def test_sync_prefix(self) -> None:
        assert RentasResource._path_prefix == "/rentas"

    def test_async_prefix(self) -> None:
        assert AsyncRentasResource._path_prefix == "/rentas"

    def test_sync_subclass(self) -> None:
        assert issubclass(RentasResource, BaseResource)

    def test_async_subclass(self) -> None:
        assert issubclass(AsyncRentasResource, AsyncBaseResource)


# ---------------------------------------------------------------------------
# Sync behaviour
# ---------------------------------------------------------------------------


class TestRentasSync:
    def test_list_no_filters(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        body = {
            "items": [
                {
                    "id": "11111111-1111-1111-1111-111111111111",
                    "periodo_desde": "2025-01-01",
                    "periodo_hasta": "2025-03-31",
                    "metrica": "tasa_interes_media",
                    "dimension_tipo": "pension",
                    "dimension_valor": "vejez",
                    "compania": "Compania de Seguros XYZ",
                    "valor": "3.45",
                    "created_at": "2025-04-10T12:00:00Z",
                }
            ],
            "total": 1,
            "limit": 20,
            "offset": 0,
        }
        route = respx_mock.get("/rentas").mock(return_value=httpx.Response(200, json=body))
        resource = RentasResource(sync_client)
        result = resource.list()
        assert result == body
        assert route.called
        assert route.calls.last.request.url.query == b""

    def test_list_with_all_filters(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/rentas",
            params={
                "compania": "Seguros ABC",
                "metrica": "prima_unica",
                "dimension_tipo": "intermediario",
                "desde": "2024-01-01",
                "hasta": "2025-12-31",
                "q": "Segur",
                "limit": "50",
                "offset": "10",
            },
        ).mock(
            return_value=httpx.Response(
                200, json={"items": [], "total": 0, "limit": 50, "offset": 10}
            )
        )
        resource = RentasResource(sync_client)
        result = resource.list(
            compania="Seguros ABC",
            metrica="prima_unica",
            dimension_tipo="intermediario",
            desde="2024-01-01",
            hasta="2025-12-31",
            q="Segur",
            limit=50,
            offset=10,
        )
        assert result == {"items": [], "total": 0, "limit": 50, "offset": 10}
        assert route.called

    def test_list_drops_none(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/rentas").mock(
            return_value=httpx.Response(
                200, json={"items": [], "total": 0, "limit": 20, "offset": 0}
            )
        )
        resource = RentasResource(sync_client)
        resource.list(
            compania=None,
            metrica=None,
            dimension_tipo=None,
            desde=None,
            hasta=None,
            q=None,
            limit=None,
            offset=None,
        )
        assert route.called
        assert route.calls.last.request.url.query == b""

    def test_list_with_metrica_only(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/rentas", params={"metrica": "tasa_interes_media"}).mock(
            return_value=httpx.Response(
                200, json={"items": [], "total": 0, "limit": 20, "offset": 0}
            )
        )
        resource = RentasResource(sync_client)
        resource.list(metrica="tasa_interes_media")
        assert route.called

    def test_iter_all_single_page(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        # One short page — must stop after the first request.
        route = respx_mock.get("/rentas", params={"limit": "100", "offset": "0"}).mock(
            return_value=httpx.Response(
                200,
                json={
                    "items": [{"id": "a", "compania": "X"}, {"id": "b", "compania": "Y"}],
                    "total": 2,
                    "limit": 100,
                    "offset": 0,
                },
            )
        )
        resource = RentasResource(sync_client)
        items = list(resource.iter_all())
        assert items == [{"id": "a", "compania": "X"}, {"id": "b", "compania": "Y"}]
        assert route.call_count == 1

    def test_iter_all_multi_page(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        # Full first page, partial second page; both walked.
        page1 = [{"id": f"r{i:03d}"} for i in range(100)]
        respx_mock.get("/rentas", params={"limit": "100", "offset": "0"}).mock(
            return_value=httpx.Response(
                200, json={"items": page1, "total": 101, "limit": 100, "offset": 0}
            )
        )
        respx_mock.get("/rentas", params={"limit": "100", "offset": "100"}).mock(
            return_value=httpx.Response(
                200,
                json={"items": [{"id": "TAIL"}], "total": 101, "limit": 100, "offset": 100},
            )
        )
        resource = RentasResource(sync_client)
        items = list(resource.iter_all())
        assert len(items) == 101
        assert items[-1] == {"id": "TAIL"}

    def test_iter_all_empty_page_stops(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/rentas", params={"limit": "100", "offset": "0"}).mock(
            return_value=httpx.Response(
                200, json={"items": [], "total": 0, "limit": 100, "offset": 0}
            )
        )
        resource = RentasResource(sync_client)
        assert list(resource.iter_all()) == []
        assert route.call_count == 1

    def test_iter_all_forwards_filters(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/rentas",
            params={
                "compania": "Seguros ABC",
                "metrica": "prima_unica",
                "dimension_tipo": "pension",
                "desde": "2024-01-01",
                "hasta": "2025-12-31",
                "q": "Seg",
                "limit": "100",
                "offset": "0",
            },
        ).mock(
            return_value=httpx.Response(
                200, json={"items": [], "total": 0, "limit": 100, "offset": 0}
            )
        )
        resource = RentasResource(sync_client)
        assert (
            list(
                resource.iter_all(
                    compania="Seguros ABC",
                    metrica="prima_unica",
                    dimension_tipo="pension",
                    desde="2024-01-01",
                    hasta="2025-12-31",
                    q="Seg",
                )
            )
            == []
        )
        assert route.called

    def test_iter_all_exact_full_page_then_empty(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        # Exactly one full page (== page_size) forces a second request that
        # returns empty, exercising the offset-increment branch.
        page1 = [{"id": f"f{i:03d}"} for i in range(100)]
        respx_mock.get("/rentas", params={"limit": "100", "offset": "0"}).mock(
            return_value=httpx.Response(
                200, json={"items": page1, "total": 100, "limit": 100, "offset": 0}
            )
        )
        respx_mock.get("/rentas", params={"limit": "100", "offset": "100"}).mock(
            return_value=httpx.Response(
                200, json={"items": [], "total": 100, "limit": 100, "offset": 100}
            )
        )
        resource = RentasResource(sync_client)
        items = list(resource.iter_all())
        assert len(items) == 100

    def test_list_500_raises(
        self,
        sync_client: CerberusClient,
        respx_mock: respx.MockRouter,
        problem_json: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Avoid sleeping during retry budget exhaustion.
        monkeypatch.setattr("time.sleep", lambda _s: None)
        respx_mock.get("/rentas").mock(
            return_value=httpx.Response(500, json=problem_json(status=500, title="Server Error"))
        )
        resource = RentasResource(sync_client)
        with pytest.raises(CerberusAPIError):
            resource.list()

    def test_list_422_out_of_range_limit_raises(
        self,
        sync_client: CerberusClient,
        respx_mock: respx.MockRouter,
        problem_json: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # limit caps are server-side (ge=1, le=100): the SDK forwards the
        # value untouched and surfaces the server's 422 as an API error.
        monkeypatch.setattr("time.sleep", lambda _s: None)
        respx_mock.get("/rentas", params={"limit": "999"}).mock(
            return_value=httpx.Response(
                422, json=problem_json(status=422, title="Unprocessable Entity")
            )
        )
        resource = RentasResource(sync_client)
        with pytest.raises(CerberusAPIError):
            resource.list(limit=999)


# ---------------------------------------------------------------------------
# Async behaviour
# ---------------------------------------------------------------------------


class TestRentasAsync:
    async def test_list_no_filters(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        body = {
            "items": [{"id": "x", "compania": "ACME", "valor": "1.23"}],
            "total": 1,
            "limit": 20,
            "offset": 0,
        }
        route = respx_mock.get("/rentas").mock(return_value=httpx.Response(200, json=body))
        resource = AsyncRentasResource(async_client)
        assert await resource.list() == body
        assert route.called
        assert route.calls.last.request.url.query == b""

    async def test_list_with_filters(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/rentas",
            params={"dimension_tipo": "pension", "q": "vida", "limit": "5", "offset": "0"},
        ).mock(
            return_value=httpx.Response(
                200, json={"items": [], "total": 0, "limit": 5, "offset": 0}
            )
        )
        resource = AsyncRentasResource(async_client)
        await resource.list(dimension_tipo="pension", q="vida", limit=5, offset=0)
        assert route.called

    async def test_iter_all_multi_page(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        page1 = [{"id": f"a{i:03d}"} for i in range(100)]
        respx_mock.get("/rentas", params={"limit": "100", "offset": "0"}).mock(
            return_value=httpx.Response(
                200, json={"items": page1, "total": 101, "limit": 100, "offset": 0}
            )
        )
        respx_mock.get("/rentas", params={"limit": "100", "offset": "100"}).mock(
            return_value=httpx.Response(
                200, json={"items": [{"id": "LAST"}], "total": 101, "limit": 100, "offset": 100}
            )
        )
        resource = AsyncRentasResource(async_client)
        out: list[dict[str, Any]] = []
        async for item in resource.iter_all():
            out.append(item)
        assert len(out) == 101
        assert out[-1] == {"id": "LAST"}

    async def test_iter_all_empty_page_stops(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/rentas", params={"limit": "100", "offset": "0"}).mock(
            return_value=httpx.Response(
                200, json={"items": [], "total": 0, "limit": 100, "offset": 0}
            )
        )
        resource = AsyncRentasResource(async_client)
        out: list[dict[str, Any]] = []
        async for item in resource.iter_all():
            out.append(item)
        assert out == []

    async def test_iter_all_forwards_filters(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/rentas",
            params={"compania": "ACME", "limit": "100", "offset": "0"},
        ).mock(
            return_value=httpx.Response(
                200, json={"items": [], "total": 0, "limit": 100, "offset": 0}
            )
        )
        resource = AsyncRentasResource(async_client)
        out: list[dict[str, Any]] = []
        async for item in resource.iter_all(compania="ACME"):
            out.append(item)
        assert out == []
        assert route.called

    async def test_list_500_raises(
        self,
        async_client: AsyncCerberusClient,
        respx_mock: respx.MockRouter,
        problem_json: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("asyncio.sleep", _noop_async_sleep)
        respx_mock.get("/rentas").mock(
            return_value=httpx.Response(500, json=problem_json(status=500, title="Server Error"))
        )
        resource = AsyncRentasResource(async_client)
        with pytest.raises(CerberusAPIError):
            await resource.list()


async def _noop_async_sleep(_s: float) -> None:
    """No-op replacement for ``asyncio.sleep`` during retry exhaustion."""
    return None
