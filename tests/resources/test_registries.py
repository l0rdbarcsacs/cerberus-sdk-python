"""Deprecation tests for ``cerberus_compliance.resources.registries``.

Post-v0.2.0 ``/registries`` is a deprecated compatibility shim (G3). The
constructor emits a single :class:`DeprecationWarning`. :meth:`list` /
:meth:`get` / :meth:`iter_all` raise :class:`NotImplementedError` with a
migration message. :meth:`lookup_rut` still works but emits a warning
and internally calls ``GET /entities/by-rut/{rut}``.
"""

from __future__ import annotations

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


class TestRegistriesDeprecation:
    def test_constructor_emits_deprecation_warning(self, sync_client: CerberusClient) -> None:
        with pytest.warns(DeprecationWarning, match="client.registries is deprecated"):
            RegistriesResource(sync_client)

    def test_list_raises_not_implemented(self, sync_client: CerberusClient) -> None:
        with pytest.warns(DeprecationWarning, match="is deprecated"):
            resource = RegistriesResource(sync_client)
        with pytest.raises(NotImplementedError, match=r"[Rr]emoved in v0\.3\.0"):
            resource.list()

    def test_get_raises_not_implemented(self, sync_client: CerberusClient) -> None:
        with pytest.warns(DeprecationWarning, match="is deprecated"):
            resource = RegistriesResource(sync_client)
        with pytest.raises(NotImplementedError, match=r"client\.entities\.by_rut"):
            resource.get("reg_1")

    def test_iter_all_raises_not_implemented(self, sync_client: CerberusClient) -> None:
        with pytest.warns(DeprecationWarning, match="is deprecated"):
            resource = RegistriesResource(sync_client)
        with pytest.raises(NotImplementedError):
            list(resource.iter_all())

    def test_lookup_rut_emits_warning_and_redirects_to_entities_by_rut(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        """lookup_rut must warn and internally hit /entities/by-rut/{rut}."""
        route = respx_mock.get("/entities/by-rut/96505760-9").mock(
            return_value=httpx.Response(200, json={"id": "ent_1"})
        )
        with pytest.warns(DeprecationWarning, match="is deprecated"):
            resource = RegistriesResource(sync_client)
        with pytest.warns(DeprecationWarning, match=r"use client\.entities\.by_rut"):
            result = resource.lookup_rut("96.505.760-9")
        assert result == {"id": "ent_1"}
        assert route.called

    def test_lookup_rut_invalid_raises_value_error(self, sync_client: CerberusClient) -> None:
        with pytest.warns(DeprecationWarning, match="is deprecated"):
            resource = RegistriesResource(sync_client)
        with pytest.raises(ValueError, match="invalid RUT"):
            resource.lookup_rut("")


class TestAsyncRegistriesDeprecation:
    async def test_constructor_emits_deprecation_warning(
        self, async_client: AsyncCerberusClient
    ) -> None:
        with pytest.warns(DeprecationWarning, match="client.registries is deprecated"):
            AsyncRegistriesResource(async_client)

    async def test_list_raises_not_implemented(self, async_client: AsyncCerberusClient) -> None:
        with pytest.warns(DeprecationWarning, match="is deprecated"):
            resource = AsyncRegistriesResource(async_client)
        with pytest.raises(NotImplementedError):
            await resource.list()

    async def test_get_raises_not_implemented(self, async_client: AsyncCerberusClient) -> None:
        with pytest.warns(DeprecationWarning, match="is deprecated"):
            resource = AsyncRegistriesResource(async_client)
        with pytest.raises(NotImplementedError):
            await resource.get("reg_1")

    async def test_iter_all_raises_not_implemented(self, async_client: AsyncCerberusClient) -> None:
        with pytest.warns(DeprecationWarning, match="is deprecated"):
            resource = AsyncRegistriesResource(async_client)
        with pytest.raises(NotImplementedError):
            # Plain non-async method raises immediately before returning iterator.
            resource.iter_all()

    async def test_lookup_rut_emits_warning_and_redirects(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/entities/by-rut/96505760-9").mock(
            return_value=httpx.Response(200, json={"id": "ent_1"})
        )
        with pytest.warns(DeprecationWarning, match="is deprecated"):
            resource = AsyncRegistriesResource(async_client)
        with pytest.warns(DeprecationWarning, match=r"use client\.entities\.by_rut"):
            result = await resource.lookup_rut("96.505.760-9")
        assert result == {"id": "ent_1"}
