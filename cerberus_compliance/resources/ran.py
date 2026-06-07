"""Typed accessor for the Cerberus Compliance ``/ran`` resource.

The RAN (*Recopilación Actualizada de Normas*) endpoint exposes the CMF's
banking-regulation chapters as a versioned snapshot table: one row per
unique ``content_md5`` of a chapter, ordered ``last_seen_at`` DESC
(newest-seen first). Each row is a point-in-time version of a RAN chapter
with its number, title, source document URL and provenance timestamps.

Unlike the cursor-paginated endpoints elsewhere in the SDK, ``/ran`` uses
offset-style pagination: the server returns the envelope
``{"items": [...], "total": int, "limit": int, "offset": int}`` directly.
We surface that raw envelope on :meth:`list` (so callers can read
``total`` to drive their own paging) and offer :meth:`iter_all` as an
offset-based convenience that walks every page without exposing offsets.

Example
-------
.. code-block:: python

    import datetime

    from cerberus_compliance import CerberusClient

    with CerberusClient() as client:
        page = client.ran.list(q="liquidez", limit=50)
        print(page["total"])
        for cap in client.ran.iter_all(desde=datetime.date(2026, 1, 1)):
            print(cap["chapter_number"], cap["chapter_title"])
"""

from __future__ import annotations

import datetime
from collections.abc import AsyncIterator, Iterator
from typing import TYPE_CHECKING, Any

from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource

if TYPE_CHECKING:
    from cerberus_compliance.client import AsyncCerberusClient, CerberusClient

__all__ = ["AsyncRANResource", "RANResource"]

# Page size used by ``iter_all`` — the server caps ``limit`` at 100.
_ITER_PAGE_SIZE = 100


def _iso_date(value: datetime.date) -> str:
    """Render a :class:`datetime.date` as a ``YYYY-MM-DD`` ISO string.

    ``datetime.datetime`` is a subclass of ``datetime.date``; calling
    ``.isoformat()`` on it would emit a full timestamp, so we normalise to
    the date component first to keep the query value ``YYYY-MM-DD``.
    """
    if isinstance(value, datetime.datetime):
        value = value.date()
    return value.isoformat()


def _build_params(
    *,
    desde: datetime.date | None,
    hasta: datetime.date | None,
    q: str | None,
    limit: int | None,
    offset: int | None,
) -> dict[str, Any] | None:
    """Assemble the ``/ran`` query-string dict, dropping ``None`` values.

    Returns ``None`` when every filter is unset so the request URL stays a
    bare ``/ran`` without a trailing ``?``.
    """
    params: dict[str, Any] = {}
    if desde is not None:
        params["desde"] = _iso_date(desde)
    if hasta is not None:
        params["hasta"] = _iso_date(hasta)
    if q is not None:
        params["q"] = q
    if limit is not None:
        params["limit"] = limit
    if offset is not None:
        params["offset"] = offset
    return params or None


def _extract_items(body: dict[str, Any]) -> list[dict[str, Any]]:
    """Pull the ``items`` array out of the RAN envelope, defensively."""
    payload = body.get("items")
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


class RANResource(BaseResource):
    """Sync accessor for ``GET /ran``.

    The list endpoint returns
    ``{"items": [...], "total": int, "limit": int, "offset": int}``;
    pagination is offset-based rather than cursor-based.
    """

    _path_prefix = "/ran"

    def __init__(self, client: CerberusClient) -> None:
        super().__init__(client)

    def list(
        self,
        *,
        desde: datetime.date | None = None,
        hasta: datetime.date | None = None,
        q: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """List RAN chapter snapshots, newest-seen first.

        Args:
            desde: Lower bound on ``last_seen_at`` (inclusive,
                ``last_seen_at >= desde``).
            hasta: Upper bound on ``last_seen_at`` (**exclusive**,
                ``last_seen_at < hasta``).
            q: Case-insensitive substring matched against ``chapter_title``
                OR ``chapter_number``. An empty string is ignored server-side.
            limit: Page size (server validates ``1 <= limit <= 100``,
                default 20).
            offset: Zero-based offset (server validates ``offset >= 0``).

        Returns:
            ``{"items": [...], "total": int, "limit": int, "offset": int}``
            — the raw envelope. ``total`` is the full filtered count, which
            callers can use to page by incrementing ``offset``.
        """
        params = _build_params(desde=desde, hasta=hasta, q=q, limit=limit, offset=offset)
        return self._client._request("GET", self._path_prefix, params=params)

    def iter_all(
        self,
        *,
        desde: datetime.date | None = None,
        hasta: datetime.date | None = None,
        q: str | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Yield every chapter snapshot across all pages, paginating by offset.

        Uses a fixed page size of 100 and increments ``offset`` until the
        server returns a short or empty page. Forwards the ``desde`` /
        ``hasta`` / ``q`` filters on every request.
        """
        offset = 0
        while True:
            body = self.list(desde=desde, hasta=hasta, q=q, limit=_ITER_PAGE_SIZE, offset=offset)
            items = _extract_items(body)
            if not items:
                return
            yield from items
            if len(items) < _ITER_PAGE_SIZE:
                return
            offset += _ITER_PAGE_SIZE


class AsyncRANResource(AsyncBaseResource):
    """Async mirror of :class:`RANResource`."""

    _path_prefix = "/ran"

    def __init__(self, client: AsyncCerberusClient) -> None:
        super().__init__(client)

    async def list(
        self,
        *,
        desde: datetime.date | None = None,
        hasta: datetime.date | None = None,
        q: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """Async variant of :meth:`RANResource.list`."""
        params = _build_params(desde=desde, hasta=hasta, q=q, limit=limit, offset=offset)
        return await self._client._request("GET", self._path_prefix, params=params)

    async def iter_all(
        self,
        *,
        desde: datetime.date | None = None,
        hasta: datetime.date | None = None,
        q: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Async variant of :meth:`RANResource.iter_all`."""
        offset = 0
        while True:
            body = await self.list(
                desde=desde, hasta=hasta, q=q, limit=_ITER_PAGE_SIZE, offset=offset
            )
            items = _extract_items(body)
            if not items:
                return
            for item in items:
                yield item
            if len(items) < _ITER_PAGE_SIZE:
                return
            offset += _ITER_PAGE_SIZE
