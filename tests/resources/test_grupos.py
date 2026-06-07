"""Tests for ``cerberus_compliance.resources.grupos`` (CMF grupos empresariales)."""

from __future__ import annotations

import httpx
import pytest
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.errors import CerberusAPIError, NotFoundError
from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource
from cerberus_compliance.resources.grupos import AsyncGruposResource, GruposResource

# A representative GroupGraph response covering every documented field,
# including nullable controller fields and the member ordering contract.
_GROUP_GRAPH = {
    "grupo_id": "G-001",
    "grupo": "Grupo Falabella",
    "controlador": {"rut": "92011000-2", "nombre": "Inversiones Auguri SA"},
    "fecha_vigencia": "2024-01-01",
    "miembros": [
        {
            "rut": "92011000-2",
            "nombre": "Inversiones Auguri SA",
            "role": "1. Es Controlador.",
            "es_controlador": True,
        },
        {
            "rut": "96505760-9",
            "nombre": "Falabella SA",
            "role": None,
            "es_controlador": False,
        },
    ],
}


class TestGruposMeta:
    def test_sync_prefix(self) -> None:
        assert GruposResource._path_prefix == "/grupos"

    def test_async_prefix(self) -> None:
        assert AsyncGruposResource._path_prefix == "/grupos"

    def test_sync_subclass(self) -> None:
        assert issubclass(GruposResource, BaseResource)

    def test_async_subclass(self) -> None:
        assert issubclass(AsyncGruposResource, AsyncBaseResource)


class TestGruposSync:
    def test_get_by_rut(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        route = respx_mock.get("/grupos/96505760-9").mock(
            return_value=httpx.Response(200, json=_GROUP_GRAPH)
        )
        resource = GruposResource(sync_client)
        result = resource.get_by_rut("96505760-9")
        assert result == _GROUP_GRAPH
        assert result["grupo_id"] == "G-001"
        assert result["controlador"]["nombre"] == "Inversiones Auguri SA"
        assert result["miembros"][0]["es_controlador"] is True
        assert result["miembros"][1]["role"] is None
        assert route.called
        # No query string and no request body for this endpoint.
        assert route.calls.last.request.url.query == b""
        assert route.calls.last.request.content == b""

    def test_get_by_rut_null_controlador(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        body = {
            "grupo_id": "G-002",
            "grupo": "Grupo Sin Controlador",
            "controlador": None,
            "fecha_vigencia": None,
            "miembros": [],
        }
        respx_mock.get("/grupos/B98771116").mock(return_value=httpx.Response(200, json=body))
        resource = GruposResource(sync_client)
        result = resource.get_by_rut("B98771116")
        assert result["controlador"] is None
        assert result["fecha_vigencia"] is None
        assert result["miembros"] == []

    def test_get_by_rut_percent_encodes(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/grupos/..%2Fadmin").mock(
            return_value=httpx.Response(404, json={"title": "Not Found", "status": 404})
        )
        resource = GruposResource(sync_client)
        with pytest.raises(NotFoundError):
            resource.get_by_rut("../admin")
        assert route.called

    def test_get_by_rut_not_found(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/grupos/00000000-0").mock(
            return_value=httpx.Response(404, json={"title": "Not Found", "status": 404})
        )
        resource = GruposResource(sync_client)
        with pytest.raises(NotFoundError):
            resource.get_by_rut("00000000-0")

    def test_get_by_rut_forbidden_scope(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/grupos/96505760-9").mock(
            return_value=httpx.Response(403, json={"title": "Forbidden", "status": 403})
        )
        resource = GruposResource(sync_client)
        with pytest.raises(CerberusAPIError) as exc:
            resource.get_by_rut("96505760-9")
        assert exc.value.status == 403


class TestGruposAsync:
    async def test_get_by_rut(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/grupos/96505760-9").mock(
            return_value=httpx.Response(200, json=_GROUP_GRAPH)
        )
        resource = AsyncGruposResource(async_client)
        result = await resource.get_by_rut("96505760-9")
        assert result == _GROUP_GRAPH
        assert result["miembros"][0]["es_controlador"] is True
        assert route.called
        assert route.calls.last.request.url.query == b""

    async def test_get_by_rut_percent_encodes(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/grupos/..%2Fadmin").mock(
            return_value=httpx.Response(404, json={"title": "Not Found", "status": 404})
        )
        resource = AsyncGruposResource(async_client)
        with pytest.raises(NotFoundError):
            await resource.get_by_rut("../admin")
        assert route.called

    async def test_get_by_rut_not_found(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/grupos/00000000-0").mock(
            return_value=httpx.Response(404, json={"title": "Not Found", "status": 404})
        )
        resource = AsyncGruposResource(async_client)
        with pytest.raises(NotFoundError):
            await resource.get_by_rut("00000000-0")
