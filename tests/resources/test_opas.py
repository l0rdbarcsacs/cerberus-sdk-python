"""Tests for ``cerberus_compliance.resources.opas`` (P5.3)."""

from __future__ import annotations

import httpx
import pytest
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.errors import NotFoundError
from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource
from cerberus_compliance.resources.opas import (
    AsyncOPAsResource,
    OPAsResource,
)


class TestOPAMeta:
    def test_sync_prefix(self) -> None:
        assert OPAsResource._path_prefix == "/opas"

    def test_async_prefix(self) -> None:
        assert AsyncOPAsResource._path_prefix == "/opas"

    def test_sync_subclass(self) -> None:
        assert issubclass(OPAsResource, BaseResource)

    def test_async_subclass(self) -> None:
        assert issubclass(AsyncOPAsResource, AsyncBaseResource)


class TestOPASync:
    def test_list(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        route = respx_mock.get("/opas").mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"id": "opa-001"}, {"id": "opa-002"}], "next": None},
            )
        )
        resource = OPAsResource(sync_client)
        result = resource.list()
        assert result == [{"id": "opa-001"}, {"id": "opa-002"}]
        assert route.called

    def test_list_drops_none_params(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/opas", params={"limit": "10"}).mock(
            return_value=httpx.Response(200, json={"data": [], "next": None})
        )
        resource = OPAsResource(sync_client)
        resource.list(limit=10, extra_none=None)
        assert route.called

    def test_get(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        respx_mock.get("/opas/opa-001").mock(
            return_value=httpx.Response(200, json={"id": "opa-001", "title": "test"})
        )
        resource = OPAsResource(sync_client)
        result = resource.get("opa-001")
        assert result["title"] == "test"

    def test_get_not_found(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        respx_mock.get("/opas/nonexistent").mock(
            return_value=httpx.Response(404, json={"title": "Not Found", "status": 404})
        )
        resource = OPAsResource(sync_client)
        with pytest.raises(NotFoundError):
            resource.get("nonexistent")

    def test_get_percent_encodes_id(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/opas/..%2Fadmin").mock(
            return_value=httpx.Response(404, json={"title": "Not Found", "status": 404})
        )
        resource = OPAsResource(sync_client)
        with pytest.raises(NotFoundError):
            resource.get("../admin")
        assert route.called

    def test_iter_all_paginates(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/opas", params={"cursor": "c2"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": 2}], "next": None})
        )
        respx_mock.get("/opas", params={}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": 1}], "next": "c2"})
        )
        resource = OPAsResource(sync_client)
        assert list(resource.iter_all()) == [{"id": 1}, {"id": 2}]


class TestOPAAsync:
    async def test_list(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/opas").mock(
            return_value=httpx.Response(200, json={"data": [{"id": "x"}], "next": None})
        )
        resource = AsyncOPAsResource(async_client)
        assert await resource.list() == [{"id": "x"}]

    async def test_get(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/opas/opa-001").mock(
            return_value=httpx.Response(200, json={"id": "opa-001"})
        )
        resource = AsyncOPAsResource(async_client)
        assert await resource.get("opa-001") == {"id": "opa-001"}

    async def test_iter_all_paginates(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/opas", params={"cursor": "c2"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": 2}], "next": None})
        )
        respx_mock.get("/opas", params={}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": 1}], "next": "c2"})
        )
        resource = AsyncOPAsResource(async_client)
        collected = []
        async for item in resource.iter_all():
            collected.append(item)
        assert collected == [{"id": 1}, {"id": 2}]
