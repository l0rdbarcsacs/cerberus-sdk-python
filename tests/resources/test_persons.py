"""Tests for :mod:`cerberus_compliance.resources.persons`.

Two real prod endpoints are wrapped:

- ``GET /v1/persons`` — paginated PEP-lite listing wrapped by
  :meth:`PersonsResource.list` and :meth:`PersonsResource.iter_all`.
- ``GET /v1/persons/{rut}/regulatory-profile`` — single-document
  compliance profile wrapped by :meth:`PersonsResource.regulatory_profile`.

The legacy ``GET /v1/persons/{id}`` detail endpoint never shipped on
the prod API, so :meth:`PersonsResource.get` is preserved as a
deprecation shim that emits a :class:`DeprecationWarning` *on first
call* (not on construction) and raises :class:`NotImplementedError`.
"""

from __future__ import annotations

import warnings
from typing import Any

import httpx
import pytest
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.errors import CerberusAPIError, NotFoundError
from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource
from cerberus_compliance.resources.persons import AsyncPersonsResource, PersonsResource
from cerberus_compliance.retry import RetryConfig


class TestPersonsClassMeta:
    def test_path_prefix_is_persons(self) -> None:
        assert PersonsResource._path_prefix == "/persons"
        assert AsyncPersonsResource._path_prefix == "/persons"

    def test_is_subclass_of_base_resource(self) -> None:
        assert issubclass(PersonsResource, BaseResource)
        assert issubclass(AsyncPersonsResource, AsyncBaseResource)


# ---------------------------------------------------------------------------
# Construction silence
# ---------------------------------------------------------------------------


class TestPersonsConstructionIsSilent:
    def test_sync_resource_construction_is_silent(self, sync_client: CerberusClient) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            PersonsResource(sync_client)

    async def test_async_resource_construction_is_silent(
        self, async_client: AsyncCerberusClient
    ) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            AsyncPersonsResource(async_client)


# ---------------------------------------------------------------------------
# Sync deprecation semantics — only ``get`` remains a shim post-v0.5.0.
# ---------------------------------------------------------------------------


class TestSyncPersonsDeprecation:
    def test_get_warns_and_raises_not_implemented(self, sync_client: CerberusClient) -> None:
        resource = PersonsResource(sync_client)
        with (
            pytest.warns(DeprecationWarning, match="deprecated"),
            pytest.raises(NotImplementedError, match=r"regulatory_profile"),
        ):
            resource.get("7890123-4")


# ---------------------------------------------------------------------------
# regulatory_profile (only real entity-detail endpoint) — sync. MUST NOT warn.
# ---------------------------------------------------------------------------


class TestSyncPersonsRegulatoryProfile:
    def test_regulatory_profile_returns_dict_without_warning(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        profile = {
            "pep": True,
            "score": 42,
            "watchlists": ["OFAC"],
            "last_reviewed_at": "2026-04-01T12:00:00Z",
        }
        route = respx_mock.get("/persons/7890123-4/regulatory-profile").mock(
            return_value=httpx.Response(200, json=profile)
        )
        resource = PersonsResource(sync_client)
        # Live endpoint: no warning allowed.
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            assert resource.regulatory_profile("7890123-4") == profile
        assert route.called

    def test_path_traversal_id_is_percent_encoded(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        """User-supplied id_ containing '../' must be percent-encoded, not traversed."""
        route = respx_mock.get("/persons/..%2Fadmin/regulatory-profile").mock(
            return_value=httpx.Response(200, json={"pep": False})
        )
        resource = PersonsResource(sync_client)
        result = resource.regulatory_profile("../admin")
        assert result == {"pep": False}
        assert route.called


# ---------------------------------------------------------------------------
# Sync ``list`` + ``iter_all`` — paginated PEP-lite listing
# ---------------------------------------------------------------------------


class TestSyncPersonsList:
    def test_list_no_filters_emits_bare_url(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/persons").mock(
            return_value=httpx.Response(
                200,
                json={
                    "persons": [{"rut": "7890123-4"}, {"rut": "10000000-0"}],
                    "next_cursor": None,
                    "has_more": False,
                },
            )
        )
        resource = PersonsResource(sync_client)
        page = resource.list()
        assert page["persons"] == [{"rut": "7890123-4"}, {"rut": "10000000-0"}]
        assert page["has_more"] is False
        assert route.called
        # No filters supplied → no query string at all.
        assert route.calls.last.request.url.query == b""

    def test_list_pep_true_serialises_lower_case(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/persons", params={"pep": "true"}).mock(
            return_value=httpx.Response(
                200, json={"persons": [], "next_cursor": None, "has_more": False}
            )
        )
        resource = PersonsResource(sync_client)
        resource.list(pep=True)
        assert route.called
        params = dict(route.calls.last.request.url.params.multi_items())
        assert params == {"pep": "true"}

    def test_list_pep_false_serialised_explicitly(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/persons", params={"pep": "false"}).mock(
            return_value=httpx.Response(
                200, json={"persons": [], "next_cursor": None, "has_more": False}
            )
        )
        resource = PersonsResource(sync_client)
        resource.list(pep=False)
        params = dict(route.calls.last.request.url.params.multi_items())
        assert params == {"pep": "false"}

    def test_list_drops_none_filters(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/persons", params={"cargo": "Director"}).mock(
            return_value=httpx.Response(
                200, json={"persons": [], "next_cursor": None, "has_more": False}
            )
        )
        resource = PersonsResource(sync_client)
        resource.list(cargo="Director", pep=None, entity_kind=None, limit=None)
        assert route.called
        params = dict(route.calls.last.request.url.params.multi_items())
        assert params == {"cargo": "Director"}

    def test_list_all_filters_forwarded(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/persons").mock(
            return_value=httpx.Response(
                200,
                json={"persons": [{"rut": "7"}], "next_cursor": None, "has_more": False},
            )
        )
        resource = PersonsResource(sync_client)
        out = resource.list(
            pep=True,
            cargo="Gerente General",
            entity_kind="banco",
            limit=25,
        )
        assert out["persons"] == [{"rut": "7"}]
        params = dict(route.calls.last.request.url.params.multi_items())
        assert params == {
            "pep": "true",
            "cargo": "Gerente General",
            "entity_kind": "banco",
            "limit": "25",
        }

    def test_list_propagates_401(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/persons").mock(
            return_value=httpx.Response(
                401,
                json={"title": "Unauthorized", "status": 401},
            )
        )
        resource = PersonsResource(sync_client)
        with pytest.raises(CerberusAPIError) as exc:
            resource.list()
        assert exc.value.status == 401

    def test_list_propagates_404(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/persons").mock(
            return_value=httpx.Response(
                404,
                json={"title": "Not Found", "status": 404},
            )
        )
        resource = PersonsResource(sync_client)
        with pytest.raises(NotFoundError):
            resource.list()


class TestSyncPersonsIterAll:
    def test_iter_all_paginates_two_pages(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        # Specific cursor route registered FIRST so the dispatcher hits it
        # before the bare subset match.
        page2 = respx_mock.get("/persons", params={"cursor": "tok2"}).mock(
            return_value=httpx.Response(
                200,
                json={
                    "persons": [{"rut": "9999999-9"}],
                    "next_cursor": None,
                    "has_more": False,
                },
            )
        )
        page1 = respx_mock.get("/persons", params={}).mock(
            return_value=httpx.Response(
                200,
                json={
                    "persons": [{"rut": "7890123-4"}],
                    "next_cursor": "tok2",
                    "has_more": True,
                },
            )
        )
        resource = PersonsResource(sync_client)
        items = list(resource.iter_all())
        assert items == [{"rut": "7890123-4"}, {"rut": "9999999-9"}]
        assert page1.called
        assert page2.called
        # First page must NOT carry a cursor.
        assert page1.calls[0].request.url.query == b""

    def test_iter_all_forwards_filters_each_page(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        page2 = respx_mock.get("/persons", params={"pep": "true", "cursor": "n2"}).mock(
            return_value=httpx.Response(
                200,
                json={"persons": [{"rut": "b"}], "next_cursor": None, "has_more": False},
            )
        )
        page1 = respx_mock.get("/persons", params={"pep": "true"}).mock(
            return_value=httpx.Response(
                200,
                json={"persons": [{"rut": "a"}], "next_cursor": "n2", "has_more": True},
            )
        )
        resource = PersonsResource(sync_client)
        out = list(resource.iter_all(pep=True))
        assert out == [{"rut": "a"}, {"rut": "b"}]
        assert page1.called
        assert page2.called
        # First-page URL must contain the filter but no cursor.
        first_params = dict(page1.calls[0].request.url.params.multi_items())
        assert first_params == {"pep": "true"}

    def test_iter_all_stops_when_has_more_false(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/persons").mock(
            return_value=httpx.Response(
                200,
                json={
                    "persons": [{"rut": "only"}],
                    "next_cursor": "would-be-next",
                    "has_more": False,
                },
            )
        )
        resource = PersonsResource(sync_client)
        # ``has_more=False`` must terminate iteration even when the server
        # leaks a stale ``next_cursor``.
        assert list(resource.iter_all()) == [{"rut": "only"}]


# ---------------------------------------------------------------------------
# Async deprecation semantics — only ``get`` remains a shim.
# ---------------------------------------------------------------------------


class TestAsyncPersonsDeprecation:
    async def test_get_warns_and_raises_not_implemented(
        self, async_client: AsyncCerberusClient
    ) -> None:
        resource = AsyncPersonsResource(async_client)
        with (
            pytest.warns(DeprecationWarning, match="deprecated"),
            pytest.raises(NotImplementedError),
        ):
            await resource.get("7890123-4")


class TestAsyncPersonsRegulatoryProfile:
    async def test_regulatory_profile_returns_dict_without_warning(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        profile = {"pep": False, "score": 7, "watchlists": []}
        respx_mock.get("/persons/7890123-4/regulatory-profile").mock(
            return_value=httpx.Response(200, json=profile)
        )
        resource = AsyncPersonsResource(async_client)
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            assert await resource.regulatory_profile("7890123-4") == profile

    async def test_path_traversal_id_is_percent_encoded(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        """User-supplied id_ containing '../' must be percent-encoded, not traversed."""
        route = respx_mock.get("/persons/..%2Fadmin/regulatory-profile").mock(
            return_value=httpx.Response(200, json={"pep": False})
        )
        resource = AsyncPersonsResource(async_client)
        result = await resource.regulatory_profile("../admin")
        assert result == {"pep": False}
        assert route.called


# ---------------------------------------------------------------------------
# Async ``list`` + ``iter_all`` mirrors
# ---------------------------------------------------------------------------


class TestAsyncPersonsList:
    async def test_list_no_filters(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/persons").mock(
            return_value=httpx.Response(
                200,
                json={
                    "persons": [{"rut": "x"}],
                    "next_cursor": None,
                    "has_more": False,
                },
            )
        )
        resource = AsyncPersonsResource(async_client)
        page = await resource.list()
        assert page["persons"] == [{"rut": "x"}]
        assert route.calls.last.request.url.query == b""

    async def test_list_with_all_filters(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/persons").mock(
            return_value=httpx.Response(
                200,
                json={"persons": [{"rut": "z"}], "next_cursor": None, "has_more": False},
            )
        )
        resource = AsyncPersonsResource(async_client)
        await resource.list(
            pep=False,
            cargo="Director",
            entity_kind="emisor",
            limit=10,
        )
        params = dict(route.calls.last.request.url.params.multi_items())
        assert params == {
            "pep": "false",
            "cargo": "Director",
            "entity_kind": "emisor",
            "limit": "10",
        }

    async def test_list_429_surfaces_rate_limit(
        self, api_key: str, base_url: str, respx_mock: respx.MockRouter
    ) -> None:
        from cerberus_compliance.errors import RateLimitError

        client = AsyncCerberusClient(
            api_key=api_key,
            base_url=base_url,
            timeout=2.0,
            retry=RetryConfig(max_attempts=1, base_delay_ms=1),
        )
        try:
            respx_mock.get("/persons").mock(
                return_value=httpx.Response(
                    429,
                    headers={"retry-after": "1"},
                    json={"title": "Too Many Requests", "status": 429},
                )
            )
            resource = AsyncPersonsResource(client)
            with pytest.raises(RateLimitError):
                await resource.list()
        finally:
            await client.close()


class TestAsyncPersonsIterAll:
    async def test_iter_all_paginates_two_pages(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/persons", params={"cursor": "p2"}).mock(
            return_value=httpx.Response(
                200,
                json={"persons": [{"rut": "b"}], "next_cursor": None, "has_more": False},
            )
        )
        first_route = respx_mock.get("/persons", params={}).mock(
            return_value=httpx.Response(
                200,
                json={"persons": [{"rut": "a"}], "next_cursor": "p2", "has_more": True},
            )
        )
        resource = AsyncPersonsResource(async_client)
        collected: list[dict[str, Any]] = []
        async for item in resource.iter_all():
            collected.append(item)
        assert collected == [{"rut": "a"}, {"rut": "b"}]
        # First-page request must not carry a cursor.
        assert first_route.calls[0].request.url.query == b""

    async def test_iter_all_forwards_filters(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/persons", params={"pep": "true", "cursor": "n2"}).mock(
            return_value=httpx.Response(
                200,
                json={"persons": [{"rut": "b"}], "next_cursor": None, "has_more": False},
            )
        )
        respx_mock.get("/persons", params={"pep": "true"}).mock(
            return_value=httpx.Response(
                200,
                json={"persons": [{"rut": "a"}], "next_cursor": "n2", "has_more": True},
            )
        )
        resource = AsyncPersonsResource(async_client)
        collected: list[dict[str, Any]] = []
        async for item in resource.iter_all(pep=True):
            collected.append(item)
        assert collected == [{"rut": "a"}, {"rut": "b"}]
