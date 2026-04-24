"""TDD tests for ``cerberus_compliance.resources.rpsf`` (G14).

The RPSF resource wraps the CMF Registro Público de Servicios Financieros
endpoints: ``/rpsf``, ``/rpsf/{id}``, ``/rpsf/by-entity/{id}``, and
``/rpsf/by-servicio/{servicio}``.
"""

from __future__ import annotations

from typing import Any

import httpx
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource
from cerberus_compliance.resources.rpsf import AsyncRPSFResource, RPSFResource


class TestRPSFMeta:
    def test_sync_prefix(self) -> None:
        assert RPSFResource._path_prefix == "/rpsf"

    def test_async_prefix(self) -> None:
        assert AsyncRPSFResource._path_prefix == "/rpsf"

    def test_sync_subclass(self) -> None:
        assert issubclass(RPSFResource, BaseResource)

    def test_async_subclass(self) -> None:
        assert issubclass(AsyncRPSFResource, AsyncBaseResource)


class TestRPSFSync:
    def test_list_no_params(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/rpsf").mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"id": "rpsf_1"}, {"id": "rpsf_2"}], "next": None},
            )
        )
        resource = RPSFResource(sync_client)
        assert resource.list() == [{"id": "rpsf_1"}, {"id": "rpsf_2"}]
        assert route.called

    def test_list_forwards_filters_and_drops_none(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/rpsf", params={"servicio": "corredora", "limit": "10"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": "rpsf_3"}], "next": None})
        )
        resource = RPSFResource(sync_client)
        resource.list(servicio="corredora", limit=10, framework=None)
        assert route.called

    def test_get_by_id(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        respx_mock.get("/rpsf/rpsf_42").mock(
            return_value=httpx.Response(200, json={"id": "rpsf_42", "servicio": "agente"})
        )
        resource = RPSFResource(sync_client)
        assert resource.get("rpsf_42") == {"id": "rpsf_42", "servicio": "agente"}

    def test_by_entity_returns_data_list(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/rpsf/by-entity/ent_7").mock(
            return_value=httpx.Response(200, json={"data": [{"id": "rpsf_1"}]})
        )
        resource = RPSFResource(sync_client)
        assert resource.by_entity("ent_7") == [{"id": "rpsf_1"}]
        assert route.called

    def test_by_entity_missing_data_returns_empty(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/rpsf/by-entity/ent_7").mock(
            return_value=httpx.Response(200, json={"data": "oops"})
        )
        resource = RPSFResource(sync_client)
        assert resource.by_entity("ent_7") == []

    def test_by_servicio_percent_encodes(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/rpsf/by-servicio/corredora%20de%20bolsa").mock(
            return_value=httpx.Response(200, json={"data": [{"id": "rpsf_9"}]})
        )
        resource = RPSFResource(sync_client)
        assert resource.by_servicio("corredora de bolsa") == [{"id": "rpsf_9"}]
        assert route.called

    def test_iter_all_paginates(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        page2 = respx_mock.get("/rpsf", params={"cursor": "tok2"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": 2}], "next": None})
        )
        page1 = respx_mock.get("/rpsf", params={}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": 1}], "next": "tok2"})
        )
        resource = RPSFResource(sync_client)
        items = list(resource.iter_all())
        assert items == [{"id": 1}, {"id": 2}]
        assert page1.called
        assert page2.called


class TestRPSFAsync:
    async def test_list(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/rpsf").mock(
            return_value=httpx.Response(200, json={"data": [{"id": "r1"}], "next": None})
        )
        resource = AsyncRPSFResource(async_client)
        assert await resource.list() == [{"id": "r1"}]

    async def test_get(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/rpsf/r1").mock(return_value=httpx.Response(200, json={"id": "r1"}))
        resource = AsyncRPSFResource(async_client)
        assert await resource.get("r1") == {"id": "r1"}

    async def test_by_entity(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/rpsf/by-entity/ent_1").mock(
            return_value=httpx.Response(200, json={"data": [{"id": "r1"}]})
        )
        resource = AsyncRPSFResource(async_client)
        assert await resource.by_entity("ent_1") == [{"id": "r1"}]

    async def test_by_servicio(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/rpsf/by-servicio/agente").mock(
            return_value=httpx.Response(200, json={"data": [{"id": "r2"}]})
        )
        resource = AsyncRPSFResource(async_client)
        assert await resource.by_servicio("agente") == [{"id": "r2"}]

    async def test_iter_all(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/rpsf", params={"cursor": "n2"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": 2}], "next": None})
        )
        respx_mock.get("/rpsf", params={}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": 1}], "next": "n2"})
        )
        resource = AsyncRPSFResource(async_client)
        collected: list[dict[str, Any]] = []
        async for item in resource.iter_all():
            collected.append(item)
        assert collected == [{"id": 1}, {"id": 2}]


class TestRPSFDefensiveEnvelopeHandling:
    def test_sync_by_servicio_non_list_data_returns_empty(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/rpsf/by-servicio/x").mock(
            return_value=httpx.Response(200, json={"data": "oops"})
        )
        resource = RPSFResource(sync_client)
        assert resource.by_servicio("x") == []

    async def test_async_by_entity_non_list_data_returns_empty(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/rpsf/by-entity/x").mock(
            return_value=httpx.Response(200, json={"data": "oops"})
        )
        resource = AsyncRPSFResource(async_client)
        assert await resource.by_entity("x") == []

    async def test_async_by_servicio_non_list_data_returns_empty(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/rpsf/by-servicio/x").mock(
            return_value=httpx.Response(200, json={"data": "oops"})
        )
        resource = AsyncRPSFResource(async_client)
        assert await resource.by_servicio("x") == []

    # -----------------------------------------------------------------
    # Prod-shape envelope ({items: ...}) must unwrap transparently via
    # the shared BaseResource._extract_items helper.
    # -----------------------------------------------------------------

    def test_sync_by_entity_accepts_items_envelope(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/rpsf/by-entity/ent_7").mock(
            return_value=httpx.Response(200, json={"items": [{"id": "rpsf_items_1"}]})
        )
        resource = RPSFResource(sync_client)
        assert resource.by_entity("ent_7") == [{"id": "rpsf_items_1"}]

    def test_sync_by_servicio_accepts_items_envelope(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/rpsf/by-servicio/agente").mock(
            return_value=httpx.Response(200, json={"items": [{"id": "rpsf_items_2"}]})
        )
        resource = RPSFResource(sync_client)
        assert resource.by_servicio("agente") == [{"id": "rpsf_items_2"}]

    async def test_async_by_entity_accepts_items_envelope(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/rpsf/by-entity/ent_1").mock(
            return_value=httpx.Response(200, json={"items": [{"id": "rpsf_items_3"}]})
        )
        resource = AsyncRPSFResource(async_client)
        assert await resource.by_entity("ent_1") == [{"id": "rpsf_items_3"}]

    async def test_async_by_servicio_accepts_items_envelope(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/rpsf/by-servicio/agente").mock(
            return_value=httpx.Response(200, json={"items": [{"id": "rpsf_items_4"}]})
        )
        resource = AsyncRPSFResource(async_client)
        assert await resource.by_servicio("agente") == [{"id": "rpsf_items_4"}]
