"""Deprecation tests for ``cerberus_compliance.resources.registries``.

Post-v0.2.0 ``/registries`` is a deprecated compatibility shim (G3).

**Deprecation semantics (tightened in the v0.2.0 post-PR review):**

- Construction is *silent* — instantiating ``RegistriesResource`` (or
  the parent ``CerberusClient``, which constructs one eagerly) does not
  emit any :class:`DeprecationWarning`. This spares downstream SDK
  users from noisy import-time warnings they can't do anything about.
- Every deprecated method — :meth:`list` / :meth:`get` /
  :meth:`iter_all` and :meth:`lookup_rut` — emits a
  :class:`DeprecationWarning` *when called*.
- :meth:`list` / :meth:`get` / :meth:`iter_all` then raise
  :class:`NotImplementedError` with a migration message.
- :meth:`lookup_rut` keeps working: warn, then proxy to
  ``GET /entities/by-rut/{rut}``.
"""

from __future__ import annotations

import warnings

import httpx
import pytest
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource
from cerberus_compliance.resources.registries import (
    AsyncRegistriesResource,
    RegistriesResource,
)


class TestRegistriesClassMeta:
    def test_path_prefix_is_registries(self) -> None:
        assert RegistriesResource._path_prefix == "/registries"
        assert AsyncRegistriesResource._path_prefix == "/registries"

    def test_is_subclass_of_base_resource(self) -> None:
        assert issubclass(RegistriesResource, BaseResource)
        assert issubclass(AsyncRegistriesResource, AsyncBaseResource)


class TestRegistriesConstructionIsSilent:
    """Constructing the shim must NOT emit a ``DeprecationWarning``.

    Partner SDK users get a ``RegistriesResource`` eagerly wired inside
    every ``CerberusClient()``; emitting a warning there would spam
    every caller on import, even ones who never touch the shim.
    """

    def test_sync_resource_construction_is_silent(self, sync_client: CerberusClient) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("error")  # any warning -> raise
            RegistriesResource(sync_client)

    async def test_async_resource_construction_is_silent(
        self, async_client: AsyncCerberusClient
    ) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            AsyncRegistriesResource(async_client)

    def test_cerberus_client_construction_is_silent(self) -> None:
        """The user-facing observation: ``CerberusClient()`` must not warn."""
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            client = CerberusClient(api_key="ck_test_silent", base_url="https://mock.test/v1")
        client.close()


class TestRegistriesDeprecation:
    def test_list_warns_and_raises_not_implemented(self, sync_client: CerberusClient) -> None:
        resource = RegistriesResource(sync_client)
        with (
            pytest.warns(DeprecationWarning, match="client.registries is deprecated"),
            pytest.raises(NotImplementedError, match=r"[Rr]emoved in v0\.3\.0"),
        ):
            resource.list()

    def test_get_warns_and_raises_not_implemented(self, sync_client: CerberusClient) -> None:
        resource = RegistriesResource(sync_client)
        with (
            pytest.warns(DeprecationWarning, match="client.registries is deprecated"),
            pytest.raises(NotImplementedError, match=r"client\.entities\.by_rut"),
        ):
            resource.get("reg_1")

    def test_iter_all_warns_and_raises_not_implemented(self, sync_client: CerberusClient) -> None:
        resource = RegistriesResource(sync_client)
        with (
            pytest.warns(DeprecationWarning, match="client.registries is deprecated"),
            pytest.raises(NotImplementedError),
        ):
            list(resource.iter_all())

    def test_lookup_rut_emits_warning_and_redirects_to_entities_by_rut(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        """lookup_rut must warn and internally hit /entities/by-rut/{rut}."""
        route = respx_mock.get("/entities/by-rut/96505760-9").mock(
            return_value=httpx.Response(200, json={"id": "ent_1"})
        )
        resource = RegistriesResource(sync_client)
        with pytest.warns(DeprecationWarning, match=r"use client\.entities\.by_rut"):
            result = resource.lookup_rut("96.505.760-9")
        assert result == {"id": "ent_1"}
        assert route.called

    def test_lookup_rut_invalid_raises_value_error(self, sync_client: CerberusClient) -> None:
        resource = RegistriesResource(sync_client)
        with (
            pytest.warns(DeprecationWarning, match="is deprecated"),
            pytest.raises(ValueError, match="invalid RUT"),
        ):
            resource.lookup_rut("")


class TestAsyncRegistriesDeprecation:
    async def test_list_warns_and_raises_not_implemented(
        self, async_client: AsyncCerberusClient
    ) -> None:
        resource = AsyncRegistriesResource(async_client)
        with (
            pytest.warns(DeprecationWarning, match="client.registries is deprecated"),
            pytest.raises(NotImplementedError),
        ):
            await resource.list()

    async def test_get_warns_and_raises_not_implemented(
        self, async_client: AsyncCerberusClient
    ) -> None:
        resource = AsyncRegistriesResource(async_client)
        with (
            pytest.warns(DeprecationWarning, match="client.registries is deprecated"),
            pytest.raises(NotImplementedError),
        ):
            await resource.get("reg_1")

    async def test_iter_all_warns_and_raises_not_implemented(
        self, async_client: AsyncCerberusClient
    ) -> None:
        resource = AsyncRegistriesResource(async_client)
        with (
            pytest.warns(DeprecationWarning, match="client.registries is deprecated"),
            pytest.raises(NotImplementedError),
        ):
            # Plain non-async method raises immediately before returning iterator.
            resource.iter_all()

    async def test_lookup_rut_emits_warning_and_redirects(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/entities/by-rut/96505760-9").mock(
            return_value=httpx.Response(200, json={"id": "ent_1"})
        )
        resource = AsyncRegistriesResource(async_client)
        with pytest.warns(DeprecationWarning, match=r"use client\.entities\.by_rut"):
            result = await resource.lookup_rut("96.505.760-9")
        assert result == {"id": "ent_1"}
