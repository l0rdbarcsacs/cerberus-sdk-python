"""Tests for ``cerberus_compliance.resources.art12`` (P5.3)."""

from __future__ import annotations

import httpx
import pytest
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.errors import NotFoundError
from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource
from cerberus_compliance.resources.art12 import (
    Art12Resource,
    AsyncArt12Resource,
)


class TestArt12Meta:
    def test_sync_prefix(self) -> None:
        assert Art12Resource._path_prefix == "/art12"

    def test_async_prefix(self) -> None:
        assert AsyncArt12Resource._path_prefix == "/art12"

    def test_sync_subclass(self) -> None:
        assert issubclass(Art12Resource, BaseResource)

    def test_async_subclass(self) -> None:
        assert issubclass(AsyncArt12Resource, AsyncBaseResource)


class TestArt12Sync:
    def test_list(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        route = respx_mock.get("/art12").mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"id": "art12-001"}, {"id": "art12-002"}], "next": None},
            )
        )
        resource = Art12Resource(sync_client)
        result = resource.list()
        assert result == [{"id": "art12-001"}, {"id": "art12-002"}]
        assert route.called

    def test_list_drops_none_params(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/art12", params={"limit": "10"}).mock(
            return_value=httpx.Response(200, json={"data": [], "next": None})
        )
        resource = Art12Resource(sync_client)
        resource.list(limit=10, extra_none=None)
        assert route.called

    def test_get(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        respx_mock.get("/art12/art12-001").mock(
            return_value=httpx.Response(200, json={"id": "art12-001", "title": "test"})
        )
        resource = Art12Resource(sync_client)
        result = resource.get("art12-001")
        assert result["title"] == "test"

    def test_get_not_found(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/art12/nonexistent").mock(
            return_value=httpx.Response(404, json={"title": "Not Found", "status": 404})
        )
        resource = Art12Resource(sync_client)
        with pytest.raises(NotFoundError):
            resource.get("nonexistent")

    def test_get_percent_encodes_id(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/art12/..%2Fadmin").mock(
            return_value=httpx.Response(404, json={"title": "Not Found", "status": 404})
        )
        resource = Art12Resource(sync_client)
        with pytest.raises(NotFoundError):
            resource.get("../admin")
        assert route.called

    def test_iter_all_paginates(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/art12", params={"cursor": "c2"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": 2}], "next": None})
        )
        respx_mock.get("/art12", params={}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": 1}], "next": "c2"})
        )
        resource = Art12Resource(sync_client)
        assert list(resource.iter_all()) == [{"id": 1}, {"id": 2}]


class TestArt12Async:
    async def test_list(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/art12").mock(
            return_value=httpx.Response(200, json={"data": [{"id": "x"}], "next": None})
        )
        resource = AsyncArt12Resource(async_client)
        assert await resource.list() == [{"id": "x"}]

    async def test_get(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/art12/art12-001").mock(
            return_value=httpx.Response(200, json={"id": "art12-001"})
        )
        resource = AsyncArt12Resource(async_client)
        assert await resource.get("art12-001") == {"id": "art12-001"}

    async def test_iter_all_paginates(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/art12", params={"cursor": "c2"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": 2}], "next": None})
        )
        respx_mock.get("/art12", params={}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": 1}], "next": "c2"})
        )
        resource = AsyncArt12Resource(async_client)
        collected = []
        async for item in resource.iter_all():
            collected.append(item)
        assert collected == [{"id": 1}, {"id": 2}]
