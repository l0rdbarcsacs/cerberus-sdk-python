"""Public Chilean registries sub-resource (CMF / SII / DICOM / Conservador).

Exposes list / get / iter_all endpoints plus a RUT-lookup helper that
normalises the input (strips whitespace, dots, and hyphens; uppercases
the check digit ``k``) before hitting the network. Invalid RUTs are
rejected with :class:`ValueError` before any request is issued.

The sub-resource follows the snake_case query-parameter convention
(``registry_type=CMF``) to stay consistent with Python naming; the
server accepts this form alongside the camelCase equivalent.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any, Literal

from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource

__all__ = ["AsyncRegistriesResource", "RegistriesResource", "RegistryType"]

RegistryType = Literal["CMF", "SII", "DICOM", "Conservador"]


def _normalize_rut(rut: str) -> str:
    """Return the canonical ``<body>-<dv>`` form of ``rut``.

    The input is stripped of whitespace, dots, and hyphens; the check
    digit is uppercased when it is ``k``. Raises :class:`ValueError`
    when the string is empty, shorter than two characters, contains
    non-alphanumeric chars, has a non-numeric body, or has a verifier
    that is not a digit or ``K``. This validation is syntactic only:
    the check-digit arithmetic is not verified.
    """
    stripped = "".join(ch for ch in rut if not ch.isspace())
    cleaned = stripped.replace(".", "").replace("-", "")

    if len(cleaned) < 2 or not cleaned.isalnum():
        raise ValueError(f"invalid RUT: {rut!r}")

    body, dv = cleaned[:-1], cleaned[-1].upper()
    if not body.isdigit() or not (dv.isdigit() or dv == "K"):
        raise ValueError(f"invalid RUT: {rut!r}")

    return f"{body}-{dv}"


def _build_list_params(
    registry_type: RegistryType | None,
    limit: int | None,
) -> dict[str, Any] | None:
    """Assemble a query dict, dropping ``None`` values.

    Returns ``None`` when all parameters are absent so the client omits
    the query string entirely.
    """
    params: dict[str, Any] = {}
    if registry_type is not None:
        params["registry_type"] = registry_type
    if limit is not None:
        params["limit"] = limit
    return params or None


def _drop_none(filters: dict[str, Any]) -> dict[str, Any] | None:
    """Remove ``None``-valued entries; return ``None`` when nothing remains."""
    cleaned = {k: v for k, v in filters.items() if v is not None}
    return cleaned or None


class RegistriesResource(BaseResource):
    """Synchronous accessor for ``/registries`` endpoints."""

    _path_prefix = "/registries"

    def list(
        self,
        *,
        registry_type: RegistryType | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """List registries, optionally filtered by ``registry_type``."""
        return self._list(params=_build_list_params(registry_type, limit))

    def get(self, id_: str) -> dict[str, Any]:
        """Fetch a single registry entry by its server-assigned id."""
        return self._get(id_)

    def lookup_rut(self, rut: str) -> dict[str, Any]:
        """Look up registries cross-referenced to a RUT.

        The input is normalised in-process and rejected with
        :class:`ValueError` when it cannot be interpreted as a RUT. On
        success this issues ``GET /registries/lookup/rut/<body>-<dv>``.
        """
        normalized = _normalize_rut(rut)
        path = f"{self._path_prefix}/lookup/rut/{normalized}"
        return self._client._request("GET", path)

    def iter_all(self, **filters: Any) -> Iterator[dict[str, Any]]:
        """Cursor-paginate through all registries matching ``filters``."""
        return self._iter_all(params=_drop_none(filters))


class AsyncRegistriesResource(AsyncBaseResource):
    """Asynchronous accessor for ``/registries`` endpoints."""

    _path_prefix = "/registries"

    async def list(
        self,
        *,
        registry_type: RegistryType | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """List registries, optionally filtered by ``registry_type``."""
        return await self._list(params=_build_list_params(registry_type, limit))

    async def get(self, id_: str) -> dict[str, Any]:
        """Fetch a single registry entry by its server-assigned id."""
        return await self._get(id_)

    async def lookup_rut(self, rut: str) -> dict[str, Any]:
        """Async variant of :meth:`RegistriesResource.lookup_rut`."""
        normalized = _normalize_rut(rut)
        path = f"{self._path_prefix}/lookup/rut/{normalized}"
        return await self._client._request("GET", path)

    def iter_all(self, **filters: Any) -> AsyncIterator[dict[str, Any]]:
        """Cursor-paginate through all registries matching ``filters``."""
        return self._iter_all(params=_drop_none(filters))
