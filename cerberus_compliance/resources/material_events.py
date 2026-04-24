"""Typed accessors for the Cerberus Compliance ``/material-events`` resource.

Material events (``hechos esenciales`` in Chilean regulatory parlance) are
disclosure filings that listed entities must submit to the CMF whenever an
event materially affects their securities or financial position. This module
exposes the synchronous :class:`MaterialEventsResource` and its asynchronous
mirror :class:`AsyncMaterialEventsResource`; both delegate to the shared base
classes in :mod:`cerberus_compliance.resources._base`.

Time filters (``since`` / ``until``) accept either ISO-8601 strings or
timezone-aware :class:`datetime.datetime` values; datetimes are serialized via
:meth:`datetime.datetime.isoformat` before being forwarded as query params,
strings pass through unchanged. See :func:`_coerce_params`.
"""

from __future__ import annotations

import builtins
from collections.abc import AsyncIterator, Iterator
from datetime import datetime
from typing import Any

from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource

__all__ = ["AsyncMaterialEventsResource", "MaterialEventsResource"]


def _coerce_params(raw: dict[str, Any] | None) -> dict[str, Any] | None:
    """Serialize datetime values in a params dict to ISO-8601 strings.

    Returns ``None`` when ``raw`` is ``None`` or empty so callers can pass the
    result straight through to ``_request(..., params=...)``. For non-empty
    inputs, returns a fresh dict where any :class:`datetime.datetime` value is
    replaced by ``value.isoformat()``; other value types pass through
    untouched.
    """
    if not raw:
        return None
    coerced: dict[str, Any] = {}
    for key, value in raw.items():
        if isinstance(value, datetime):
            coerced[key] = value.isoformat()
        else:
            coerced[key] = value
    return coerced


class MaterialEventsResource(BaseResource):
    """Synchronous accessor for the ``/material-events`` endpoint family."""

    _path_prefix = "/material-events"

    def list(
        self,
        *,
        entity_id: str | None = None,
        since: str | datetime | None = None,
        until: str | datetime | None = None,
        limit: int | None = None,
    ) -> builtins.list[dict[str, Any]]:
        """Return the first page of material events, optionally filtered.

        Args:
            entity_id: Restrict to events for a single entity (by RUT).
            since: Lower bound on publication timestamp. ``datetime`` values
                are serialized to ISO-8601; strings are forwarded verbatim.
            until: Upper bound on publication timestamp. Same coercion rule
                as ``since``.
            limit: Maximum number of events to return on this page.
        """
        raw: dict[str, Any] = {}
        if entity_id is not None:
            raw["entity_id"] = entity_id
        if since is not None:
            raw["since"] = since
        if until is not None:
            raw["until"] = until
        if limit is not None:
            raw["limit"] = limit
        return self._list(params=_coerce_params(raw))

    def get(self, id_: str) -> dict[str, Any]:
        """Fetch a single material event by ID (``GET /material-events/<id_>``)."""
        return self._get(id_)

    def iter_all(self, **filters: Any) -> Iterator[dict[str, Any]]:
        """Iterate through every material event, transparently paginating.

        Forwards arbitrary ``**filters`` on every page request, applying the
        same datetime-to-ISO coercion rule as :meth:`list`. Returns the
        underlying generator directly so callers get a plain sync generator.
        """
        return self._iter_all(params=_coerce_params(filters))


class AsyncMaterialEventsResource(AsyncBaseResource):
    """Asynchronous accessor for the ``/material-events`` endpoint family."""

    _path_prefix = "/material-events"

    async def list(
        self,
        *,
        entity_id: str | None = None,
        since: str | datetime | None = None,
        until: str | datetime | None = None,
        limit: int | None = None,
    ) -> builtins.list[dict[str, Any]]:
        """Async variant of :meth:`MaterialEventsResource.list`."""
        raw: dict[str, Any] = {}
        if entity_id is not None:
            raw["entity_id"] = entity_id
        if since is not None:
            raw["since"] = since
        if until is not None:
            raw["until"] = until
        if limit is not None:
            raw["limit"] = limit
        return await self._list(params=_coerce_params(raw))

    async def get(self, id_: str) -> dict[str, Any]:
        """Async variant of :meth:`MaterialEventsResource.get`."""
        return await self._get(id_)

    def iter_all(self, **filters: Any) -> AsyncIterator[dict[str, Any]]:
        """Async iterator over every material event.

        Intentionally a non-``async`` method that returns the underlying async
        generator directly, so callers can write ``async for`` at the call
        site without an extra ``await``. Applies the same datetime-to-ISO
        coercion rule as :meth:`MaterialEventsResource.iter_all`.
        """
        return self._iter_all(params=_coerce_params(filters))
