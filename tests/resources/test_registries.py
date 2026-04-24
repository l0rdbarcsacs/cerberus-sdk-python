"""TDD tests for ``cerberus_compliance.resources.registries``.

The :class:`RegistriesResource` proxies the public Chilean registries
sub-API (CMF / SII / DICOM / Conservador de Bienes Raíces) plus a
RUT-lookup helper that normalises the input before issuing the request.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.errors import CerberusAPIError
from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource
from cerberus_compliance.resources.registries import (
    AsyncRegistriesResource,
    RegistriesResource,
)

# ---------------------------------------------------------------------------
# Meta / subclass hygiene
# ---------------------------------------------------------------------------


class TestRegistriesClassMeta:
    def test_path_prefix_is_registries(self) -> None:
        assert RegistriesResource._path_prefix == "/registries"
        assert AsyncRegistriesResource._path_prefix == "/registries"

    def test_is_subclass_of_base_resource(self) -> None:
        assert issubclass(RegistriesResource, BaseResource)
        assert issubclass(AsyncRegistriesResource, AsyncBaseResource)


# ---------------------------------------------------------------------------
# Sync tests
# ---------------------------------------------------------------------------


class TestRegistriesResource:
    def test_list_no_filters(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/registries").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [{"id": "reg_1", "type": "CMF"}, {"id": "reg_2", "type": "SII"}],
                    "next": None,
                },
            )
        )
        resource = RegistriesResource(sync_client)

        items = resource.list()

        assert items == [{"id": "reg_1", "type": "CMF"}, {"id": "reg_2", "type": "SII"}]
        assert route.called
        # No query string should have been sent.
        assert route.calls.last.request.url.query == b""

    def test_list_filters_registry_type(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/registries", params={"registry_type": "CMF"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": "reg_1"}], "next": None})
        )
        resource = RegistriesResource(sync_client)

        items = resource.list(registry_type="CMF")

        assert items == [{"id": "reg_1"}]
        assert route.called

    def test_list_forwards_limit(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/registries", params={"registry_type": "DICOM", "limit": "5"}).mock(
            return_value=httpx.Response(200, json={"data": [], "next": None})
        )
        resource = RegistriesResource(sync_client)

        assert resource.list(registry_type="DICOM", limit=5) == []
        assert route.called

    def test_list_omits_none(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/registries", params={"registry_type": "SII"}).mock(
            return_value=httpx.Response(200, json={"data": [], "next": None})
        )
        resource = RegistriesResource(sync_client)

        # Passing only registry_type; limit defaults to None and must NOT be sent.
        resource.list(registry_type="SII")

        assert route.called
        query = route.calls.last.request.url.query.decode()
        assert "limit" not in query
        assert "registry_type=SII" in query

    def test_list_with_all_none_sends_no_query(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/registries").mock(
            return_value=httpx.Response(200, json={"data": [], "next": None})
        )
        resource = RegistriesResource(sync_client)

        resource.list(registry_type=None, limit=None)

        assert route.called
        assert route.calls.last.request.url.query == b""

    def test_get_by_id(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        respx_mock.get("/registries/reg_42").mock(
            return_value=httpx.Response(
                200, json={"id": "reg_42", "type": "Conservador", "status": "active"}
            )
        )
        resource = RegistriesResource(sync_client)

        result = resource.get("reg_42")

        assert result == {"id": "reg_42", "type": "Conservador", "status": "active"}

    def test_get_404_raises_cerberus_api_error(
        self,
        sync_client: CerberusClient,
        respx_mock: respx.MockRouter,
        problem_json: Any,
    ) -> None:
        respx_mock.get("/registries/missing").mock(
            return_value=httpx.Response(
                404,
                json=problem_json(
                    status=404, title="Not Found", detail="registry missing not found"
                ),
                headers={"content-type": "application/problem+json"},
            )
        )
        resource = RegistriesResource(sync_client)

        with pytest.raises(CerberusAPIError) as excinfo:
            resource.get("missing")

        assert excinfo.value.status == 404

    def test_lookup_rut_normalizes_dots_hyphens(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/registries/lookup/rut/12345678-5").mock(
            return_value=httpx.Response(200, json={"rut": "12345678-5", "name": "Acme"})
        )
        resource = RegistriesResource(sync_client)

        result = resource.lookup_rut("12.345.678-5")

        assert result == {"rut": "12345678-5", "name": "Acme"}
        assert route.called

    def test_lookup_rut_uppercases_k(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/registries/lookup/rut/12345678-K").mock(
            return_value=httpx.Response(200, json={"rut": "12345678-K"})
        )
        resource = RegistriesResource(sync_client)

        result = resource.lookup_rut("12.345.678-k")

        assert result == {"rut": "12345678-K"}
        assert route.called

    def test_lookup_rut_strips_whitespace(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/registries/lookup/rut/12345678-5").mock(
            return_value=httpx.Response(200, json={"rut": "12345678-5"})
        )
        resource = RegistriesResource(sync_client)

        resource.lookup_rut(" 12345678-5 ")

        assert route.called

    def test_lookup_rut_already_canonical(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/registries/lookup/rut/76543210-9").mock(
            return_value=httpx.Response(200, json={"rut": "76543210-9"})
        )
        resource = RegistriesResource(sync_client)

        assert resource.lookup_rut("76543210-9") == {"rut": "76543210-9"}
        assert route.called

    def test_lookup_rut_invalid_empty_raises_value_error(self, sync_client: CerberusClient) -> None:
        resource = RegistriesResource(sync_client)

        with pytest.raises(ValueError, match="invalid RUT"):
            resource.lookup_rut("")

    def test_lookup_rut_invalid_whitespace_only_raises(self, sync_client: CerberusClient) -> None:
        resource = RegistriesResource(sync_client)

        with pytest.raises(ValueError, match="invalid RUT"):
            resource.lookup_rut("   ")

    def test_lookup_rut_invalid_non_alnum_raises(self, sync_client: CerberusClient) -> None:
        resource = RegistriesResource(sync_client)

        with pytest.raises(ValueError, match="invalid RUT"):
            resource.lookup_rut("abc!@#")

    def test_lookup_rut_invalid_only_punctuation_raises(self, sync_client: CerberusClient) -> None:
        resource = RegistriesResource(sync_client)

        with pytest.raises(ValueError, match="invalid RUT"):
            resource.lookup_rut("...---")

    @pytest.mark.parametrize("bad", ["5", "k", "K", "-5", "5-"])
    def test_lookup_rut_single_char_body_rejected(
        self, sync_client: CerberusClient, bad: str
    ) -> None:
        # After stripping, a single alphanumeric character leaves an
        # empty body — reject before emitting a malformed ``-5`` path.
        resource = RegistriesResource(sync_client)
        with pytest.raises(ValueError, match="invalid RUT"):
            resource.lookup_rut(bad)

    def test_lookup_rut_alphabetic_body_rejected(self, sync_client: CerberusClient) -> None:
        # Body must be purely numeric (Chilean RUT convention).
        resource = RegistriesResource(sync_client)
        with pytest.raises(ValueError, match="invalid RUT"):
            resource.lookup_rut("abc1234-5")

    def test_lookup_rut_non_dk_verifier_rejected(self, sync_client: CerberusClient) -> None:
        # Verifier must be a digit or ``K``; anything else is syntactically invalid.
        resource = RegistriesResource(sync_client)
        with pytest.raises(ValueError, match="invalid RUT"):
            resource.lookup_rut("12345678-Z")

    def test_iter_all_paginates_forwards_filters(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        # Specific (cursor) route FIRST — respx is subset-match and picks in order.
        page2 = respx_mock.get(
            "/registries", params={"registry_type": "SII", "cursor": "tok2"}
        ).mock(return_value=httpx.Response(200, json={"data": [{"id": "reg_2"}], "next": None}))
        page1 = respx_mock.get("/registries", params={"registry_type": "SII"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": "reg_1"}], "next": "tok2"})
        )
        resource = RegistriesResource(sync_client)

        items = list(resource.iter_all(registry_type="SII"))

        assert items == [{"id": "reg_1"}, {"id": "reg_2"}]
        assert page1.called
        assert page2.called

    def test_iter_all_drops_none_filters(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/registries", params={"registry_type": "CMF"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": "r1"}], "next": None})
        )
        resource = RegistriesResource(sync_client)

        items = list(resource.iter_all(registry_type="CMF", limit=None))

        assert items == [{"id": "r1"}]
        assert route.called
        query = route.calls.last.request.url.query.decode()
        assert "limit" not in query

    def test_iter_all_stops_on_null_next(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/registries").mock(
            return_value=httpx.Response(200, json={"data": [{"id": "only"}], "next": None})
        )
        resource = RegistriesResource(sync_client)

        assert list(resource.iter_all()) == [{"id": "only"}]
        assert route.call_count == 1


# ---------------------------------------------------------------------------
# Async tests
# ---------------------------------------------------------------------------


class TestAsyncRegistriesResource:
    async def test_list_no_filters(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/registries").mock(
            return_value=httpx.Response(
                200, json={"data": [{"id": "reg_a"}, {"id": "reg_b"}], "next": None}
            )
        )
        resource = AsyncRegistriesResource(async_client)

        items = await resource.list()

        assert items == [{"id": "reg_a"}, {"id": "reg_b"}]
        assert route.called
        assert route.calls.last.request.url.query == b""

    async def test_list_filters_registry_type(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/registries", params={"registry_type": "DICOM"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": "d1"}], "next": None})
        )
        resource = AsyncRegistriesResource(async_client)

        items = await resource.list(registry_type="DICOM")

        assert items == [{"id": "d1"}]
        assert route.called

    async def test_list_omits_none(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/registries", params={"registry_type": "SII"}).mock(
            return_value=httpx.Response(200, json={"data": [], "next": None})
        )
        resource = AsyncRegistriesResource(async_client)

        await resource.list(registry_type="SII")

        assert route.called
        query = route.calls.last.request.url.query.decode()
        assert "limit" not in query
        assert "registry_type=SII" in query

    async def test_list_with_limit(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/registries", params={"limit": "3"}).mock(
            return_value=httpx.Response(200, json={"data": [], "next": None})
        )
        resource = AsyncRegistriesResource(async_client)

        assert await resource.list(limit=3) == []
        assert route.called

    async def test_get_by_id(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/registries/reg_z").mock(
            return_value=httpx.Response(200, json={"id": "reg_z", "type": "CMF"})
        )
        resource = AsyncRegistriesResource(async_client)

        assert await resource.get("reg_z") == {"id": "reg_z", "type": "CMF"}

    async def test_get_404_raises_cerberus_api_error(
        self,
        async_client: AsyncCerberusClient,
        respx_mock: respx.MockRouter,
        problem_json: Any,
    ) -> None:
        respx_mock.get("/registries/missing").mock(
            return_value=httpx.Response(
                404,
                json=problem_json(status=404, title="Not Found"),
                headers={"content-type": "application/problem+json"},
            )
        )
        resource = AsyncRegistriesResource(async_client)

        with pytest.raises(CerberusAPIError) as excinfo:
            await resource.get("missing")

        assert excinfo.value.status == 404

    async def test_lookup_rut_normalizes_dots_hyphens(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/registries/lookup/rut/12345678-5").mock(
            return_value=httpx.Response(200, json={"rut": "12345678-5"})
        )
        resource = AsyncRegistriesResource(async_client)

        assert await resource.lookup_rut("12.345.678-5") == {"rut": "12345678-5"}
        assert route.called

    async def test_lookup_rut_uppercases_k(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/registries/lookup/rut/12345678-K").mock(
            return_value=httpx.Response(200, json={"rut": "12345678-K"})
        )
        resource = AsyncRegistriesResource(async_client)

        assert await resource.lookup_rut("12.345.678-k") == {"rut": "12345678-K"}
        assert route.called

    async def test_lookup_rut_strips_whitespace(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/registries/lookup/rut/12345678-5").mock(
            return_value=httpx.Response(200, json={"rut": "12345678-5"})
        )
        resource = AsyncRegistriesResource(async_client)

        await resource.lookup_rut(" 12345678-5 ")

        assert route.called

    async def test_lookup_rut_invalid_empty_raises(self, async_client: AsyncCerberusClient) -> None:
        resource = AsyncRegistriesResource(async_client)

        with pytest.raises(ValueError, match="invalid RUT"):
            await resource.lookup_rut("")

    async def test_lookup_rut_invalid_non_alnum_raises(
        self, async_client: AsyncCerberusClient
    ) -> None:
        resource = AsyncRegistriesResource(async_client)

        with pytest.raises(ValueError, match="invalid RUT"):
            await resource.lookup_rut("abc!@#")

    async def test_iter_all_paginates_forwards_filters(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        # Specific route first.
        respx_mock.get("/registries", params={"registry_type": "Conservador", "cursor": "n2"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": "c2"}], "next": None})
        )
        respx_mock.get("/registries", params={"registry_type": "Conservador"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": "c1"}], "next": "n2"})
        )
        resource = AsyncRegistriesResource(async_client)

        collected: list[dict[str, Any]] = []
        async for item in resource.iter_all(registry_type="Conservador"):
            collected.append(item)

        assert collected == [{"id": "c1"}, {"id": "c2"}]

    async def test_iter_all_drops_none_filters(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/registries", params={"registry_type": "CMF"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": "r1"}], "next": None})
        )
        resource = AsyncRegistriesResource(async_client)

        collected: list[dict[str, Any]] = []
        async for item in resource.iter_all(registry_type="CMF", limit=None):
            collected.append(item)

        assert collected == [{"id": "r1"}]
        assert route.called
        query = route.calls.last.request.url.query.decode()
        assert "limit" not in query

    async def test_iter_all_stops_on_null_next(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/registries").mock(
            return_value=httpx.Response(200, json={"data": [{"id": "x"}], "next": None})
        )
        resource = AsyncRegistriesResource(async_client)

        collected: list[dict[str, Any]] = []
        async for item in resource.iter_all():
            collected.append(item)

        assert collected == [{"id": "x"}]
        assert route.call_count == 1
