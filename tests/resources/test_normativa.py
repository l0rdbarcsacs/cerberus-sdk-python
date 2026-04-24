"""TDD tests for ``cerberus_compliance.resources.normativa`` (G15).

The Normativa resource wraps ``/normativa``, ``/normativa/{id}`` and
``/normativa/{id}/mercado`` — the Chilean regulatory-text catalogue
plus its per-norm market-segment mapping.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.errors import NotFoundError
from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource
from cerberus_compliance.resources.normativa import (
    AsyncNormativaResource,
    NormativaResource,
)


class TestNormativaMeta:
    def test_sync_prefix(self) -> None:
        assert NormativaResource._path_prefix == "/normativa"

    def test_async_prefix(self) -> None:
        assert AsyncNormativaResource._path_prefix == "/normativa"

    def test_sync_subclass(self) -> None:
        assert issubclass(NormativaResource, BaseResource)

    def test_async_subclass(self) -> None:
        assert issubclass(AsyncNormativaResource, AsyncBaseResource)


class TestNormativaSync:
    def test_list(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        route = respx_mock.get("/normativa").mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"id": "ley-21521"}, {"id": "ncg-514"}], "next": None},
            )
        )
        resource = NormativaResource(sync_client)
        assert resource.list() == [{"id": "ley-21521"}, {"id": "ncg-514"}]
        assert route.called

    def test_list_forwards_filters(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/normativa", params={"framework": "Ley21521"}).mock(
            return_value=httpx.Response(200, json={"data": [], "next": None})
        )
        resource = NormativaResource(sync_client)
        resource.list(framework="Ley21521", active=None)
        assert route.called

    def test_get(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        respx_mock.get("/normativa/ley-21521").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "ley-21521",
                    "title": "Ley Fintech",
                    "citation": "Ley 21.521",
                },
            )
        )
        resource = NormativaResource(sync_client)
        result = resource.get("ley-21521")
        assert result["title"] == "Ley Fintech"

    def test_mercado_returns_aggregate(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/normativa/ley-21521/mercado").mock(
            return_value=httpx.Response(
                200,
                json={
                    "normativa_id": "ley-21521",
                    "segmentos": ["fintech", "plataformas-alternativas"],
                },
            )
        )
        resource = NormativaResource(sync_client)
        result = resource.mercado("ley-21521")
        assert result["segmentos"] == ["fintech", "plataformas-alternativas"]
        assert route.called

    def test_mercado_percent_encodes_id(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/normativa/..%2Fadmin/mercado").mock(
            return_value=httpx.Response(404, json={"title": "Not Found", "status": 404})
        )
        resource = NormativaResource(sync_client)
        with pytest.raises(NotFoundError):
            resource.mercado("../admin")
        assert route.called


class TestNormativaAsync:
    async def test_list(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/normativa").mock(
            return_value=httpx.Response(200, json={"data": [{"id": "x"}], "next": None})
        )
        resource = AsyncNormativaResource(async_client)
        assert await resource.list() == [{"id": "x"}]

    async def test_get(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/normativa/ley-21521").mock(
            return_value=httpx.Response(200, json={"id": "ley-21521"})
        )
        resource = AsyncNormativaResource(async_client)
        assert await resource.get("ley-21521") == {"id": "ley-21521"}

    async def test_mercado(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/normativa/ley-21521/mercado").mock(
            return_value=httpx.Response(200, json={"normativa_id": "ley-21521", "segmentos": []})
        )
        resource = AsyncNormativaResource(async_client)
        result = await resource.mercado("ley-21521")
        assert result["normativa_id"] == "ley-21521"


class TestNormativaIterAll:
    def test_sync_iter_all_paginates(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/normativa", params={"cursor": "n2"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": 2}], "next": None})
        )
        respx_mock.get("/normativa", params={}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": 1}], "next": "n2"})
        )
        resource = NormativaResource(sync_client)
        assert list(resource.iter_all()) == [{"id": 1}, {"id": 2}]

    async def test_async_iter_all_paginates(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/normativa", params={"cursor": "n2"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": 2}], "next": None})
        )
        respx_mock.get("/normativa", params={}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": 1}], "next": "n2"})
        )
        resource = AsyncNormativaResource(async_client)
        collected: list[dict[str, object]] = []
        async for item in resource.iter_all():
            collected.append(item)
        assert collected == [{"id": 1}, {"id": 2}]
