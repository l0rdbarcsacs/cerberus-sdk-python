"""Tests for ``cerberus_compliance.resources.esg`` (P5.3 — NCG 461)."""

from __future__ import annotations

import httpx
import pytest
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.errors import NotFoundError
from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource
from cerberus_compliance.resources.esg import AsyncESGResource, ESGResource


class TestESGMeta:
    def test_sync_prefix(self) -> None:
        assert ESGResource._path_prefix == "/esg"

    def test_async_prefix(self) -> None:
        assert AsyncESGResource._path_prefix == "/esg"

    def test_sync_subclass(self) -> None:
        assert issubclass(ESGResource, BaseResource)

    def test_async_subclass(self) -> None:
        assert issubclass(AsyncESGResource, AsyncBaseResource)


class TestESGSync:
    def test_get_by_rut(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        route = respx_mock.get("/esg/96505760-9").mock(
            return_value=httpx.Response(
                200,
                json={
                    "rut": "96505760-9",
                    "legal_name": "Falabella SA",
                    "ncg_461": {"reported": True, "year": 2023},
                },
            )
        )
        resource = ESGResource(sync_client)
        result = resource.get("96505760-9")
        assert result["rut"] == "96505760-9"
        assert result["ncg_461"]["reported"] is True
        assert route.called

    def test_get_not_found(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        respx_mock.get("/esg/00000000-0").mock(
            return_value=httpx.Response(404, json={"title": "Not Found", "status": 404})
        )
        resource = ESGResource(sync_client)
        with pytest.raises(NotFoundError):
            resource.get("00000000-0")

    def test_get_percent_encodes_rut(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/esg/..%2Fadmin").mock(
            return_value=httpx.Response(404, json={"title": "Not Found", "status": 404})
        )
        resource = ESGResource(sync_client)
        with pytest.raises(NotFoundError):
            resource.get("../admin")
        assert route.called

    def test_list(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        route = respx_mock.get("/esg").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [{"rut": "96505760-9"}, {"rut": "96806980-2"}],
                    "next": None,
                },
            )
        )
        resource = ESGResource(sync_client)
        result = resource.list()
        assert len(result) == 2
        assert result[0]["rut"] == "96505760-9"
        assert route.called

    def test_list_drops_none_params(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/esg", params={"sector": "retail"}).mock(
            return_value=httpx.Response(200, json={"data": [], "next": None})
        )
        resource = ESGResource(sync_client)
        resource.list(sector="retail", extra=None)
        assert route.called

    def test_iter_all_paginates(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/esg", params={"cursor": "c2"}).mock(
            return_value=httpx.Response(200, json={"data": [{"rut": "r2"}], "next": None})
        )
        respx_mock.get("/esg", params={}).mock(
            return_value=httpx.Response(200, json={"data": [{"rut": "r1"}], "next": "c2"})
        )
        resource = ESGResource(sync_client)
        assert list(resource.iter_all()) == [{"rut": "r1"}, {"rut": "r2"}]


class TestESGAsync:
    async def test_get(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/esg/96505760-9").mock(
            return_value=httpx.Response(200, json={"rut": "96505760-9", "ncg_461": {}})
        )
        resource = AsyncESGResource(async_client)
        result = await resource.get("96505760-9")
        assert result["rut"] == "96505760-9"

    async def test_list(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/esg").mock(
            return_value=httpx.Response(200, json={"data": [{"rut": "x"}], "next": None})
        )
        resource = AsyncESGResource(async_client)
        assert await resource.list() == [{"rut": "x"}]

    async def test_iter_all_paginates(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/esg", params={"cursor": "c2"}).mock(
            return_value=httpx.Response(200, json={"data": [{"rut": "r2"}], "next": None})
        )
        respx_mock.get("/esg", params={}).mock(
            return_value=httpx.Response(200, json={"data": [{"rut": "r1"}], "next": "c2"})
        )
        resource = AsyncESGResource(async_client)
        collected = []
        async for item in resource.iter_all():
            collected.append(item)
        assert collected == [{"rut": "r1"}, {"rut": "r2"}]
