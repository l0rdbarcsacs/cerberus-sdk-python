"""Tests for ``cerberus_compliance.resources.dictamenes`` (P5.3)."""

from __future__ import annotations

import httpx
import pytest
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource
from cerberus_compliance.resources.dictamenes import (
    AsyncDictamenesResource,
    DictamenesResource,
)


class TestDictamenesMeta:
    def test_sync_prefix(self) -> None:
        assert DictamenesResource._path_prefix == "/dictamenes"

    def test_async_prefix(self) -> None:
        assert AsyncDictamenesResource._path_prefix == "/dictamenes"

    def test_sync_subclass(self) -> None:
        assert issubclass(DictamenesResource, BaseResource)

    def test_async_subclass(self) -> None:
        assert issubclass(AsyncDictamenesResource, AsyncBaseResource)


class TestDictamenesSync:
    def test_list(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        route = respx_mock.get("/dictamenes").mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"id": "dict-001"}, {"id": "dict-002"}], "next": None},
            )
        )
        resource = DictamenesResource(sync_client)
        result = resource.list()
        assert result == [{"id": "dict-001"}, {"id": "dict-002"}]
        assert route.called

    def test_list_drops_none_params(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/dictamenes", params={"limit": "10"}).mock(
            return_value=httpx.Response(200, json={"data": [], "next": None})
        )
        resource = DictamenesResource(sync_client)
        resource.list(limit=10, extra_none=None)
        assert route.called

    def test_get_raises_not_implemented(self, sync_client: CerberusClient) -> None:
        resource = DictamenesResource(sync_client)
        with pytest.raises(NotImplementedError, match="not a real API endpoint"):
            resource.get("d-001")

    def test_iter_all_paginates(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/dictamenes", params={"cursor": "c2"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": 2}], "next": None})
        )
        respx_mock.get("/dictamenes", params={}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": 1}], "next": "c2"})
        )
        resource = DictamenesResource(sync_client)
        assert list(resource.iter_all()) == [{"id": 1}, {"id": 2}]


class TestDictamenesAsync:
    async def test_list(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/dictamenes").mock(
            return_value=httpx.Response(200, json={"data": [{"id": "x"}], "next": None})
        )
        resource = AsyncDictamenesResource(async_client)
        assert await resource.list() == [{"id": "x"}]

    async def test_get_raises_not_implemented(self, async_client: AsyncCerberusClient) -> None:
        resource = AsyncDictamenesResource(async_client)
        with pytest.raises(NotImplementedError, match="not a real API endpoint"):
            await resource.get("d-001")

    async def test_iter_all_paginates(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/dictamenes", params={"cursor": "c2"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": 2}], "next": None})
        )
        respx_mock.get("/dictamenes", params={}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": 1}], "next": "c2"})
        )
        resource = AsyncDictamenesResource(async_client)
        collected = []
        async for item in resource.iter_all():
            collected.append(item)
        assert collected == [{"id": 1}, {"id": 2}]
