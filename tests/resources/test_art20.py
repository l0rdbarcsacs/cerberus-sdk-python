"""Tests for ``cerberus_compliance.resources.art20`` (P5.3)."""

from __future__ import annotations

import httpx
import pytest
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource
from cerberus_compliance.resources.art20 import (
    Art20Resource,
    AsyncArt20Resource,
)


class TestArt20Meta:
    def test_sync_prefix(self) -> None:
        assert Art20Resource._path_prefix == "/art20"

    def test_async_prefix(self) -> None:
        assert AsyncArt20Resource._path_prefix == "/art20"

    def test_sync_subclass(self) -> None:
        assert issubclass(Art20Resource, BaseResource)

    def test_async_subclass(self) -> None:
        assert issubclass(AsyncArt20Resource, AsyncBaseResource)


class TestArt20Sync:
    def test_list(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        route = respx_mock.get("/art20").mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"id": "art20-001"}, {"id": "art20-002"}], "next": None},
            )
        )
        resource = Art20Resource(sync_client)
        result = resource.list()
        assert result == [{"id": "art20-001"}, {"id": "art20-002"}]
        assert route.called

    def test_list_drops_none_params(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/art20", params={"limit": "10"}).mock(
            return_value=httpx.Response(200, json={"data": [], "next": None})
        )
        resource = Art20Resource(sync_client)
        resource.list(limit=10, extra_none=None)
        assert route.called

    def test_get_raises_not_implemented(self, sync_client: CerberusClient) -> None:
        resource = Art20Resource(sync_client)
        with pytest.raises(NotImplementedError, match="not a real API endpoint"):
            resource.get("a20-001")

    def test_iter_all_paginates(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/art20", params={"cursor": "c2"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": 2}], "next": None})
        )
        respx_mock.get("/art20", params={}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": 1}], "next": "c2"})
        )
        resource = Art20Resource(sync_client)
        assert list(resource.iter_all()) == [{"id": 1}, {"id": 2}]


class TestArt20Async:
    async def test_list(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/art20").mock(
            return_value=httpx.Response(200, json={"data": [{"id": "x"}], "next": None})
        )
        resource = AsyncArt20Resource(async_client)
        assert await resource.list() == [{"id": "x"}]

    async def test_get_raises_not_implemented(self, async_client: AsyncCerberusClient) -> None:
        resource = AsyncArt20Resource(async_client)
        with pytest.raises(NotImplementedError, match="not a real API endpoint"):
            await resource.get("a20-001")

    async def test_iter_all_paginates(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/art20", params={"cursor": "c2"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": 2}], "next": None})
        )
        respx_mock.get("/art20", params={}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": 1}], "next": "c2"})
        )
        resource = AsyncArt20Resource(async_client)
        collected = []
        async for item in resource.iter_all():
            collected.append(item)
        assert collected == [{"id": 1}, {"id": 2}]
