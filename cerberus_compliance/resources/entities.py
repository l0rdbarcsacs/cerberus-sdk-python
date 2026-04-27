"""Typed accessors for the Cerberus Compliance ``/entities`` resource.

Entities are Chilean legal persons (companies, foundations, public
agencies) identified by their RUT. This module exposes the synchronous
:class:`EntitiesResource` and its asynchronous mirror
:class:`AsyncEntitiesResource`; both delegate to the shared base classes
in :mod:`cerberus_compliance.resources._base`.

Nested collection endpoints (``material-events``, ``sanctions``,
``directors``, ``regulations``) parse the response envelope
defensively via the shared :func:`_extract_items` helper on
:class:`~cerberus_compliance.resources._base.BaseResource`. Both
``{"data": [...]}`` (documented shape) and ``{"items": [...]}`` (live
prod shape) are accepted; missing keys, non-list values, and non-dict
items all collapse to an empty list (or are skipped) so callers never
receive malformed payloads.
"""

from __future__ import annotations

import builtins
from collections.abc import AsyncIterator, Iterator
from typing import Any
from urllib.parse import quote

from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource

__all__ = ["AsyncEntitiesResource", "EntitiesResource"]


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

    def by_rut(self, rut: str) -> dict[str, Any]:
        """Fetch an entity by canonical RUT (``GET /entities/by-rut/<rut>``).

        Distinct from :meth:`get` which expects the server-assigned entity
        id. The RUT path segment is percent-encoded so dotted forms like
        ``96.505.760-9`` survive round-trip unchanged.
        """
        path = f"{self._path_prefix}/by-rut/{quote(rut, safe='')}"
        return self._client._request("GET", path)

    def ownership(self, id_: str) -> dict[str, Any]:
        """Return the ownership/beneficial-owner graph for an entity.

        Issues ``GET /entities/<id_>/ownership``. The endpoint returns an
        aggregate object (parents, shareholders, ultimate-beneficial-owner
        chain), not a paginated list; the body is returned verbatim.
        """
        path = f"{self._path_prefix}/{quote(id_, safe='')}/ownership"
        return self._client._request("GET", path)

    def material_events(self, id_: str) -> builtins.list[dict[str, Any]]:
        """List material events (``hechos esenciales``) for an entity."""
        body = self._client._request(
            "GET", f"{self._path_prefix}/{quote(id_, safe='')}/material-events"
        )
        return self._extract_items(body)

    def sanctions(self, id_: str) -> builtins.list[dict[str, Any]]:
        """List sanctions observed against an entity.

        Issues ``GET /sanctions/by-entity/<id_>``. Prior versions of the
        SDK hit ``/entities/<id_>/sanctions``, which never existed on the
        prod API — see CHANGELOG v0.2.0 for the gap-audit fix.
        """
        body = self._client._request("GET", f"/sanctions/by-entity/{quote(id_, safe='')}")
        return self._extract_items(body)

    def directors(self, id_: str) -> builtins.list[dict[str, Any]]:
        """List the current board of directors for an entity."""
        body = self._client._request("GET", f"{self._path_prefix}/{quote(id_, safe='')}/directors")
        return self._extract_items(body)

    def regulations(self, id_: str) -> builtins.list[dict[str, Any]]:
        """List regulatory obligations applicable to an entity."""
        body = self._client._request(
            "GET", f"{self._path_prefix}/{quote(id_, safe='')}/regulations"
        )
        return self._extract_items(body)

    def diff(
        self,
        entity_id: str,
        *,
        from_: str,
        to: str | None = None,
    ) -> dict[str, Any]:
        """Return SCD2 changes between two ISO dates.

        Issues ``GET /entities/{entity_id}/diff?from=…&to=…``. The
        ``from_`` Python kwarg maps to the wire param ``from`` (the
        Python keyword forced the trailing-underscore alias).

        Args:
            entity_id: Server-assigned entity id.
            from_: ``YYYY-MM-DD`` lower bound (required).
            to: Optional ``YYYY-MM-DD`` upper bound. When ``None`` the
                server defaults to "now".

        Returns:
            ``{"entity_id": str, "entity_rut": str, "from": str,
            "to": str, "changes": [{"timestamp": str, "field": str,
            "old_value": Any, "new_value": Any, "source": str}, ...],
            "total": int}``.
        """
        params: dict[str, Any] = {"from": from_}
        if to is not None:
            params["to"] = to
        return self._client._request(
            "GET",
            f"{self._path_prefix}/{quote(entity_id, safe='')}/diff",
            params=params,
        )

    def bancos_fichas(
        self,
        rut: str,
        *,
        year: int | None = None,
        month: int | None = None,
    ) -> builtins.list[dict[str, Any]]:
        """List bank "fichas" (regulatory snapshots) for a bank RUT.

        Issues ``GET /bancos/{rut}/fichas`` with optional ``year`` and
        ``month`` filters. Returned envelope is normalised via
        :func:`_extract_items` so both ``{"data": [...]}`` and
        ``{"items": [...]}`` shapes are accepted.
        """
        params: dict[str, Any] = {}
        if year is not None:
            params["year"] = year
        if month is not None:
            params["month"] = month
        body = self._client._request(
            "GET",
            f"/bancos/{quote(rut, safe='')}/fichas",
            params=params or None,
        )
        return self._extract_items(body)

    def bancos_fichas_latest_per_section(self, rut: str) -> dict[str, Any]:
        """Return the most recent ficha per section for a bank.

        Issues ``GET /bancos/{rut}/fichas/latest-per-section``. The
        endpoint returns a single aggregate object keyed by section
        name (not a list envelope), so the body is returned verbatim.
        """
        return self._client._request(
            "GET",
            f"/bancos/{quote(rut, safe='')}/fichas/latest-per-section",
        )

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

    async def by_rut(self, rut: str) -> dict[str, Any]:
        """Async variant of :meth:`EntitiesResource.by_rut`."""
        path = f"{self._path_prefix}/by-rut/{quote(rut, safe='')}"
        return await self._client._request("GET", path)

    async def ownership(self, id_: str) -> dict[str, Any]:
        """Async variant of :meth:`EntitiesResource.ownership`."""
        path = f"{self._path_prefix}/{quote(id_, safe='')}/ownership"
        return await self._client._request("GET", path)

    async def material_events(self, id_: str) -> builtins.list[dict[str, Any]]:
        """Async variant of :meth:`EntitiesResource.material_events`."""
        body = await self._client._request(
            "GET", f"{self._path_prefix}/{quote(id_, safe='')}/material-events"
        )
        return self._extract_items(body)

    async def sanctions(self, id_: str) -> builtins.list[dict[str, Any]]:
        """Async variant of :meth:`EntitiesResource.sanctions`."""
        body = await self._client._request("GET", f"/sanctions/by-entity/{quote(id_, safe='')}")
        return self._extract_items(body)

    async def directors(self, id_: str) -> builtins.list[dict[str, Any]]:
        """Async variant of :meth:`EntitiesResource.directors`."""
        body = await self._client._request(
            "GET", f"{self._path_prefix}/{quote(id_, safe='')}/directors"
        )
        return self._extract_items(body)

    async def regulations(self, id_: str) -> builtins.list[dict[str, Any]]:
        """Async variant of :meth:`EntitiesResource.regulations`."""
        body = await self._client._request(
            "GET", f"{self._path_prefix}/{quote(id_, safe='')}/regulations"
        )
        return self._extract_items(body)

    async def diff(
        self,
        entity_id: str,
        *,
        from_: str,
        to: str | None = None,
    ) -> dict[str, Any]:
        """Async variant of :meth:`EntitiesResource.diff`."""
        params: dict[str, Any] = {"from": from_}
        if to is not None:
            params["to"] = to
        return await self._client._request(
            "GET",
            f"{self._path_prefix}/{quote(entity_id, safe='')}/diff",
            params=params,
        )

    async def bancos_fichas(
        self,
        rut: str,
        *,
        year: int | None = None,
        month: int | None = None,
    ) -> builtins.list[dict[str, Any]]:
        """Async variant of :meth:`EntitiesResource.bancos_fichas`."""
        params: dict[str, Any] = {}
        if year is not None:
            params["year"] = year
        if month is not None:
            params["month"] = month
        body = await self._client._request(
            "GET",
            f"/bancos/{quote(rut, safe='')}/fichas",
            params=params or None,
        )
        return self._extract_items(body)

    async def bancos_fichas_latest_per_section(self, rut: str) -> dict[str, Any]:
        """Async variant of :meth:`EntitiesResource.bancos_fichas_latest_per_section`."""
        return await self._client._request(
            "GET",
            f"/bancos/{quote(rut, safe='')}/fichas/latest-per-section",
        )

    def iter_all(self, **filters: Any) -> AsyncIterator[dict[str, Any]]:
        """Async iterator over every entity; mirrors :meth:`EntitiesResource.iter_all`.

        Intentionally a non-``async`` method that returns the underlying
        async generator directly — matches the idiom used in the base
        resource tests and keeps ``async for`` usage natural at the call
        site.
        """
        return self._iter_all(params=filters or None)
