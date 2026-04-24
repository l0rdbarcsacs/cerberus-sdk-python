"""Deprecated: public Chilean registries sub-resource.

The original ``/registries`` endpoint family never shipped on the prod
Cerberus Compliance API at ``https://compliance.cerberus.cl/v1``. The
audit that produced the v0.2.0 plan (G3) found the SDK was targeting a
fictional namespace; callers should migrate to:

- :meth:`cerberus_compliance.resources.entities.EntitiesResource.by_rut`
  for RUT lookups (``GET /v1/entities/by-rut/{rut}``).
- :attr:`cerberus_compliance.CerberusClient.rpsf` for CMF-regulated
  financial-service registry records.

This module remains in the SDK as a compatibility shim:

- :meth:`RegistriesResource.lookup_rut` still works — it emits a
  :class:`DeprecationWarning` and internally calls ``entities.by_rut``.
- :meth:`RegistriesResource.list` and :meth:`RegistriesResource.get`
  raise :class:`NotImplementedError` with an explicit migration message.
- The constructor emits a single :class:`DeprecationWarning` the first
  time an instance is created, so existing code that never calls a
  method still learns about the deprecation during unit tests.

The module will be removed in v0.3.0.
"""

from __future__ import annotations

import warnings
from collections.abc import AsyncIterator, Iterator
from typing import TYPE_CHECKING, Any, Literal
from urllib.parse import quote

from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource

if TYPE_CHECKING:
    from cerberus_compliance.client import AsyncCerberusClient, CerberusClient

__all__ = ["AsyncRegistriesResource", "RegistriesResource", "RegistryType"]

RegistryType = Literal["CMF", "SII", "DICOM", "Conservador"]

_DEPRECATION_MSG = (
    "client.registries is deprecated and will be removed in v0.2.0+1 (planned v0.3.0). "
    "Use client.entities.by_rut() for RUT lookups, or client.rpsf for CMF registry records. "
    "See CHANGELOG v0.2.0 (G3) for the migration."
)
_REMOVAL_MSG = (
    "client.registries.{name} is no longer backed by a real endpoint; "
    "use client.entities.by_rut() or client.rpsf instead. Removed in v0.3.0."
)


def _normalize_rut(rut: str) -> str:
    """Return the canonical ``<body>-<dv>`` form of ``rut``.

    Retained for backwards compatibility with :meth:`lookup_rut`; the
    canonical form is what ``entities.by_rut`` now hits.
    """
    stripped = "".join(ch for ch in rut if not ch.isspace())
    cleaned = stripped.replace(".", "").replace("-", "")

    if len(cleaned) < 2 or not cleaned.isalnum():
        raise ValueError(f"invalid RUT: {rut!r}")

    body, dv = cleaned[:-1], cleaned[-1].upper()
    if not body.isdigit() or not (dv.isdigit() or dv == "K"):
        raise ValueError(f"invalid RUT: {rut!r}")

    return f"{body}-{dv}"


class RegistriesResource(BaseResource):
    """Deprecated shim for ``/registries``. See module docstring."""

    _path_prefix = "/registries"

    def __init__(self, client: CerberusClient) -> None:
        super().__init__(client)
        warnings.warn(_DEPRECATION_MSG, DeprecationWarning, stacklevel=2)

    def list(
        self,
        *,
        registry_type: RegistryType | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Deprecated: no-op. Raises :class:`NotImplementedError`."""
        raise NotImplementedError(_REMOVAL_MSG.format(name="list"))

    def get(self, id_: str) -> dict[str, Any]:
        """Deprecated: no-op. Raises :class:`NotImplementedError`."""
        raise NotImplementedError(_REMOVAL_MSG.format(name="get"))

    def lookup_rut(self, rut: str) -> dict[str, Any]:
        """Deprecated: redirects to ``entities.by_rut``.

        Emits a :class:`DeprecationWarning` and returns the result of
        ``GET /entities/by-rut/{rut}``. The RUT is normalised in-process
        (same rules as the pre-v0.2.0 implementation) so callers relying
        on lenient input (``96.505.760-9``, ``96505760-9``) still work.
        """
        warnings.warn(
            "client.registries.lookup_rut is deprecated; use client.entities.by_rut instead. "
            "Removed in v0.3.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        normalized = _normalize_rut(rut)
        return self._client._request("GET", f"/entities/by-rut/{quote(normalized, safe='')}")

    def iter_all(self, **filters: Any) -> Iterator[dict[str, Any]]:
        """Deprecated: no-op. Raises :class:`NotImplementedError`."""
        raise NotImplementedError(_REMOVAL_MSG.format(name="iter_all"))


class AsyncRegistriesResource(AsyncBaseResource):
    """Deprecated async mirror of :class:`RegistriesResource`."""

    _path_prefix = "/registries"

    def __init__(self, client: AsyncCerberusClient) -> None:
        super().__init__(client)
        warnings.warn(_DEPRECATION_MSG, DeprecationWarning, stacklevel=2)

    async def list(
        self,
        *,
        registry_type: RegistryType | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Deprecated: no-op. Raises :class:`NotImplementedError`."""
        raise NotImplementedError(_REMOVAL_MSG.format(name="list"))

    async def get(self, id_: str) -> dict[str, Any]:
        """Deprecated: no-op. Raises :class:`NotImplementedError`."""
        raise NotImplementedError(_REMOVAL_MSG.format(name="get"))

    async def lookup_rut(self, rut: str) -> dict[str, Any]:
        """Async variant of :meth:`RegistriesResource.lookup_rut`."""
        warnings.warn(
            "client.registries.lookup_rut is deprecated; use client.entities.by_rut instead. "
            "Removed in v0.3.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        normalized = _normalize_rut(rut)
        return await self._client._request("GET", f"/entities/by-rut/{quote(normalized, safe='')}")

    def iter_all(self, **filters: Any) -> AsyncIterator[dict[str, Any]]:
        """Deprecated: no-op. Raises :class:`NotImplementedError`."""
        raise NotImplementedError(_REMOVAL_MSG.format(name="iter_all"))
