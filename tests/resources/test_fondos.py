"""Tests for ``cerberus_compliance.resources.fondos`` (CMF BPR fondos mutuos)."""

from __future__ import annotations

import httpx
import pytest
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.errors import CerberusAPIError, NotFoundError
from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource
from cerberus_compliance.resources.fondos import AsyncFondosResource, FondosResource

# A representative FundMetrics row; decimals arrive as strings (parse as Decimal).
_FUND_ROW = {
    "run": "9022-0",
    "nombre": "Fondo Mutuo X",
    "serie": "A",
    "periodo": "2024-03",
    "periodicidad": "mensual",
    "moneda": "CLP",
    "patrimonio": "123456789.12",
    "rentabilidad": "0.0345",
    "n_participes": 4210,
    "valor_cuota": "1234.5678",
}


class TestFondosMeta:
    def test_sync_prefix(self) -> None:
        assert FondosResource._path_prefix == "/fondos"

    def test_async_prefix(self) -> None:
        assert AsyncFondosResource._path_prefix == "/fondos"

    def test_sync_subclass(self) -> None:
        assert issubclass(FondosResource, BaseResource)

    def test_async_subclass(self) -> None:
        assert issubclass(AsyncFondosResource, AsyncBaseResource)


class TestFondosListSync:
    def test_list_no_params(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/fondos").mock(
            return_value=httpx.Response(
                200,
                json={
                    "items": [_FUND_ROW],
                    "next_cursor": None,
                    "prev_cursor": None,
                    "limit": 50,
                },
            )
        )
        resource = FondosResource(sync_client)
        result = resource.list()
        assert len(result) == 1
        assert result[0]["run"] == "9022-0"
        assert result[0]["patrimonio"] == "123456789.12"
        assert route.called
        # No params set -> empty query string.
        assert route.calls.last.request.url.params.multi_items() == []

    def test_list_forwards_all_params(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/fondos").mock(
            return_value=httpx.Response(
                200,
                json={"items": [], "next_cursor": None, "prev_cursor": None, "limit": 25},
            )
        )
        resource = FondosResource(sync_client)
        resource.list(
            periodicidad="mensual",
            periodo="2024-03",
            cursor="opaque-cursor",
            limit=25,
        )
        params = dict(route.calls.last.request.url.params.multi_items())
        assert params == {
            "periodicidad": "mensual",
            "periodo": "2024-03",
            "cursor": "opaque-cursor",
            "limit": "25",
        }

    def test_list_drops_none_params(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/fondos", params={"periodicidad": "diaria"}).mock(
            return_value=httpx.Response(
                200,
                json={"items": [], "next_cursor": None, "prev_cursor": None, "limit": 50},
            )
        )
        resource = FondosResource(sync_client)
        resource.list(periodicidad="diaria", periodo=None, cursor=None, limit=None)
        assert route.called
        params = dict(route.calls.last.request.url.params.multi_items())
        assert params == {"periodicidad": "diaria"}

    def test_list_empty_page_on_invalid_periodicidad(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        # Invalid periodicidad => empty page (200), NOT 422.
        respx_mock.get("/fondos").mock(
            return_value=httpx.Response(
                200,
                json={"items": [], "next_cursor": None, "prev_cursor": None, "limit": 50},
            )
        )
        resource = FondosResource(sync_client)
        assert resource.list() == []

    def test_list_propagates_401(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/fondos").mock(
            return_value=httpx.Response(401, json={"title": "Unauthorized", "status": 401})
        )
        resource = FondosResource(sync_client)
        with pytest.raises(CerberusAPIError) as exc:
            resource.list()
        assert exc.value.status == 401

    def test_iter_all_paginates(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/fondos", params={"periodicidad": "mensual", "cursor": "c2"}).mock(
            return_value=httpx.Response(
                200,
                json={"items": [{"run": "r2"}], "next_cursor": None},
            )
        )
        respx_mock.get("/fondos", params={"periodicidad": "mensual"}).mock(
            return_value=httpx.Response(
                200,
                json={"items": [{"run": "r1"}], "next_cursor": "c2"},
            )
        )
        resource = FondosResource(sync_client)
        assert list(resource.iter_all(periodicidad="mensual")) == [
            {"run": "r1"},
            {"run": "r2"},
        ]


class TestFondosGetSync:
    def test_get_by_run(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        route = respx_mock.get("/fondos/9022-0").mock(
            return_value=httpx.Response(
                200,
                json={
                    "items": [_FUND_ROW],
                    "next_cursor": None,
                    "prev_cursor": None,
                    "limit": 50,
                },
            )
        )
        resource = FondosResource(sync_client)
        result = resource.get("9022-0")
        assert len(result) == 1
        assert result[0]["serie"] == "A"
        assert route.called
        assert route.calls.last.request.url.params.multi_items() == []

    def test_get_forwards_params(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/fondos/9022-0").mock(
            return_value=httpx.Response(
                200,
                json={"items": [], "next_cursor": None, "prev_cursor": None, "limit": 10},
            )
        )
        resource = FondosResource(sync_client)
        resource.get("9022-0", periodicidad="diaria", cursor="cur", limit=10)
        params = dict(route.calls.last.request.url.params.multi_items())
        assert params == {"periodicidad": "diaria", "cursor": "cur", "limit": "10"}

    def test_get_percent_encodes_run(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/fondos/..%2Fadmin").mock(
            return_value=httpx.Response(404, json={"title": "Not Found", "status": 404})
        )
        resource = FondosResource(sync_client)
        with pytest.raises(NotFoundError):
            resource.get("../admin")
        assert route.called

    def test_get_not_found(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        respx_mock.get("/fondos/0000-0").mock(
            return_value=httpx.Response(404, json={"title": "Not Found", "status": 404})
        )
        resource = FondosResource(sync_client)
        with pytest.raises(NotFoundError):
            resource.get("0000-0")


class TestFondosListAsync:
    async def test_list(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/fondos").mock(
            return_value=httpx.Response(
                200,
                json={"items": [_FUND_ROW], "next_cursor": None, "prev_cursor": None, "limit": 50},
            )
        )
        resource = AsyncFondosResource(async_client)
        result = await resource.list(periodicidad="mensual", periodo="2024-03", limit=50)
        assert result[0]["run"] == "9022-0"
        params = dict(route.calls.last.request.url.params.multi_items())
        assert params == {"periodicidad": "mensual", "periodo": "2024-03", "limit": "50"}

    async def test_iter_all_paginates(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/fondos", params={"cursor": "c2"}).mock(
            return_value=httpx.Response(200, json={"items": [{"run": "r2"}], "next_cursor": None})
        )
        respx_mock.get("/fondos", params={}).mock(
            return_value=httpx.Response(200, json={"items": [{"run": "r1"}], "next_cursor": "c2"})
        )
        resource = AsyncFondosResource(async_client)
        collected = []
        async for item in resource.iter_all():
            collected.append(item)
        assert collected == [{"run": "r1"}, {"run": "r2"}]


class TestFondosGetAsync:
    async def test_get(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/fondos/9022-0").mock(
            return_value=httpx.Response(
                200,
                json={"items": [_FUND_ROW], "next_cursor": None, "prev_cursor": None, "limit": 50},
            )
        )
        resource = AsyncFondosResource(async_client)
        result = await resource.get("9022-0", limit=50)
        assert result[0]["valor_cuota"] == "1234.5678"
        params = dict(route.calls.last.request.url.params.multi_items())
        assert params == {"limit": "50"}

    async def test_get_not_found(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/fondos/0000-0").mock(
            return_value=httpx.Response(404, json={"title": "Not Found", "status": 404})
        )
        resource = AsyncFondosResource(async_client)
        with pytest.raises(NotFoundError):
            await resource.get("0000-0")
