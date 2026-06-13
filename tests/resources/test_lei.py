"""Tests for ``cerberus_compliance.resources.lei`` (SDK-01).

``/v1/lei`` is the GLEIF Legal Entity Identifier registry. Unlike the
cursor-paginated collections, it paginates by ``limit``/``offset`` and returns
an ``{items, total, limit, offset}`` envelope, so :meth:`LeiResource.iter_all`
walks by offset (not cursor).
"""

from __future__ import annotations

import httpx
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource
from cerberus_compliance.resources.lei import AsyncLeiResource, LeiResource


class TestLeiMeta:
    def test_sync_prefix(self) -> None:
        assert LeiResource._path_prefix == "/lei"

    def test_async_prefix(self) -> None:
        assert AsyncLeiResource._path_prefix == "/lei"

    def test_sync_subclass(self) -> None:
        assert issubclass(LeiResource, BaseResource)

    def test_async_subclass(self) -> None:
        assert issubclass(AsyncLeiResource, AsyncBaseResource)


class TestLeiSync:
    def test_list(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        route = respx_mock.get("/lei").mock(
            return_value=httpx.Response(
                200,
                json={
                    "items": [{"lei": "5493001KJTIIGC8Y1R12"}, {"lei": "529900T8BM49AURSDO55"}],
                    "total": 2,
                    "limit": 20,
                    "offset": 0,
                },
            )
        )
        result = LeiResource(sync_client).list()
        assert [r["lei"] for r in result] == ["5493001KJTIIGC8Y1R12", "529900T8BM49AURSDO55"]
        assert route.called

    def test_list_typed_filters_drop_none(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/lei", params={"jurisdiction": "CL", "registration_status": "ISSUED"}
        ).mock(return_value=httpx.Response(200, json={"items": [], "total": 0}))
        LeiResource(sync_client).list(jurisdiction="CL", registration_status="ISSUED", rut=None)
        assert route.called

    def test_get(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        route = respx_mock.get("/lei/5493001KJTIIGC8Y1R12").mock(
            return_value=httpx.Response(
                200, json={"lei": "5493001KJTIIGC8Y1R12", "legal_name": "X"}
            )
        )
        out = LeiResource(sync_client).get("5493001KJTIIGC8Y1R12")
        assert out["legal_name"] == "X"
        assert route.called

    def test_iter_all_paginates_by_offset(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/lei", params={"limit": "2", "offset": "0"}).mock(
            return_value=httpx.Response(
                200, json={"items": [{"lei": "A"}, {"lei": "B"}], "total": 3}
            )
        )
        respx_mock.get("/lei", params={"limit": "2", "offset": "2"}).mock(
            return_value=httpx.Response(200, json={"items": [{"lei": "C"}], "total": 3})
        )
        out = list(LeiResource(sync_client).iter_all(page_size=2))
        assert [r["lei"] for r in out] == ["A", "B", "C"]


class TestLeiAsync:
    async def test_list(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/lei").mock(
            return_value=httpx.Response(200, json={"items": [{"lei": "Z"}], "total": 1})
        )
        assert await AsyncLeiResource(async_client).list() == [{"lei": "Z"}]

    async def test_get(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/lei/ABC").mock(
            return_value=httpx.Response(200, json={"lei": "ABC", "legal_name": "Y"})
        )
        out = await AsyncLeiResource(async_client).get("ABC")
        assert out["legal_name"] == "Y"

    async def test_iter_all_paginates_by_offset(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/lei", params={"limit": "2", "offset": "0"}).mock(
            return_value=httpx.Response(
                200, json={"items": [{"lei": "A"}, {"lei": "B"}], "total": 3}
            )
        )
        respx_mock.get("/lei", params={"limit": "2", "offset": "2"}).mock(
            return_value=httpx.Response(200, json={"items": [{"lei": "C"}], "total": 3})
        )
        collected = [r["lei"] async for r in AsyncLeiResource(async_client).iter_all(page_size=2)]
        assert collected == ["A", "B", "C"]
