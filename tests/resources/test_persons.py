"""Tests for :mod:`cerberus_compliance.resources.persons`.

Post-v0.2.0 the ``/persons`` collection + detail endpoints never shipped
on the prod API; only ``/v1/persons/{rut}/regulatory-profile`` is real.
:class:`PersonsResource` therefore behaves as a partial deprecation shim
(same pattern as :mod:`cerberus_compliance.resources.registries`):

- Constructor emits a single :class:`DeprecationWarning`.
- :meth:`list` / :meth:`get` / :meth:`iter_all` raise
  :class:`NotImplementedError` with a migration message pointing at
  :meth:`regulatory_profile` and :meth:`EntitiesResource.directors`.
- :meth:`regulatory_profile` keeps working — it's the only real endpoint
  in the family and still percent-encodes its path segment.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource
from cerberus_compliance.resources.persons import AsyncPersonsResource, PersonsResource


class TestPersonsClassMeta:
    def test_path_prefix_is_persons(self) -> None:
        assert PersonsResource._path_prefix == "/persons"
        assert AsyncPersonsResource._path_prefix == "/persons"

    def test_is_subclass_of_base_resource(self) -> None:
        assert issubclass(PersonsResource, BaseResource)
        assert issubclass(AsyncPersonsResource, AsyncBaseResource)


# ---------------------------------------------------------------------------
# Sync deprecation semantics
# ---------------------------------------------------------------------------


class TestSyncPersonsDeprecation:
    def test_constructor_emits_deprecation_warning(self, sync_client: CerberusClient) -> None:
        with pytest.warns(DeprecationWarning, match="client.persons.list and client.persons.get"):
            PersonsResource(sync_client)

    def test_list_raises_not_implemented(self, sync_client: CerberusClient) -> None:
        with pytest.warns(DeprecationWarning, match="deprecated"):
            resource = PersonsResource(sync_client)
        with pytest.raises(NotImplementedError, match=r"is not a real API endpoint"):
            resource.list()

    def test_list_with_filters_still_raises(self, sync_client: CerberusClient) -> None:
        with pytest.warns(DeprecationWarning, match="deprecated"):
            resource = PersonsResource(sync_client)
        with pytest.raises(NotImplementedError, match=r"Will be removed in v0\.3\.0"):
            resource.list(rut="7890123-4", limit=5)

    def test_get_raises_not_implemented(self, sync_client: CerberusClient) -> None:
        with pytest.warns(DeprecationWarning, match="deprecated"):
            resource = PersonsResource(sync_client)
        with pytest.raises(NotImplementedError, match=r"regulatory_profile"):
            resource.get("7890123-4")

    def test_iter_all_raises_not_implemented(self, sync_client: CerberusClient) -> None:
        with pytest.warns(DeprecationWarning, match="deprecated"):
            resource = PersonsResource(sync_client)
        with pytest.raises(NotImplementedError):
            resource.iter_all()


# ---------------------------------------------------------------------------
# regulatory_profile (only real endpoint) — sync
# ---------------------------------------------------------------------------


class TestSyncPersonsRegulatoryProfile:
    def test_regulatory_profile_returns_dict(
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
        with pytest.warns(DeprecationWarning, match="deprecated"):
            resource = PersonsResource(sync_client)
        assert resource.regulatory_profile("7890123-4") == profile
        assert route.called

    def test_path_traversal_id_is_percent_encoded(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        """User-supplied id_ containing '../' must be percent-encoded, not traversed."""
        route = respx_mock.get("/persons/..%2Fadmin/regulatory-profile").mock(
            return_value=httpx.Response(200, json={"pep": False})
        )
        with pytest.warns(DeprecationWarning, match="deprecated"):
            resource = PersonsResource(sync_client)
        result = resource.regulatory_profile("../admin")
        assert result == {"pep": False}
        assert route.called


# ---------------------------------------------------------------------------
# Async deprecation semantics
# ---------------------------------------------------------------------------


class TestAsyncPersonsDeprecation:
    async def test_constructor_emits_deprecation_warning(
        self, async_client: AsyncCerberusClient
    ) -> None:
        with pytest.warns(DeprecationWarning, match="client.persons.list and client.persons.get"):
            AsyncPersonsResource(async_client)

    async def test_list_raises_not_implemented(self, async_client: AsyncCerberusClient) -> None:
        with pytest.warns(DeprecationWarning, match="deprecated"):
            resource = AsyncPersonsResource(async_client)
        with pytest.raises(NotImplementedError, match=r"is not a real API endpoint"):
            await resource.list()

    async def test_get_raises_not_implemented(self, async_client: AsyncCerberusClient) -> None:
        with pytest.warns(DeprecationWarning, match="deprecated"):
            resource = AsyncPersonsResource(async_client)
        with pytest.raises(NotImplementedError):
            await resource.get("7890123-4")

    async def test_iter_all_raises_not_implemented(self, async_client: AsyncCerberusClient) -> None:
        with pytest.warns(DeprecationWarning, match="deprecated"):
            resource = AsyncPersonsResource(async_client)
        with pytest.raises(NotImplementedError):
            # Plain non-async method raises immediately before returning iterator.
            resource.iter_all()


class TestAsyncPersonsRegulatoryProfile:
    async def test_regulatory_profile_returns_dict(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        profile = {"pep": False, "score": 7, "watchlists": []}
        respx_mock.get("/persons/7890123-4/regulatory-profile").mock(
            return_value=httpx.Response(200, json=profile)
        )
        with pytest.warns(DeprecationWarning, match="deprecated"):
            resource = AsyncPersonsResource(async_client)
        assert await resource.regulatory_profile("7890123-4") == profile

    async def test_path_traversal_id_is_percent_encoded(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        """User-supplied id_ containing '../' must be percent-encoded, not traversed."""
        route = respx_mock.get("/persons/..%2Fadmin/regulatory-profile").mock(
            return_value=httpx.Response(200, json={"pep": False})
        )
        with pytest.warns(DeprecationWarning, match="deprecated"):
            resource = AsyncPersonsResource(async_client)
        result = await resource.regulatory_profile("../admin")
        assert result == {"pep": False}
        assert route.called
