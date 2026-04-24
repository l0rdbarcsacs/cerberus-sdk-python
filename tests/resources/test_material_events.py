"""Deprecation tests for ``cerberus_compliance.resources.material_events``.

Post-v0.2.0 the module is a deprecated shim (G3).

**Deprecation semantics (tightened in the v0.2.0 post-PR review):**

- Construction is silent: neither ``MaterialEventsResource`` nor the
  parent ``CerberusClient`` emit a :class:`DeprecationWarning` on
  instantiation.
- Every deprecated method — :meth:`list`, :meth:`get`, :meth:`iter_all`
  — emits a :class:`DeprecationWarning` *when called* and then raises
  :class:`NotImplementedError` with the migration recipe
  (``client.entities.get(id)["hechos_esenciales"]`` or
  ``client.kyb.get(rut, include=["material_events"])``).
"""

from __future__ import annotations

import warnings

import pytest

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource
from cerberus_compliance.resources.material_events import (
    AsyncMaterialEventsResource,
    MaterialEventsResource,
)


class TestMaterialEventsMeta:
    def test_path_prefix(self) -> None:
        assert MaterialEventsResource._path_prefix == "/material-events"
        assert AsyncMaterialEventsResource._path_prefix == "/material-events"

    def test_subclasses(self) -> None:
        assert issubclass(MaterialEventsResource, BaseResource)
        assert issubclass(AsyncMaterialEventsResource, AsyncBaseResource)


class TestMaterialEventsConstructionIsSilent:
    def test_sync_resource_construction_is_silent(self, sync_client: CerberusClient) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            MaterialEventsResource(sync_client)

    async def test_async_resource_construction_is_silent(
        self, async_client: AsyncCerberusClient
    ) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            AsyncMaterialEventsResource(async_client)


class TestMaterialEventsDeprecation:
    def test_list_warns_and_raises_not_implemented(self, sync_client: CerberusClient) -> None:
        resource = MaterialEventsResource(sync_client)
        with (
            pytest.warns(DeprecationWarning, match="client.material_events is deprecated"),
            pytest.raises(NotImplementedError, match="hechos_esenciales"),
        ):
            resource.list()

    def test_get_warns_and_raises_not_implemented(self, sync_client: CerberusClient) -> None:
        resource = MaterialEventsResource(sync_client)
        with (
            pytest.warns(DeprecationWarning, match="client.material_events is deprecated"),
            pytest.raises(NotImplementedError, match=r"client\.entities\.get"),
        ):
            resource.get("me_1")

    def test_iter_all_warns_and_raises_not_implemented(self, sync_client: CerberusClient) -> None:
        resource = MaterialEventsResource(sync_client)
        with (
            pytest.warns(DeprecationWarning, match="client.material_events is deprecated"),
            pytest.raises(NotImplementedError),
        ):
            list(resource.iter_all())


class TestAsyncMaterialEventsDeprecation:
    async def test_list_warns_and_raises_not_implemented(
        self, async_client: AsyncCerberusClient
    ) -> None:
        resource = AsyncMaterialEventsResource(async_client)
        with (
            pytest.warns(DeprecationWarning, match="client.material_events is deprecated"),
            pytest.raises(NotImplementedError),
        ):
            await resource.list()

    async def test_get_warns_and_raises_not_implemented(
        self, async_client: AsyncCerberusClient
    ) -> None:
        resource = AsyncMaterialEventsResource(async_client)
        with (
            pytest.warns(DeprecationWarning, match="client.material_events is deprecated"),
            pytest.raises(NotImplementedError),
        ):
            await resource.get("me_1")

    async def test_iter_all_warns_and_raises_not_implemented(
        self, async_client: AsyncCerberusClient
    ) -> None:
        resource = AsyncMaterialEventsResource(async_client)
        with (
            pytest.warns(DeprecationWarning, match="client.material_events is deprecated"),
            pytest.raises(NotImplementedError),
        ):
            resource.iter_all()
