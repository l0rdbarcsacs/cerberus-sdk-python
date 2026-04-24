"""Typed accessors for the Cerberus Compliance ``/persons`` resource.

Persons are Chilean natural persons (``personas naturales``), identified
by their RUT. This module exposes the synchronous
:class:`PersonsResource` and its asynchronous mirror
:class:`AsyncPersonsResource`; both delegate to the shared base classes
in :mod:`cerberus_compliance.resources._base`.

The ``/persons/<id>/regulatory-profile`` endpoint returns a single
object (not a ``{"data": [...]}`` envelope) describing the person's
compliance-risk signals — PEP status, sanctions score, watchlist hits,
etc. — and is returned verbatim to the caller.
"""

from __future__ import annotations

import builtins
from collections.abc import AsyncIterator, Iterator
from typing import Any
from urllib.parse import quote

from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource

__all__ = ["AsyncPersonsResource", "PersonsResource"]


class PersonsResource(BaseResource):
    """Synchronous accessor for the ``/persons`` endpoint family."""

    _path_prefix = "/persons"

    def list(
        self,
        *,
        rut: str | None = None,
        limit: int | None = None,
    ) -> builtins.list[dict[str, Any]]:
        """Return the first page of persons, optionally filtered.

        Args:
            rut: Chilean RUT filter (e.g. ``"7890123-4"``).
            limit: Maximum number of persons to return on this page.
        """
        params: dict[str, Any] = {}
        if rut is not None:
            params["rut"] = rut
        if limit is not None:
            params["limit"] = limit
        return self._list(params=params or None)

    def get(self, id_: str) -> dict[str, Any]:
        """Fetch a single person by RUT (``GET /persons/<id_>``)."""
        return self._get(id_)

    def regulatory_profile(self, id_: str) -> dict[str, Any]:
        """Return the full compliance profile for a person.

        Issues ``GET /persons/<id_>/regulatory-profile``. The endpoint
        returns a single object (not a list envelope), so the parsed
        body is returned as-is.
        """
        return self._client._request(
            "GET", f"{self._path_prefix}/{quote(id_, safe='')}/regulatory-profile"
        )

    def iter_all(self, **filters: Any) -> Iterator[dict[str, Any]]:
        """Iterate through every person, transparently paginating.

        Forwards arbitrary ``**filters`` on every page request. Returns
        the underlying generator directly (rather than ``yield from``)
        so the method itself is a plain sync function that hands back a
        generator.
        """
        return self._iter_all(params=filters or None)


class AsyncPersonsResource(AsyncBaseResource):
    """Asynchronous accessor for the ``/persons`` endpoint family."""

    _path_prefix = "/persons"

    async def list(
        self,
        *,
        rut: str | None = None,
        limit: int | None = None,
    ) -> builtins.list[dict[str, Any]]:
        """Async variant of :meth:`PersonsResource.list`."""
        params: dict[str, Any] = {}
        if rut is not None:
            params["rut"] = rut
        if limit is not None:
            params["limit"] = limit
        return await self._list(params=params or None)

    async def get(self, id_: str) -> dict[str, Any]:
        """Async variant of :meth:`PersonsResource.get`."""
        return await self._get(id_)

    async def regulatory_profile(self, id_: str) -> dict[str, Any]:
        """Async variant of :meth:`PersonsResource.regulatory_profile`."""
        return await self._client._request(
            "GET", f"{self._path_prefix}/{quote(id_, safe='')}/regulatory-profile"
        )

    def iter_all(self, **filters: Any) -> AsyncIterator[dict[str, Any]]:
        """Async iterator over every person; mirror of :meth:`PersonsResource.iter_all`.

        Intentionally a non-``async`` method that returns the underlying
        async generator directly, so callers can write ``async for`` at
        the call site without an extra ``await``.
        """
        return self._iter_all(params=filters or None)
