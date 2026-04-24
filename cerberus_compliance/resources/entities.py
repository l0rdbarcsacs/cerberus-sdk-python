"""Typed accessors for the Cerberus Compliance ``/entities`` resource.

Entities are Chilean legal persons (companies, foundations, public
agencies) identified by their RUT. This module exposes the synchronous
:class:`EntitiesResource` and its asynchronous mirror
:class:`AsyncEntitiesResource`; both delegate to the shared base classes
in :mod:`cerberus_compliance.resources._base`.

Nested collection endpoints (``material-events``, ``sanctions``,
``directors``, ``regulations``) parse the response envelope
defensively: a missing ``data`` key, a non-list ``data`` value, or
non-dict items in the list are all silently collapsed to an empty list
(or skipped), so callers never receive malformed payloads.
"""

from __future__ import annotations

import builtins
from collections.abc import AsyncIterator, Iterator
from typing import Any

from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource

__all__ = ["AsyncEntitiesResource", "EntitiesResource"]


def _extract_data_list(body: dict[str, Any]) -> list[dict[str, Any]]:
    """Return a list of dicts from a ``{"data": [...]}``-shaped envelope.

    Returns ``[]`` when ``data`` is missing or not a list, and drops any
    non-dict items in a valid list so the result is always a concrete
    ``list[dict[str, Any]]``.
    """
    data = body.get("data")
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


class EntitiesResource(BaseResource):
    """Synchronous accessor for the ``/entities`` endpoint family."""

    _path_prefix = "/entities"

    def list(
        self,
        *,
        rut: str | None = None,
        limit: int | None = None,
    ) -> builtins.list[dict[str, Any]]:
        """Return the first page of entities, optionally filtered.

        Args:
            rut: Chilean RUT filter (e.g. ``"76123456-7"``).
            limit: Maximum number of entities to return on this page.
        """
        params: dict[str, Any] = {}
        if rut is not None:
            params["rut"] = rut
        if limit is not None:
            params["limit"] = limit
        return self._list(params=params or None)

    def get(self, id_: str) -> dict[str, Any]:
        """Fetch a single entity by RUT (``GET /entities/<id_>``)."""
        return self._get(id_)

    def material_events(self, id_: str) -> builtins.list[dict[str, Any]]:
        """List material events (``hechos esenciales``) for an entity."""
        body = self._client._request("GET", f"{self._path_prefix}/{id_}/material-events")
        return _extract_data_list(body)

    def sanctions(self, id_: str) -> builtins.list[dict[str, Any]]:
        """List sanctions observed against an entity."""
        body = self._client._request("GET", f"{self._path_prefix}/{id_}/sanctions")
        return _extract_data_list(body)

    def directors(self, id_: str) -> builtins.list[dict[str, Any]]:
        """List the current board of directors for an entity."""
        body = self._client._request("GET", f"{self._path_prefix}/{id_}/directors")
        return _extract_data_list(body)

    def regulations(self, id_: str) -> builtins.list[dict[str, Any]]:
        """List regulatory obligations applicable to an entity."""
        body = self._client._request("GET", f"{self._path_prefix}/{id_}/regulations")
        return _extract_data_list(body)

    def iter_all(self, **filters: Any) -> Iterator[dict[str, Any]]:
        """Iterate through every entity, transparently paginating.

        Forwards arbitrary ``**filters`` on every page request. Returns
        the underlying generator directly (instead of ``yield from``) so
        callers get a plain sync generator without the extra frame.
        """
        return self._iter_all(params=filters or None)


class AsyncEntitiesResource(AsyncBaseResource):
    """Asynchronous accessor for the ``/entities`` endpoint family."""

    _path_prefix = "/entities"

    async def list(
        self,
        *,
        rut: str | None = None,
        limit: int | None = None,
    ) -> builtins.list[dict[str, Any]]:
        """Async variant of :meth:`EntitiesResource.list`."""
        params: dict[str, Any] = {}
        if rut is not None:
            params["rut"] = rut
        if limit is not None:
            params["limit"] = limit
        return await self._list(params=params or None)

    async def get(self, id_: str) -> dict[str, Any]:
        """Async variant of :meth:`EntitiesResource.get`."""
        return await self._get(id_)

    async def material_events(self, id_: str) -> builtins.list[dict[str, Any]]:
        """Async variant of :meth:`EntitiesResource.material_events`."""
        body = await self._client._request("GET", f"{self._path_prefix}/{id_}/material-events")
        return _extract_data_list(body)

    async def sanctions(self, id_: str) -> builtins.list[dict[str, Any]]:
        """Async variant of :meth:`EntitiesResource.sanctions`."""
        body = await self._client._request("GET", f"{self._path_prefix}/{id_}/sanctions")
        return _extract_data_list(body)

    async def directors(self, id_: str) -> builtins.list[dict[str, Any]]:
        """Async variant of :meth:`EntitiesResource.directors`."""
        body = await self._client._request("GET", f"{self._path_prefix}/{id_}/directors")
        return _extract_data_list(body)

    async def regulations(self, id_: str) -> builtins.list[dict[str, Any]]:
        """Async variant of :meth:`EntitiesResource.regulations`."""
        body = await self._client._request("GET", f"{self._path_prefix}/{id_}/regulations")
        return _extract_data_list(body)

    def iter_all(self, **filters: Any) -> AsyncIterator[dict[str, Any]]:
        """Async iterator over every entity; mirrors :meth:`EntitiesResource.iter_all`.

        Intentionally a non-``async`` method that returns the underlying
        async generator directly — matches the idiom used in the base
        resource tests and keeps ``async for`` usage natural at the call
        site.
        """
        return self._iter_all(params=filters or None)
