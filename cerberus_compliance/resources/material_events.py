"""Deprecated: standalone ``/material-events`` sub-resource.

Prod API ``https://compliance.cerberus.cl/v1`` does not expose a
top-level ``/material-events`` endpoint family. Material events
(``hechos esenciales``) are embedded in the entity profile under the
``hechos_esenciales`` key returned by ``GET /v1/entities/{id}`` and
``GET /v1/kyb/{rut}``. The audit that produced the v0.2.0 plan (G3)
flagged this as a broken SDK surface.

Migration
---------
* Single entity:

  .. code-block:: python

      events = client.entities.get("ent_123")["hechos_esenciales"]

* Rich, point-in-time view:

  .. code-block:: python

      profile = client.kyb.get("96.505.760-9", include=["material_events"])
      events = profile["hechos_esenciales"]

Each deprecated method emits a :class:`DeprecationWarning` *on first
call* (not on construction), so ``CerberusClient()`` stays silent for
partner SDK users who never touch the shim. :meth:`list`, :meth:`get`,
and :meth:`iter_all` raise :class:`NotImplementedError` with the
migration recipe. The module will be removed in v0.3.0.
"""

from __future__ import annotations

import builtins
import warnings
from collections.abc import AsyncIterator, Iterator
from datetime import datetime
from typing import Any

from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource

__all__ = ["AsyncMaterialEventsResource", "MaterialEventsResource"]

_DEPRECATION_MSG = (
    "client.material_events is deprecated and will be removed in v0.3.0. "
    'Use client.entities.get(id)["hechos_esenciales"] or '
    'client.kyb.get(rut, include=["material_events"]) instead. '
    "See CHANGELOG v0.2.0 (G3) for the migration."
)
_REMOVAL_MSG = (
    "client.material_events.{name} is no longer backed by a real endpoint; "
    'use client.entities.get(id)["hechos_esenciales"] or '
    'client.kyb.get(rut, include=["material_events"]) instead. Removed in v0.3.0.'
)


def _warn_deprecated_call(name: str) -> None:
    """Emit the standard per-call :class:`DeprecationWarning` for the shim.

    Factored into a helper so every deprecated method in both the sync
    and async shims uses the exact same message + stacklevel — keeping
    the user-visible warning text stable for downstream filter rules.
    """
    warnings.warn(
        _DEPRECATION_MSG + f" (hit via client.material_events.{name})",
        DeprecationWarning,
        stacklevel=3,
    )


class MaterialEventsResource(BaseResource):
    """Deprecated shim for ``/material-events``. See module docstring."""

    _path_prefix = "/material-events"

    def list(
        self,
        *,
        entity_id: str | None = None,
        since: str | datetime | None = None,
        until: str | datetime | None = None,
        limit: int | None = None,
    ) -> builtins.list[dict[str, Any]]:
        """Deprecated: no-op. Raises :class:`NotImplementedError`.

        Emits a :class:`DeprecationWarning` before raising so callers
        running under ``-W error::DeprecationWarning`` see the warning
        path rather than a naked :class:`NotImplementedError`.
        """
        _warn_deprecated_call("list")
        raise NotImplementedError(_REMOVAL_MSG.format(name="list"))

    def get(self, id_: str) -> dict[str, Any]:
        """Deprecated: no-op. Raises :class:`NotImplementedError`."""
        _warn_deprecated_call("get")
        raise NotImplementedError(_REMOVAL_MSG.format(name="get"))

    def iter_all(self, **filters: Any) -> Iterator[dict[str, Any]]:
        """Deprecated: no-op. Raises :class:`NotImplementedError`."""
        _warn_deprecated_call("iter_all")
        raise NotImplementedError(_REMOVAL_MSG.format(name="iter_all"))


class AsyncMaterialEventsResource(AsyncBaseResource):
    """Deprecated async mirror of :class:`MaterialEventsResource`."""

    _path_prefix = "/material-events"

    async def list(
        self,
        *,
        entity_id: str | None = None,
        since: str | datetime | None = None,
        until: str | datetime | None = None,
        limit: int | None = None,
    ) -> builtins.list[dict[str, Any]]:
        """Deprecated: no-op. Raises :class:`NotImplementedError`."""
        _warn_deprecated_call("list")
        raise NotImplementedError(_REMOVAL_MSG.format(name="list"))

    async def get(self, id_: str) -> dict[str, Any]:
        """Deprecated: no-op. Raises :class:`NotImplementedError`."""
        _warn_deprecated_call("get")
        raise NotImplementedError(_REMOVAL_MSG.format(name="get"))

    def iter_all(self, **filters: Any) -> AsyncIterator[dict[str, Any]]:
        """Deprecated: no-op. Raises :class:`NotImplementedError`."""
        _warn_deprecated_call("iter_all")
        raise NotImplementedError(_REMOVAL_MSG.format(name="iter_all"))
