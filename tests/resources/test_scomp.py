"""Tests for ``cerberus_compliance.resources.scomp``."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.errors import CerberusAPIError
from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource
from cerberus_compliance.resources.scomp import (
    AsyncSCOMPResource,
    SCOMPResource,
)

# ---------------------------------------------------------------------------
# Static structural tests
# ---------------------------------------------------------------------------


class TestSCOMPMeta:
    def test_sync_prefix(self) -> None:
        assert SCOMPResource._path_prefix == "/scomp"

    def test_async_prefix(self) -> None:
        assert AsyncSCOMPResource._path_prefix == "/scomp"

    def test_sync_subclass(self) -> None:
        assert issubclass(SCOMPResource, BaseResource)

    def test_async_subclass(self) -> None:
        assert issubclass(AsyncSCOMPResource, AsyncBaseResource)


# ---------------------------------------------------------------------------
# Sync behaviour
# ---------------------------------------------------------------------------


class TestSCOMPSync:
    def test_list_no_filters(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        body = {
            "items": [
                {
                    "id": "11111111-1111-1111-1111-111111111111",
                    "informe": "afiliados",
                    "periodo_desde": "2024-01-01",
                    "periodo_hasta": "2024-01-31",
                    "fila": "Total",
                    "columna": "Hombres",
                    "valor": "1234.56",
                    "meta": {"unidad": "personas"},
                    "created_at": "2024-02-01T00:00:00Z",
                },
            ],
            "total": 1,
            "limit": 20,
            "offset": 0,
        }
        route = respx_mock.get("/scomp").mock(return_value=httpx.Response(200, json=body))
        resource = SCOMPResource(sync_client)
        result = resource.list_estadisticas()
        assert result == body
        assert route.called
        assert route.calls.last.request.url.query == b""

    def test_list_with_all_filters(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/scomp",
            params={
                "desde": "2024-01-01",
                "hasta": "2024-12-31",
                "q": "afiliados",
                "limit": "50",
                "offset": "10",
            },
        ).mock(
            return_value=httpx.Response(
                200, json={"items": [], "total": 0, "limit": 50, "offset": 10}
            )
        )
        resource = SCOMPResource(sync_client)
        result = resource.list_estadisticas(
            desde="2024-01-01",
            hasta="2024-12-31",
            q="afiliados",
            limit=50,
            offset=10,
        )
        assert result == {"items": [], "total": 0, "limit": 50, "offset": 10}
        assert route.called

    def test_list_with_date_bounds_only(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/scomp", params={"desde": "2023-06-01", "hasta": "2023-06-30"}
        ).mock(
            return_value=httpx.Response(
                200, json={"items": [], "total": 0, "limit": 20, "offset": 0}
            )
        )
        resource = SCOMPResource(sync_client)
        resource.list_estadisticas(desde="2023-06-01", hasta="2023-06-30")
        assert route.called

    def test_list_drops_none(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/scomp").mock(
            return_value=httpx.Response(
                200, json={"items": [], "total": 0, "limit": 20, "offset": 0}
            )
        )
        resource = SCOMPResource(sync_client)
        resource.list_estadisticas(desde=None, hasta=None, q=None, limit=None, offset=None)
        assert route.called
        assert route.calls.last.request.url.query == b""

    def test_iter_all_single_page(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        # One short page (< page size 100) — must stop after the first
        # request without issuing a second.
        route = respx_mock.get("/scomp", params={"limit": "100", "offset": "0"}).mock(
            return_value=httpx.Response(
                200,
                json={
                    "items": [{"id": "a", "valor": "1"}, {"id": "b", "valor": "2"}],
                    "total": 2,
                    "limit": 100,
                    "offset": 0,
                },
            )
        )
        resource = SCOMPResource(sync_client)
        items = list(resource.iter_all_estadisticas())
        assert items == [{"id": "a", "valor": "1"}, {"id": "b", "valor": "2"}]
        assert route.call_count == 1

    def test_iter_all_multi_page(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        # Two pages: a full first page, partial second page; iter_all must
        # walk both before stopping.
        page1 = [{"id": f"P{i:03d}"} for i in range(100)]
        respx_mock.get("/scomp", params={"limit": "100", "offset": "0"}).mock(
            return_value=httpx.Response(
                200, json={"items": page1, "total": 101, "limit": 100, "offset": 0}
            )
        )
        respx_mock.get("/scomp", params={"limit": "100", "offset": "100"}).mock(
            return_value=httpx.Response(
                200,
                json={"items": [{"id": "TAIL"}], "total": 101, "limit": 100, "offset": 100},
            )
        )
        resource = SCOMPResource(sync_client)
        items = list(resource.iter_all_estadisticas())
        assert len(items) == 101
        assert items[-1] == {"id": "TAIL"}

    def test_iter_all_empty_first_page(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/scomp", params={"limit": "100", "offset": "0"}).mock(
            return_value=httpx.Response(
                200, json={"items": [], "total": 0, "limit": 100, "offset": 0}
            )
        )
        resource = SCOMPResource(sync_client)
        assert list(resource.iter_all_estadisticas()) == []
        assert route.call_count == 1

    def test_iter_all_forwards_filters(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/scomp",
            params={
                "desde": "2024-01-01",
                "hasta": "2024-06-30",
                "q": "pensiones",
                "limit": "100",
                "offset": "0",
            },
        ).mock(
            return_value=httpx.Response(
                200, json={"items": [], "total": 0, "limit": 100, "offset": 0}
            )
        )
        resource = SCOMPResource(sync_client)
        assert (
            list(
                resource.iter_all_estadisticas(
                    desde="2024-01-01", hasta="2024-06-30", q="pensiones"
                )
            )
            == []
        )
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
        respx_mock.get("/scomp").mock(
            return_value=httpx.Response(500, json=problem_json(status=500, title="Server Error"))
        )
        resource = SCOMPResource(sync_client)
        with pytest.raises(CerberusAPIError):
            resource.list_estadisticas()


# ---------------------------------------------------------------------------
# Async behaviour
# ---------------------------------------------------------------------------


class TestSCOMPAsync:
    async def test_list_no_filters(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        body = {
            "items": [{"id": "AB", "valor": "9.9"}],
            "total": 1,
            "limit": 20,
            "offset": 0,
        }
        route = respx_mock.get("/scomp").mock(return_value=httpx.Response(200, json=body))
        resource = AsyncSCOMPResource(async_client)
        assert await resource.list_estadisticas() == body
        assert route.called
        assert route.calls.last.request.url.query == b""

    async def test_list_with_filters(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/scomp", params={"q": "renta", "limit": "5", "offset": "0"}).mock(
            return_value=httpx.Response(
                200, json={"items": [], "total": 0, "limit": 5, "offset": 0}
            )
        )
        resource = AsyncSCOMPResource(async_client)
        await resource.list_estadisticas(q="renta", limit=5, offset=0)
        assert route.called

    async def test_iter_all_multi_page(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        page1 = [{"id": f"X{i:03d}"} for i in range(100)]
        respx_mock.get("/scomp", params={"limit": "100", "offset": "0"}).mock(
            return_value=httpx.Response(
                200, json={"items": page1, "total": 101, "limit": 100, "offset": 0}
            )
        )
        respx_mock.get("/scomp", params={"limit": "100", "offset": "100"}).mock(
            return_value=httpx.Response(
                200,
                json={"items": [{"id": "LAST"}], "total": 101, "limit": 100, "offset": 100},
            )
        )
        resource = AsyncSCOMPResource(async_client)
        out: list[dict[str, Any]] = []
        async for item in resource.iter_all_estadisticas():
            out.append(item)
        assert len(out) == 101
        assert out[-1] == {"id": "LAST"}

    async def test_iter_all_empty_page_stops(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/scomp", params={"limit": "100", "offset": "0"}).mock(
            return_value=httpx.Response(
                200, json={"items": [], "total": 0, "limit": 100, "offset": 0}
            )
        )
        resource = AsyncSCOMPResource(async_client)
        out: list[dict[str, Any]] = []
        async for item in resource.iter_all_estadisticas():
            out.append(item)
        assert out == []

    async def test_iter_all_forwards_filters(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/scomp", params={"desde": "2025-01-01", "limit": "100", "offset": "0"}
        ).mock(
            return_value=httpx.Response(
                200, json={"items": [], "total": 0, "limit": 100, "offset": 0}
            )
        )
        resource = AsyncSCOMPResource(async_client)
        out: list[dict[str, Any]] = []
        async for item in resource.iter_all_estadisticas(desde="2025-01-01"):
            out.append(item)
        assert out == []
        assert route.called
