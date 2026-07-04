"""Tests for ``cerberus_compliance.resources.regulatory_subscriptions`` (v0.9.0)."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource
from cerberus_compliance.resources.regulatory_subscriptions import (
    AsyncRegulatorySubscriptionsResource,
    RegulatorySubscriptionsResource,
)

_PROFILE = {
    "sectores_ciiu": ["64", "65"],
    "secciones_rollup": ["Actividades financieras y de seguros"],
    "materias": [],
    "facetas": ["proteccion_datos"],
    "fuentes": [],
    "ruts": [],
}


class TestRegSubsMeta:
    def test_sync_prefix(self) -> None:
        assert RegulatorySubscriptionsResource._path_prefix == "/regulatory-subscriptions"

    def test_async_prefix(self) -> None:
        assert AsyncRegulatorySubscriptionsResource._path_prefix == "/regulatory-subscriptions"

    def test_sync_subclass(self) -> None:
        assert issubclass(RegulatorySubscriptionsResource, BaseResource)

    def test_async_subclass(self) -> None:
        assert issubclass(AsyncRegulatorySubscriptionsResource, AsyncBaseResource)


class TestRegSubsSync:
    def test_get(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        route = respx_mock.get("/regulatory-subscriptions").mock(
            return_value=httpx.Response(200, json=_PROFILE)
        )
        result = RegulatorySubscriptionsResource(sync_client).get()
        assert result == _PROFILE
        assert route.called

    def test_update_sends_only_provided_lists(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.put("/regulatory-subscriptions").mock(
            return_value=httpx.Response(200, json=_PROFILE)
        )
        RegulatorySubscriptionsResource(sync_client).update(
            sectores_ciiu=["64"], facetas=["proteccion_datos"]
        )
        assert route.called
        sent = json.loads(route.calls.last.request.content)
        # Solo las listas provistas viajan en el body (upsert parcial).
        assert sent == {"sectores_ciiu": ["64"], "facetas": ["proteccion_datos"]}

    def test_update_empty_body_when_nothing_provided(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.put("/regulatory-subscriptions").mock(
            return_value=httpx.Response(200, json=_PROFILE)
        )
        RegulatorySubscriptionsResource(sync_client).update()
        assert json.loads(route.calls.last.request.content) == {}


class TestRegSubsAsync:
    @pytest.mark.asyncio
    async def test_get(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/regulatory-subscriptions").mock(
            return_value=httpx.Response(200, json=_PROFILE)
        )
        result = await AsyncRegulatorySubscriptionsResource(async_client).get()
        assert result == _PROFILE
        assert route.called

    @pytest.mark.asyncio
    async def test_update(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.put("/regulatory-subscriptions").mock(
            return_value=httpx.Response(200, json=_PROFILE)
        )
        await AsyncRegulatorySubscriptionsResource(async_client).update(ruts=["76543210-9"])
        assert json.loads(route.calls.last.request.content) == {"ruts": ["76543210-9"]}
