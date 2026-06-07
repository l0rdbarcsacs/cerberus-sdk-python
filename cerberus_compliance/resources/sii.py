"""Typed accessor for the Cerberus Compliance ``/sii`` resource.

The *SII* surface exposes the Servicio de Impuestos Internos public
taxpayer registry (*nóminas SII*) as one row per contribuyente. Each
row carries the canonicalised RUT, ``razon_social``, the SII ``estado``
(typically ``"vigente"`` / ``"terminado"`` — free-form text, not a
closed enum), the ``tipo_contribuyente``, the activity-start date, the
``domicilio_comuna``, and the list of ACTECO economic activities. Only
public-registry attributes are exposed — never tax/risk/criminal
scoring (Ley 21.719).

The list endpoint uses **offset/limit** pagination and returns the raw
envelope ``{"items": [...], "total": N, "limit": L, "offset": O}`` — not
the cursor-paginated shape used elsewhere in the SDK (there is no
``next_cursor``); the caller walks pages by incrementing ``offset`` up
to ``total``. Results are ordered by ``rut_canonical`` ascending.

Count-cap gotcha: over the ~3.3M-row registry, *broad* listings (no
``rut`` and no ``q`` — including the estado-only or no-filter cases)
cap the reported ``total`` at ``10_000``; a ``total == 10000`` means
"at least 10000", not the real count. Only ``items`` is exact, never
capped. To get an **exact** ``total`` narrow the query with ``rut``
(exact canonical lookup) or ``q`` (Spanish full-text search over
``razon_social``); ``estado`` alone does *not* make ``total`` exact.

Filtering semantics (mirroring the server):

* ``rut`` — any RUT format (dots/DV optional); canonicalised and matched
  exactly on ``rut_canonical``. An invalid/non-canonicalisable RUT
  returns an empty envelope with HTTP 200 (not 422).
* ``q`` — Spanish word-based full-text search over ``razon_social``
  (``plainto_tsquery('spanish')``). Empty string is treated as absent.
* ``estado`` — case-insensitive equality on the SII estado.

We surface the raw envelope on :meth:`list` and offer :meth:`iter_all`
as an offset-based convenience that walks every page without exposing
offsets to the caller.

Example
-------
.. code-block:: python

    from cerberus_compliance import CerberusClient

    with CerberusClient() as client:
        page = client.sii.list(q="banco", limit=50)
        for row in client.sii.iter_all(estado="vigente"):
            print(row["rut"], row["razon_social"])
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import TYPE_CHECKING, Any

from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource

if TYPE_CHECKING:
    from cerberus_compliance.client import AsyncCerberusClient, CerberusClient

__all__ = ["AsyncSIIResource", "SIIResource"]


def _build_params(
    *,
    rut: str | None,
    q: str | None,
    estado: str | None,
    limit: int | None,
    offset: int | None,
) -> dict[str, Any] | None:
    """Assemble the ``/sii`` query-string dict, dropping ``None`` values.

    Returns ``None`` when every parameter is unset so the request URL
    stays a bare ``/sii`` without a trailing ``?``.
    """
    params: dict[str, Any] = {}
    if rut is not None:
        params["rut"] = rut
    if q is not None:
        params["q"] = q
    if estado is not None:
        params["estado"] = estado
    if limit is not None:
        params["limit"] = limit
    if offset is not None:
        params["offset"] = offset
    return params or None


class SIIResource(BaseResource):
    """Sync accessor for ``GET /sii`` (SII public taxpayer registry).

    The list endpoint returns ``{"items": [...], "total": int,
    "limit": int, "offset": int}``; pagination is offset-based rather
    than cursor-based. Requires the ``sii:read`` scope.
    """

    _path_prefix = "/sii"

    def __init__(self, client: CerberusClient) -> None:
        super().__init__(client)

    def list(
        self,
        *,
        rut: str | None = None,
        q: str | None = None,
        estado: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """List SII registry rows, with optional filters.

        Args:
            rut: RUT in any format (dots/DV optional); canonicalised and
                matched exactly. An invalid RUT yields an empty envelope
                (HTTP 200, not 422). Narrowing by ``rut`` makes ``total``
                exact (not capped).
            q: Spanish full-text search over ``razon_social``
                (word-based). Empty strings are ignored server-side.
                Narrowing by ``q`` makes ``total`` exact (not capped).
            estado: Case-insensitive SII estado (e.g. ``"vigente"``,
                ``"terminado"``); free-form ``str``, not a closed enum.
                ``estado`` alone does *not* make ``total`` exact — broad
                listings stay capped at ``10_000``.
            limit: Page size (server validation: ``1 <= limit <= 100``).
            offset: Zero-based offset (server validation: ``offset >= 0``).

        Returns:
            ``{"items": [...], "total": int, "limit": int, "offset": int}``
            — the raw offset/limit envelope. ``total`` is the global count
            of the filtered query, capped at ``10_000`` for broad listings
            (no ``rut`` and no ``q``); only ``items`` is never capped.
        """
        params = _build_params(rut=rut, q=q, estado=estado, limit=limit, offset=offset)
        return self._client._request("GET", self._path_prefix, params=params)

    def iter_all(
        self,
        *,
        rut: str | None = None,
        q: str | None = None,
        estado: str | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Yield every matching row across all pages, paginating by offset.

        Uses a fixed page size of 100 (the server maximum) and increments
        ``offset`` until a page comes back shorter than the page size or
        empty. Yields each item dict; filters are forwarded unchanged.

        Note: for broad listings (no ``rut`` and no ``q``) the server
        does not cap ``items`` — only the ``total`` field — so iteration
        walks the full result set regardless of the count cap.
        """
        page_size = 100
        offset = 0
        while True:
            body = self.list(rut=rut, q=q, estado=estado, limit=page_size, offset=offset)
            items = self._extract_items(body)
            if not items:
                return
            yield from items
            if len(items) < page_size:
                return
            offset += page_size


class AsyncSIIResource(AsyncBaseResource):
    """Async mirror of :class:`SIIResource`."""

    _path_prefix = "/sii"

    def __init__(self, client: AsyncCerberusClient) -> None:
        super().__init__(client)

    async def list(
        self,
        *,
        rut: str | None = None,
        q: str | None = None,
        estado: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """Async variant of :meth:`SIIResource.list`."""
        params = _build_params(rut=rut, q=q, estado=estado, limit=limit, offset=offset)
        return await self._client._request("GET", self._path_prefix, params=params)

    async def iter_all(
        self,
        *,
        rut: str | None = None,
        q: str | None = None,
        estado: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Async variant of :meth:`SIIResource.iter_all`."""
        page_size = 100
        offset = 0
        while True:
            body = await self.list(rut=rut, q=q, estado=estado, limit=page_size, offset=offset)
            items = self._extract_items(body)
            if not items:
                return
            for item in items:
                yield item
            if len(items) < page_size:
                return
            offset += page_size
