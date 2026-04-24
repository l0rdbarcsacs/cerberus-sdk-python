"""TDD tests for ``cerberus_compliance.resources.normativa_consulta`` (G9).

The ``NormativaConsultaResource`` wraps the flat ``/normativa-consulta``
list endpoint with an ``estado`` filter (``abierta`` / ``cerrada``).
There is no ``get(id)`` surface — the CMF consulta identifier is not
stable across the two upstream portal views, so the SDK exposes only a
list with pagination params forwarded verbatim.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.errors import ValidationError
from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource
from cerberus_compliance.resources.normativa_consulta import (
    AsyncNormativaConsultaResource,
    NormativaConsultaResource,
)

# ---------------------------------------------------------------------------
# Meta
# ---------------------------------------------------------------------------


class TestNormativaConsultaMeta:
    def test_sync_prefix(self) -> None:
        assert NormativaConsultaResource._path_prefix == "/normativa-consulta"

    def test_async_prefix(self) -> None:
        assert AsyncNormativaConsultaResource._path_prefix == "/normativa-consulta"

    def test_sync_subclass(self) -> None:
        assert issubclass(NormativaConsultaResource, BaseResource)

    def test_async_subclass(self) -> None:
        assert issubclass(AsyncNormativaConsultaResource, AsyncBaseResource)

    def test_client_wires_attribute(self, sync_client: CerberusClient) -> None:
        assert isinstance(sync_client.normativa_consulta, NormativaConsultaResource)


# ---------------------------------------------------------------------------
# Sync list
# ---------------------------------------------------------------------------


class TestNormativaConsultaList:
    def test_list_default_estado_is_abierta(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/normativa-consulta",
            params={"estado": "abierta", "limit": "100"},
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "items": [
                        {"cmf_consulta_id": "CTA-2026-017", "estado": "abierta"},
                    ],
                    "next_cursor": None,
                    "limit": 100,
                },
            )
        )
        resource = NormativaConsultaResource(sync_client)
        rows = resource.list()
        assert rows == [{"cmf_consulta_id": "CTA-2026-017", "estado": "abierta"}]
        assert route.called

    def test_list_cerrada_explicit(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get(
            "/normativa-consulta",
            params={"estado": "cerrada", "limit": "50"},
        ).mock(
            return_value=httpx.Response(
                200,
                json={"items": [], "next_cursor": None, "limit": 50},
            )
        )
        resource = NormativaConsultaResource(sync_client)
        rows = resource.list(estado="cerrada", limit=50)
        assert rows == []

    def test_list_forwards_offset_when_nonzero(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get(
            "/normativa-consulta",
            params={"estado": "abierta", "limit": "100", "offset": "50"},
        ).mock(return_value=httpx.Response(200, json={"items": []}))
        resource = NormativaConsultaResource(sync_client)
        assert resource.list(offset=50) == []

    def test_list_omits_offset_when_zero(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        """offset=0 (the default) should not pollute the query string."""
        route = respx_mock.get(
            "/normativa-consulta",
            params={"estado": "abierta", "limit": "100"},
        ).mock(return_value=httpx.Response(200, json={"items": []}))
        resource = NormativaConsultaResource(sync_client)
        resource.list()
        request = route.calls.last.request
        assert "offset" not in request.url.params

    def test_list_accepts_data_envelope(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        """Envelope compatibility: ``{"data": [...]}`` also works."""
        respx_mock.get(
            "/normativa-consulta",
            params={"estado": "abierta", "limit": "100"},
        ).mock(return_value=httpx.Response(200, json={"data": [{"id": "x"}], "next": None}))
        resource = NormativaConsultaResource(sync_client)
        assert resource.list() == [{"id": "x"}]

    def test_list_422_raises_validation_error(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        """Passing an invalid ``estado`` surfaces as :class:`ValidationError`."""
        respx_mock.get(
            "/normativa-consulta",
            params={"estado": "pendiente", "limit": "100"},
        ).mock(
            return_value=httpx.Response(
                422,
                json={
                    "type": "about:blank",
                    "title": "Validation error",
                    "status": 422,
                    "detail": "estado must be abierta|cerrada",
                },
            )
        )
        resource = NormativaConsultaResource(sync_client)
        with pytest.raises(ValidationError):
            resource.list(estado="pendiente")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Async mirror
# ---------------------------------------------------------------------------


class TestNormativaConsultaAsync:
    async def test_list_default(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get(
            "/normativa-consulta",
            params={"estado": "abierta", "limit": "100"},
        ).mock(
            return_value=httpx.Response(
                200,
                json={"items": [{"cmf_consulta_id": "CTA-2026-017"}]},
            )
        )
        resource = AsyncNormativaConsultaResource(async_client)
        rows = await resource.list()
        assert rows == [{"cmf_consulta_id": "CTA-2026-017"}]

    async def test_list_cerrada(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get(
            "/normativa-consulta",
            params={"estado": "cerrada", "limit": "100"},
        ).mock(return_value=httpx.Response(200, json={"items": []}))
        resource = AsyncNormativaConsultaResource(async_client)
        assert await resource.list(estado="cerrada") == []
