"""Tests for ``cerberus_compliance.resources.banking``."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.errors import CerberusAPIError
from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource
from cerberus_compliance.resources.banking import (
    AsyncBankingResource,
    BankingResource,
)

# ---------------------------------------------------------------------------
# Static structural tests
# ---------------------------------------------------------------------------


class TestBankingMeta:
    def test_sync_prefix(self) -> None:
        assert BankingResource._path_prefix == "/banking/indicadores"

    def test_async_prefix(self) -> None:
        assert AsyncBankingResource._path_prefix == "/banking/indicadores"

    def test_sync_subclass(self) -> None:
        assert issubclass(BankingResource, BaseResource)

    def test_async_subclass(self) -> None:
        assert issubclass(AsyncBankingResource, AsyncBaseResource)


# ---------------------------------------------------------------------------
# Sync behaviour
# ---------------------------------------------------------------------------


class TestBankingSync:
    def test_list_no_filters(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        body = {
            "items": [
                {
                    "id": "11111111-1111-1111-1111-111111111111",
                    "banco_codigo": "001",
                    "banco_nombre": "Banco de Chile",
                    "periodo": "2026-05",
                    "indicador_tipo": "patrimonio_efectivo.total",
                    "valor": "12345.67",
                    "created_at": "2026-06-01T00:00:00Z",
                }
            ],
            "total": 1,
            "limit": 20,
            "offset": 0,
        }
        route = respx_mock.get("/banking/indicadores").mock(
            return_value=httpx.Response(200, json=body)
        )
        resource = BankingResource(sync_client)
        result = resource.list_indicadores()
        assert result == body
        assert route.called
        assert route.calls.last.request.url.query == b""

    def test_list_with_banco_and_tipo(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/banking/indicadores",
            params={"banco": "001", "tipo": "patrimonio_efectivo.total"},
        ).mock(
            return_value=httpx.Response(
                200, json={"items": [], "total": 0, "limit": 20, "offset": 0}
            )
        )
        resource = BankingResource(sync_client)
        result = resource.list_indicadores(banco="001", tipo="patrimonio_efectivo.total")
        assert result == {"items": [], "total": 0, "limit": 20, "offset": 0}
        assert route.called

    def test_list_with_period_window_and_q(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/banking/indicadores",
            params={"desde": "2026-01", "hasta": "2026-05", "q": "chile"},
        ).mock(
            return_value=httpx.Response(
                200, json={"items": [], "total": 0, "limit": 20, "offset": 0}
            )
        )
        resource = BankingResource(sync_client)
        resource.list_indicadores(desde="2026-01", hasta="2026-05", q="chile")
        assert route.called

    def test_list_with_limit_and_offset(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/banking/indicadores", params={"limit": "50", "offset": "10"}).mock(
            return_value=httpx.Response(
                200, json={"items": [], "total": 0, "limit": 50, "offset": 10}
            )
        )
        resource = BankingResource(sync_client)
        resource.list_indicadores(limit=50, offset=10)
        assert route.called

    def test_list_drops_none(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/banking/indicadores").mock(
            return_value=httpx.Response(
                200, json={"items": [], "total": 0, "limit": 20, "offset": 0}
            )
        )
        resource = BankingResource(sync_client)
        resource.list_indicadores(
            banco=None, tipo=None, desde=None, hasta=None, q=None, limit=None, offset=None
        )
        assert route.called
        assert route.calls.last.request.url.query == b""

    def test_list_empty_q_is_forwarded(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        # An empty-string ``q`` is *not* None, so it must be sent (the server
        # decides to ignore it); only ``None`` is dropped client-side.
        route = respx_mock.get("/banking/indicadores", params={"q": ""}).mock(
            return_value=httpx.Response(
                200, json={"items": [], "total": 0, "limit": 20, "offset": 0}
            )
        )
        resource = BankingResource(sync_client)
        resource.list_indicadores(q="")
        assert route.called
        assert b"q=" in route.calls.last.request.url.query

    def test_iter_all_single_page(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        # Fewer items than the SDK page size (100) — stops after one request.
        route = respx_mock.get("/banking/indicadores", params={"limit": "100", "offset": "0"}).mock(
            return_value=httpx.Response(
                200,
                json={
                    "items": [{"id": "a"}, {"id": "b"}],
                    "total": 2,
                    "limit": 100,
                    "offset": 0,
                },
            )
        )
        resource = BankingResource(sync_client)
        items = list(resource.iter_all_indicadores())
        assert items == [{"id": "a"}, {"id": "b"}]
        assert route.call_count == 1

    def test_iter_all_multi_page(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        page1 = [{"id": f"r{i:03d}"} for i in range(100)]
        respx_mock.get("/banking/indicadores", params={"limit": "100", "offset": "0"}).mock(
            return_value=httpx.Response(
                200, json={"items": page1, "total": 101, "limit": 100, "offset": 0}
            )
        )
        respx_mock.get("/banking/indicadores", params={"limit": "100", "offset": "100"}).mock(
            return_value=httpx.Response(
                200,
                json={"items": [{"id": "TAIL"}], "total": 101, "limit": 100, "offset": 100},
            )
        )
        resource = BankingResource(sync_client)
        items = list(resource.iter_all_indicadores())
        assert len(items) == 101
        assert items[-1] == {"id": "TAIL"}

    def test_iter_all_full_page_then_empty(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        # Exactly one full page, then an empty page that terminates iteration.
        page1 = [{"id": f"r{i:03d}"} for i in range(100)]
        respx_mock.get("/banking/indicadores", params={"limit": "100", "offset": "0"}).mock(
            return_value=httpx.Response(
                200, json={"items": page1, "total": 100, "limit": 100, "offset": 0}
            )
        )
        empty = respx_mock.get(
            "/banking/indicadores", params={"limit": "100", "offset": "100"}
        ).mock(
            return_value=httpx.Response(
                200, json={"items": [], "total": 100, "limit": 100, "offset": 100}
            )
        )
        resource = BankingResource(sync_client)
        items = list(resource.iter_all_indicadores())
        assert len(items) == 100
        assert empty.called

    def test_iter_all_forwards_filters(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/banking/indicadores",
            params={
                "banco": "001",
                "tipo": "patrimonio_efectivo.total",
                "desde": "2025-01",
                "hasta": "2026-05",
                "q": "chile",
                "limit": "100",
                "offset": "0",
            },
        ).mock(
            return_value=httpx.Response(
                200, json={"items": [], "total": 0, "limit": 100, "offset": 0}
            )
        )
        resource = BankingResource(sync_client)
        assert (
            list(
                resource.iter_all_indicadores(
                    banco="001",
                    tipo="patrimonio_efectivo.total",
                    desde="2025-01",
                    hasta="2026-05",
                    q="chile",
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
        respx_mock.get("/banking/indicadores").mock(
            return_value=httpx.Response(500, json=problem_json(status=500, title="Server Error"))
        )
        resource = BankingResource(sync_client)
        with pytest.raises(CerberusAPIError):
            resource.list_indicadores()


# ---------------------------------------------------------------------------
# Async behaviour
# ---------------------------------------------------------------------------


class TestBankingAsync:
    async def test_list_no_filters(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        body = {
            "items": [{"id": "x", "banco_codigo": "001", "valor": "1.0"}],
            "total": 1,
            "limit": 20,
            "offset": 0,
        }
        route = respx_mock.get("/banking/indicadores").mock(
            return_value=httpx.Response(200, json=body)
        )
        resource = AsyncBankingResource(async_client)
        assert await resource.list_indicadores() == body
        assert route.called

    async def test_list_with_banco(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/banking/indicadores", params={"banco": "002"}).mock(
            return_value=httpx.Response(
                200, json={"items": [], "total": 0, "limit": 20, "offset": 0}
            )
        )
        resource = AsyncBankingResource(async_client)
        await resource.list_indicadores(banco="002")
        assert route.called

    async def test_iter_all_multi_page(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        page1 = [{"id": f"x{i:03d}"} for i in range(100)]
        respx_mock.get("/banking/indicadores", params={"limit": "100", "offset": "0"}).mock(
            return_value=httpx.Response(
                200, json={"items": page1, "total": 101, "limit": 100, "offset": 0}
            )
        )
        respx_mock.get("/banking/indicadores", params={"limit": "100", "offset": "100"}).mock(
            return_value=httpx.Response(
                200,
                json={"items": [{"id": "LAST"}], "total": 101, "limit": 100, "offset": 100},
            )
        )
        resource = AsyncBankingResource(async_client)
        out: list[dict[str, Any]] = []
        async for item in resource.iter_all_indicadores():
            out.append(item)
        assert len(out) == 101
        assert out[-1] == {"id": "LAST"}

    async def test_iter_all_empty_page_stops(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/banking/indicadores", params={"limit": "100", "offset": "0"}).mock(
            return_value=httpx.Response(
                200, json={"items": [], "total": 0, "limit": 100, "offset": 0}
            )
        )
        resource = AsyncBankingResource(async_client)
        out: list[dict[str, Any]] = []
        async for item in resource.iter_all_indicadores():
            out.append(item)
        assert out == []

    async def test_iter_all_forwards_tipo(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/banking/indicadores",
            params={"tipo": "indicadores_liquidez.lcr", "limit": "100", "offset": "0"},
        ).mock(
            return_value=httpx.Response(
                200, json={"items": [], "total": 0, "limit": 100, "offset": 0}
            )
        )
        resource = AsyncBankingResource(async_client)
        out: list[dict[str, Any]] = []
        async for item in resource.iter_all_indicadores(tipo="indicadores_liquidez.lcr"):
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
        async def _no_sleep(_s: float) -> None:
            return None

        monkeypatch.setattr("asyncio.sleep", _no_sleep)
        respx_mock.get("/banking/indicadores").mock(
            return_value=httpx.Response(500, json=problem_json(status=500, title="Server Error"))
        )
        resource = AsyncBankingResource(async_client)
        with pytest.raises(CerberusAPIError):
            await resource.list_indicadores()
