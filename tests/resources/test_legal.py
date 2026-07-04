"""Tests for ``cerberus_compliance.resources.legal`` (v0.9.0)."""

from __future__ import annotations

import httpx
import pytest
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource
from cerberus_compliance.resources.legal import AsyncLegalResource, LegalResource


class TestLegalMeta:
    def test_sync_prefix(self) -> None:
        assert LegalResource._path_prefix == "/legal/search"

    def test_async_prefix(self) -> None:
        assert AsyncLegalResource._path_prefix == "/legal/search"

    def test_sync_subclass(self) -> None:
        assert issubclass(LegalResource, BaseResource)

    def test_async_subclass(self) -> None:
        assert issubclass(AsyncLegalResource, AsyncBaseResource)


class TestLegalSync:
    def test_search_no_filters(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        body = {
            "items": [{"numero": "21719"}],
            "next_cursor": None,
            "prev_cursor": None,
            "limit": 20,
        }
        route = respx_mock.get("/legal/search").mock(return_value=httpx.Response(200, json=body))
        result = LegalResource(sync_client).search()
        assert result == body
        assert route.called
        assert route.calls.last.request.url.query == b""

    def test_search_with_filters(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/legal/search",
            params={"q": "datos", "facetas": "proteccion_datos", "estado": "vigente", "limit": "5"},
        ).mock(return_value=httpx.Response(200, json={"items": [], "next_cursor": None}))
        LegalResource(sync_client).search(
            q="datos", facetas="proteccion_datos", estado="vigente", limit=5
        )
        assert route.called

    def test_iter_all_follows_cursor(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        page1 = {"items": [{"numero": "1"}], "next_cursor": "C2"}
        page2 = {"items": [{"numero": "2"}], "next_cursor": None}
        respx_mock.get("/legal/search").mock(
            side_effect=[httpx.Response(200, json=page1), httpx.Response(200, json=page2)]
        )
        got = list(LegalResource(sync_client).iter_all(q="x"))
        assert [n["numero"] for n in got] == ["1", "2"]


class TestLegalAsync:
    @pytest.mark.asyncio
    async def test_search(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        body = {"items": [{"numero": "21719"}], "next_cursor": None, "limit": 20}
        route = respx_mock.get("/legal/search").mock(return_value=httpx.Response(200, json=body))
        result = await AsyncLegalResource(async_client).search(q="ley")
        assert result == body
        assert route.called

    @pytest.mark.asyncio
    async def test_iter_all(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        page1 = {"items": [{"numero": "1"}], "next_cursor": "C2"}
        page2 = {"items": [{"numero": "2"}], "next_cursor": None}
        respx_mock.get("/legal/search").mock(
            side_effect=[httpx.Response(200, json=page1), httpx.Response(200, json=page2)]
        )
        got = [n async for n in AsyncLegalResource(async_client).iter_all()]
        assert [n["numero"] for n in got] == ["1", "2"]
