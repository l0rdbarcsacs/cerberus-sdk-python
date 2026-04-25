"""Tests for ``cerberus_compliance.resources.comunicaciones`` (P5.3)."""

from __future__ import annotations

import httpx
import pytest
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.errors import NotFoundError
from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource
from cerberus_compliance.resources.comunicaciones import (
    AsyncComunicacionesResource,
    ComunicacionesResource,
)


class TestComunicacionesMeta:
    def test_sync_prefix(self) -> None:
        assert ComunicacionesResource._path_prefix == "/comunicaciones"

    def test_async_prefix(self) -> None:
        assert AsyncComunicacionesResource._path_prefix == "/comunicaciones"

    def test_sync_subclass(self) -> None:
        assert issubclass(ComunicacionesResource, BaseResource)

    def test_async_subclass(self) -> None:
        assert issubclass(AsyncComunicacionesResource, AsyncBaseResource)


class TestComunicacionesSync:
    def test_list(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        route = respx_mock.get("/comunicaciones").mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"id": "com-001"}, {"id": "com-002"}], "next": None},
            )
        )
        resource = ComunicacionesResource(sync_client)
        result = resource.list()
        assert result == [{"id": "com-001"}, {"id": "com-002"}]
        assert route.called

    def test_list_drops_none_params(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/comunicaciones", params={"limit": "10"}).mock(
            return_value=httpx.Response(200, json={"data": [], "next": None})
        )
        resource = ComunicacionesResource(sync_client)
        resource.list(limit=10, extra_none=None)
        assert route.called

    def test_get(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        respx_mock.get("/comunicaciones/com-001").mock(
            return_value=httpx.Response(200, json={"id": "com-001", "title": "test"})
        )
        resource = ComunicacionesResource(sync_client)
        result = resource.get("com-001")
        assert result["title"] == "test"

    def test_get_not_found(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/comunicaciones/nonexistent").mock(
            return_value=httpx.Response(404, json={"title": "Not Found", "status": 404})
        )
        resource = ComunicacionesResource(sync_client)
        with pytest.raises(NotFoundError):
            resource.get("nonexistent")

    def test_get_percent_encodes_id(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/comunicaciones/..%2Fadmin").mock(
            return_value=httpx.Response(404, json={"title": "Not Found", "status": 404})
        )
        resource = ComunicacionesResource(sync_client)
        with pytest.raises(NotFoundError):
            resource.get("../admin")
        assert route.called

    def test_iter_all_paginates(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/comunicaciones", params={"cursor": "c2"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": 2}], "next": None})
        )
        respx_mock.get("/comunicaciones", params={}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": 1}], "next": "c2"})
        )
        resource = ComunicacionesResource(sync_client)
        assert list(resource.iter_all()) == [{"id": 1}, {"id": 2}]


class TestComunicacionesAsync:
    async def test_list(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/comunicaciones").mock(
            return_value=httpx.Response(200, json={"data": [{"id": "x"}], "next": None})
        )
        resource = AsyncComunicacionesResource(async_client)
        assert await resource.list() == [{"id": "x"}]

    async def test_get(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/comunicaciones/com-001").mock(
            return_value=httpx.Response(200, json={"id": "com-001"})
        )
        resource = AsyncComunicacionesResource(async_client)
        assert await resource.get("com-001") == {"id": "com-001"}

    async def test_iter_all_paginates(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/comunicaciones", params={"cursor": "c2"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": 2}], "next": None})
        )
        respx_mock.get("/comunicaciones", params={}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": 1}], "next": "c2"})
        )
        resource = AsyncComunicacionesResource(async_client)
        collected = []
        async for item in resource.iter_all():
            collected.append(item)
        assert collected == [{"id": 1}, {"id": 2}]
