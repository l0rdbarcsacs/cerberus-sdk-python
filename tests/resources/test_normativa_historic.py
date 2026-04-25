"""Tests for ``cerberus_compliance.resources.normativa_historic`` (P5.3)."""

from __future__ import annotations

import httpx
import pytest
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.errors import NotFoundError
from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource
from cerberus_compliance.resources.normativa_historic import (
    AsyncNormativaHistoricResource,
    NormativaHistoricResource,
)


class TestNormativaHistoricMeta:
    def test_sync_prefix(self) -> None:
        assert NormativaHistoricResource._path_prefix == "/normativa/historic"

    def test_async_prefix(self) -> None:
        assert AsyncNormativaHistoricResource._path_prefix == "/normativa/historic"

    def test_sync_subclass(self) -> None:
        assert issubclass(NormativaHistoricResource, BaseResource)

    def test_async_subclass(self) -> None:
        assert issubclass(AsyncNormativaHistoricResource, AsyncBaseResource)


class TestNormativaHistoricSync:
    def test_list(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        route = respx_mock.get("/normativa/historic").mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"id": "nh-001"}, {"id": "nh-002"}], "next": None},
            )
        )
        resource = NormativaHistoricResource(sync_client)
        result = resource.list()
        assert result == [{"id": "nh-001"}, {"id": "nh-002"}]
        assert route.called

    def test_list_drops_none_params(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/normativa/historic", params={"limit": "10"}).mock(
            return_value=httpx.Response(200, json={"data": [], "next": None})
        )
        resource = NormativaHistoricResource(sync_client)
        resource.list(limit=10, extra_none=None)
        assert route.called

    def test_get(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        respx_mock.get("/normativa/historic/nh-001").mock(
            return_value=httpx.Response(200, json={"id": "nh-001", "title": "test"})
        )
        resource = NormativaHistoricResource(sync_client)
        result = resource.get("nh-001")
        assert result["title"] == "test"

    def test_get_not_found(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/normativa/historic/nonexistent").mock(
            return_value=httpx.Response(404, json={"title": "Not Found", "status": 404})
        )
        resource = NormativaHistoricResource(sync_client)
        with pytest.raises(NotFoundError):
            resource.get("nonexistent")

    def test_get_percent_encodes_id(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/normativa/historic/..%2Fadmin").mock(
            return_value=httpx.Response(404, json={"title": "Not Found", "status": 404})
        )
        resource = NormativaHistoricResource(sync_client)
        with pytest.raises(NotFoundError):
            resource.get("../admin")
        assert route.called

    def test_iter_all_paginates(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/normativa/historic", params={"cursor": "c2"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": 2}], "next": None})
        )
        respx_mock.get("/normativa/historic", params={}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": 1}], "next": "c2"})
        )
        resource = NormativaHistoricResource(sync_client)
        assert list(resource.iter_all()) == [{"id": 1}, {"id": 2}]


class TestNormativaHistoricAsync:
    async def test_list(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/normativa/historic").mock(
            return_value=httpx.Response(200, json={"data": [{"id": "x"}], "next": None})
        )
        resource = AsyncNormativaHistoricResource(async_client)
        assert await resource.list() == [{"id": "x"}]

    async def test_get(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/normativa/historic/nh-001").mock(
            return_value=httpx.Response(200, json={"id": "nh-001"})
        )
        resource = AsyncNormativaHistoricResource(async_client)
        assert await resource.get("nh-001") == {"id": "nh-001"}

    async def test_iter_all_paginates(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/normativa/historic", params={"cursor": "c2"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": 2}], "next": None})
        )
        respx_mock.get("/normativa/historic", params={}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": 1}], "next": "c2"})
        )
        resource = AsyncNormativaHistoricResource(async_client)
        collected = []
        async for item in resource.iter_all():
            collected.append(item)
        assert collected == [{"id": 1}, {"id": 2}]
