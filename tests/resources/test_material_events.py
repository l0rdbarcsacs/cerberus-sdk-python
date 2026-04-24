"""Deprecation tests for ``cerberus_compliance.resources.material_events``.

Post-v0.2.0 the module is a deprecated shim (G3). Constructor emits a
:class:`DeprecationWarning`; :meth:`list` / :meth:`get` / :meth:`iter_all`
raise :class:`NotImplementedError` pointing at the migration path
(``client.entities.get(id)["hechos_esenciales"]`` or
``client.kyb.get(rut, include=["material_events"])``).
"""

from __future__ import annotations

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


class TestMaterialEventsDeprecation:
    def test_constructor_emits_deprecation_warning(self, sync_client: CerberusClient) -> None:
        with pytest.warns(DeprecationWarning, match="client.material_events is deprecated"):
            MaterialEventsResource(sync_client)

    def test_list_raises_not_implemented_with_migration_hint(
        self, sync_client: CerberusClient
    ) -> None:
        with pytest.warns(DeprecationWarning, match="is deprecated"):
            resource = MaterialEventsResource(sync_client)
        with pytest.raises(NotImplementedError, match="hechos_esenciales"):
            resource.list()

    def test_get_raises_not_implemented(self, sync_client: CerberusClient) -> None:
        with pytest.warns(DeprecationWarning, match="is deprecated"):
            resource = MaterialEventsResource(sync_client)
        with pytest.raises(NotImplementedError, match=r"client\.entities\.get"):
            resource.get("me_1")

    def test_iter_all_raises_not_implemented(self, sync_client: CerberusClient) -> None:
        with pytest.warns(DeprecationWarning, match="is deprecated"):
            resource = MaterialEventsResource(sync_client)
        with pytest.raises(NotImplementedError):
            list(resource.iter_all())


class TestAsyncMaterialEventsDeprecation:
    async def test_constructor_emits_deprecation_warning(
        self, async_client: AsyncCerberusClient
    ) -> None:
        with pytest.warns(DeprecationWarning, match="client.material_events is deprecated"):
            AsyncMaterialEventsResource(async_client)

    async def test_list_raises_not_implemented(self, async_client: AsyncCerberusClient) -> None:
        with pytest.warns(DeprecationWarning, match="is deprecated"):
            resource = AsyncMaterialEventsResource(async_client)
        with pytest.raises(NotImplementedError):
            await resource.list()

    async def test_get_raises_not_implemented(self, async_client: AsyncCerberusClient) -> None:
        with pytest.warns(DeprecationWarning, match="is deprecated"):
            resource = AsyncMaterialEventsResource(async_client)
        with pytest.raises(NotImplementedError):
            await resource.get("me_1")

    async def test_iter_all_raises_not_implemented(self, async_client: AsyncCerberusClient) -> None:
        with pytest.warns(DeprecationWarning, match="is deprecated"):
            resource = AsyncMaterialEventsResource(async_client)
        with pytest.raises(NotImplementedError):
            resource.iter_all()
