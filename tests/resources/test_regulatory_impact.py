"""Tests for ``cerberus_compliance.resources.regulatory_impact`` (v0.9.0)."""

from __future__ import annotations

import httpx
import pytest
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource
from cerberus_compliance.resources.regulatory_impact import (
    AsyncRegulatoryImpactResource,
    RegulatoryImpactResource,
)

_ID = "a1b2c3d4-1111-2222-3333-444455556666"


class TestRegulatoryImpactMeta:
    def test_sync_prefix(self) -> None:
        assert RegulatoryImpactResource._path_prefix == "/regulatory-impact"

    def test_async_prefix(self) -> None:
        assert AsyncRegulatoryImpactResource._path_prefix == "/regulatory-impact"

    def test_sync_subclass(self) -> None:
        assert issubclass(RegulatoryImpactResource, BaseResource)

    def test_async_subclass(self) -> None:
        assert issubclass(AsyncRegulatoryImpactResource, AsyncBaseResource)


class TestRegulatoryImpactSync:
    def test_get(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        body = {"id": _ID, "titulo": "Impacto NCG X", "severidad": "alta"}
        route = respx_mock.get(f"/regulatory-impact/{_ID}").mock(
            return_value=httpx.Response(200, json=body)
        )
        result = RegulatoryImpactResource(sync_client).get(_ID)
        assert result == body
        assert route.called

    def test_get_encodes_id(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/regulatory-impact/a%2Fb").mock(
            return_value=httpx.Response(200, json={})
        )
        RegulatoryImpactResource(sync_client).get("a/b")
        assert route.called


class TestRegulatoryImpactAsync:
    @pytest.mark.asyncio
    async def test_get(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        body = {"id": _ID, "titulo": "Impacto"}
        route = respx_mock.get(f"/regulatory-impact/{_ID}").mock(
            return_value=httpx.Response(200, json=body)
        )
        result = await AsyncRegulatoryImpactResource(async_client).get(_ID)
        assert result == body
        assert route.called
