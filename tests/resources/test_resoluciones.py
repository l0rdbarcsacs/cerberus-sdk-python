"""Tests for ``cerberus_compliance.resources.resoluciones`` (P5.3)."""

from __future__ import annotations

import httpx
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.errors import NotFoundError
from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource
from cerberus_compliance.resources.resoluciones import (
    AsyncResolucionesResource,
    ResolucionesResource,
)


class TestResolucionesMeta:
    def test_sync_prefix(self) -> None:
        assert ResolucionesResource._path_prefix == "/resoluciones"

    def test_async_prefix(self) -> None:
        assert AsyncResolucionesResource._path_prefix == "/resoluciones"

    def test_sync_subclass(self) -> None:
        assert issubclass(ResolucionesResource, BaseResource)

    def test_async_subclass(self) -> None:
        assert issubclass(AsyncResolucionesResource, AsyncBaseResource)


class TestResolucionesSync:
    def test_list(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        route = respx_mock.get("/resoluciones").mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"id": "res-2024-0001"}, {"id": "res-2024-0002"}], "next": None},
            )
        )
        resource = ResolucionesResource(sync_client)
        result = resource.list()
        assert result == [{"id": "res-2024-0001"}, {"id": "res-2024-0002"}]
        assert route.called

    def test_list_forwards_filters_drops_none(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/resoluciones", params={"year": "2024"}).mock(
            return_value=httpx.Response(200, json={"data": [], "next": None})
        )
        resource = ResolucionesResource(sync_client)
        resource.list(year="2024", entity_rut=None)
        assert route.called

    def test_get(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        respx_mock.get("/resoluciones/res-2024-0042").mock(
            return_value=httpx.Response(
                200, json={"id": "res-2024-0042", "titulo": "Resolucion de prueba"}
            )
        )
        resource = ResolucionesResource(sync_client)
        result = resource.get("res-2024-0042")
        assert result["titulo"] == "Resolucion de prueba"

    def test_get_not_found(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        respx_mock.get("/resoluciones/nonexistent").mock(
            return_value=httpx.Response(404, json={"title": "Not Found", "status": 404})
        )
        resource = ResolucionesResource(sync_client)
        import pytest

        with pytest.raises(NotFoundError):
            resource.get("nonexistent")

    def test_get_percent_encodes_id(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/resoluciones/..%2Fadmin").mock(
            return_value=httpx.Response(404, json={"title": "Not Found", "status": 404})
        )
        resource = ResolucionesResource(sync_client)
        import pytest

        with pytest.raises(NotFoundError):
            resource.get("../admin")
        assert route.called

    def test_iter_all_paginates(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/resoluciones", params={"cursor": "cur2"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": 2}], "next": None})
        )
        respx_mock.get("/resoluciones", params={}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": 1}], "next": "cur2"})
        )
        resource = ResolucionesResource(sync_client)
        assert list(resource.iter_all()) == [{"id": 1}, {"id": 2}]


class TestResolucionesAsync:
    async def test_list(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/resoluciones").mock(
            return_value=httpx.Response(200, json={"data": [{"id": "res-async-1"}], "next": None})
        )
        resource = AsyncResolucionesResource(async_client)
        assert await resource.list() == [{"id": "res-async-1"}]

    async def test_get(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/resoluciones/res-2024-0001").mock(
            return_value=httpx.Response(200, json={"id": "res-2024-0001"})
        )
        resource = AsyncResolucionesResource(async_client)
        assert await resource.get("res-2024-0001") == {"id": "res-2024-0001"}

    async def test_iter_all(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/resoluciones", params={"cursor": "c2"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": 2}], "next": None})
        )
        respx_mock.get("/resoluciones", params={}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": 1}], "next": "c2"})
        )
        resource = AsyncResolucionesResource(async_client)
        collected = []
        async for item in resource.iter_all():
            collected.append(item)
        assert collected == [{"id": 1}, {"id": 2}]
