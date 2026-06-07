"""Tests for ``cerberus_compliance.resources.sii``."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.errors import CerberusAPIError
from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource
from cerberus_compliance.resources.sii import (
    AsyncSIIResource,
    SIIResource,
)

# ---------------------------------------------------------------------------
# Static structural tests
# ---------------------------------------------------------------------------


class TestSIIMeta:
    def test_sync_prefix(self) -> None:
        assert SIIResource._path_prefix == "/sii"

    def test_async_prefix(self) -> None:
        assert AsyncSIIResource._path_prefix == "/sii"

    def test_sync_subclass(self) -> None:
        assert issubclass(SIIResource, BaseResource)

    def test_async_subclass(self) -> None:
        assert issubclass(AsyncSIIResource, AsyncBaseResource)


# ---------------------------------------------------------------------------
# Sync behaviour
# ---------------------------------------------------------------------------


class TestSIISync:
    def test_list_no_filters(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        body = {
            "items": [
                {"rut": "76.123.456-0", "razon_social": "ACME SPA", "estado": "vigente"},
                {"rut": "77.000.111-2", "razon_social": "BETA LTDA", "estado": "terminado"},
            ],
            "total": 10000,
            "limit": 20,
            "offset": 0,
        }
        route = respx_mock.get("/sii").mock(return_value=httpx.Response(200, json=body))
        resource = SIIResource(sync_client)
        result = resource.list()
        assert result == body
        assert route.called
        assert route.calls.last.request.url.query == b""

    def test_list_with_rut(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        body = {
            "items": [{"rut": "76.123.456-0", "razon_social": "ACME SPA", "estado": "vigente"}],
            "total": 1,
            "limit": 20,
            "offset": 0,
        }
        route = respx_mock.get("/sii", params={"rut": "76123456-0"}).mock(
            return_value=httpx.Response(200, json=body)
        )
        resource = SIIResource(sync_client)
        result = resource.list(rut="76123456-0")
        assert result == body
        assert route.called

    def test_list_with_q(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        route = respx_mock.get("/sii", params={"q": "banco"}).mock(
            return_value=httpx.Response(
                200, json={"items": [], "total": 0, "limit": 20, "offset": 0}
            )
        )
        resource = SIIResource(sync_client)
        result = resource.list(q="banco")
        assert result == {"items": [], "total": 0, "limit": 20, "offset": 0}
        assert route.called

    def test_list_with_estado(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/sii", params={"estado": "vigente"}).mock(
            return_value=httpx.Response(
                200, json={"items": [], "total": 0, "limit": 20, "offset": 0}
            )
        )
        resource = SIIResource(sync_client)
        resource.list(estado="vigente")
        assert route.called

    def test_list_with_limit_and_offset(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/sii", params={"limit": "5", "offset": "10"}).mock(
            return_value=httpx.Response(
                200, json={"items": [], "total": 0, "limit": 5, "offset": 10}
            )
        )
        resource = SIIResource(sync_client)
        resource.list(limit=5, offset=10)
        assert route.called

    def test_list_all_filters(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/sii",
            params={
                "rut": "76123456-0",
                "q": "acme",
                "estado": "vigente",
                "limit": "50",
                "offset": "0",
            },
        ).mock(
            return_value=httpx.Response(
                200, json={"items": [], "total": 0, "limit": 50, "offset": 0}
            )
        )
        resource = SIIResource(sync_client)
        resource.list(rut="76123456-0", q="acme", estado="vigente", limit=50, offset=0)
        assert route.called

    def test_list_drops_none(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/sii").mock(
            return_value=httpx.Response(
                200, json={"items": [], "total": 0, "limit": 20, "offset": 0}
            )
        )
        resource = SIIResource(sync_client)
        resource.list(rut=None, q=None, estado=None, limit=None, offset=None)
        assert route.called
        assert route.calls.last.request.url.query == b""

    def test_iter_all_single_page(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        # One page, fewer items than the SDK's page size (100) — must stop
        # after the first request without issuing a second.
        route = respx_mock.get("/sii", params={"limit": "100", "offset": "0"}).mock(
            return_value=httpx.Response(
                200,
                json={
                    "items": [{"rut": "1-9"}, {"rut": "2-7"}],
                    "total": 2,
                    "limit": 100,
                    "offset": 0,
                },
            )
        )
        resource = SIIResource(sync_client)
        items = list(resource.iter_all())
        assert items == [{"rut": "1-9"}, {"rut": "2-7"}]
        assert route.call_count == 1

    def test_iter_all_multi_page(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        # Two pages: a full first page, partial second page; iter_all
        # must walk both before stopping.
        page1_items = [{"rut": f"{i}-K"} for i in range(100)]
        respx_mock.get("/sii", params={"limit": "100", "offset": "0"}).mock(
            return_value=httpx.Response(
                200, json={"items": page1_items, "total": 101, "limit": 100, "offset": 0}
            )
        )
        respx_mock.get("/sii", params={"limit": "100", "offset": "100"}).mock(
            return_value=httpx.Response(
                200,
                json={"items": [{"rut": "TAIL"}], "total": 101, "limit": 100, "offset": 100},
            )
        )
        resource = SIIResource(sync_client)
        items = list(resource.iter_all())
        assert len(items) == 101
        assert items[-1] == {"rut": "TAIL"}

    def test_iter_all_empty_first_page(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/sii", params={"limit": "100", "offset": "0"}).mock(
            return_value=httpx.Response(
                200, json={"items": [], "total": 0, "limit": 100, "offset": 0}
            )
        )
        resource = SIIResource(sync_client)
        assert list(resource.iter_all()) == []
        assert route.call_count == 1

    def test_iter_all_forwards_filters(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/sii",
            params={
                "rut": "76123456-0",
                "q": "acme",
                "estado": "vigente",
                "limit": "100",
                "offset": "0",
            },
        ).mock(
            return_value=httpx.Response(
                200, json={"items": [], "total": 0, "limit": 100, "offset": 0}
            )
        )
        resource = SIIResource(sync_client)
        assert list(resource.iter_all(rut="76123456-0", q="acme", estado="vigente")) == []
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
        respx_mock.get("/sii").mock(
            return_value=httpx.Response(500, json=problem_json(status=500, title="Server Error"))
        )
        resource = SIIResource(sync_client)
        with pytest.raises(CerberusAPIError):
            resource.list()


# ---------------------------------------------------------------------------
# Async behaviour
# ---------------------------------------------------------------------------


class TestSIIAsync:
    async def test_list_no_filters(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        body = {
            "items": [{"rut": "76.123.456-0", "razon_social": "ACME SPA", "estado": "vigente"}],
            "total": 1,
            "limit": 20,
            "offset": 0,
        }
        route = respx_mock.get("/sii").mock(return_value=httpx.Response(200, json=body))
        resource = AsyncSIIResource(async_client)
        assert await resource.list() == body
        assert route.called
        assert route.calls.last.request.url.query == b""

    async def test_list_with_q(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/sii", params={"q": "banco"}).mock(
            return_value=httpx.Response(
                200, json={"items": [], "total": 0, "limit": 20, "offset": 0}
            )
        )
        resource = AsyncSIIResource(async_client)
        await resource.list(q="banco")
        assert route.called

    async def test_list_all_filters(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/sii",
            params={
                "rut": "76123456-0",
                "q": "acme",
                "estado": "vigente",
                "limit": "50",
                "offset": "10",
            },
        ).mock(
            return_value=httpx.Response(
                200, json={"items": [], "total": 0, "limit": 50, "offset": 10}
            )
        )
        resource = AsyncSIIResource(async_client)
        await resource.list(rut="76123456-0", q="acme", estado="vigente", limit=50, offset=10)
        assert route.called

    async def test_iter_all_multi_page(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        page1 = [{"rut": f"X{i:03d}"} for i in range(100)]
        respx_mock.get("/sii", params={"limit": "100", "offset": "0"}).mock(
            return_value=httpx.Response(
                200, json={"items": page1, "total": 101, "limit": 100, "offset": 0}
            )
        )
        respx_mock.get("/sii", params={"limit": "100", "offset": "100"}).mock(
            return_value=httpx.Response(
                200,
                json={"items": [{"rut": "LAST"}], "total": 101, "limit": 100, "offset": 100},
            )
        )
        resource = AsyncSIIResource(async_client)
        out: list[dict[str, Any]] = []
        async for item in resource.iter_all():
            out.append(item)
        assert len(out) == 101
        assert out[-1] == {"rut": "LAST"}

    async def test_iter_all_empty_page_stops(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/sii", params={"limit": "100", "offset": "0"}).mock(
            return_value=httpx.Response(
                200, json={"items": [], "total": 0, "limit": 100, "offset": 0}
            )
        )
        resource = AsyncSIIResource(async_client)
        out: list[dict[str, Any]] = []
        async for item in resource.iter_all(estado="vigente"):
            out.append(item)
        assert out == []

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
        respx_mock.get("/sii").mock(
            return_value=httpx.Response(500, json=problem_json(status=500, title="Server Error"))
        )
        resource = AsyncSIIResource(async_client)
        with pytest.raises(CerberusAPIError):
            await resource.list()
