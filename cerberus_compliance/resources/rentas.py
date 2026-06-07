"""Typed accessor for the Cerberus Compliance ``/rentas`` resource.

The *rentas vitalicias* surface exposes the CMF ``rv_ranking`` feed — a
public-statistics table of life-annuity (renta vitalicia) ranking metrics
per insurance company. The backend unpivots the source ``.xls`` into one
row per (company x dimension x metric) value, so each item carries a
``metrica`` slug (e.g. ``tasa_interes_media``, ``prima_unica``), a
``dimension_tipo`` discriminator (e.g. ``pension`` / ``intermediario``),
the company *display name* (this surface has no entity RUT), and a
``Decimal`` ``valor``.

The list endpoint uses **offset/limit** pagination and returns the raw
envelope ``{"items": [...], "total": N, "limit": L, "offset": O}`` — not
the cursor-paginated shape used elsewhere in the SDK (there is no
``next_cursor``). ``total`` is the global count of the filtered query,
not the length of the current page; results are always ordered by
``periodo_hasta`` descending (most recent first), with no order parameter
exposed.

Filtering semantics (mirroring the server):

* ``compania`` — **exact** equality on the company display name.
* ``metrica`` — **exact** equality on the metric slug (free-form ``str``).
* ``dimension_tipo`` — **exact** equality on the dimension discriminator.
* ``q`` — case-insensitive **substring** (``ILIKE %q%``) over ``compania``;
  combinable with ``compania`` (both filters are applied).
* ``desde`` / ``hasta`` — inclusive bounds on ``periodo_hasta`` (ISO-8601
  ``YYYY-MM-DD`` strings), i.e. ``desde <= periodo_hasta <= hasta``.

We surface the raw envelope on :meth:`list` and offer :meth:`iter_all` as
an offset-based convenience that walks every page without exposing
offsets to the caller.

Example
-------
.. code-block:: python

    from cerberus_compliance import CerberusClient

    with CerberusClient() as client:
        page = client.rentas.list(metrica="tasa_interes_media", limit=50)
        for row in client.rentas.iter_all(dimension_tipo="pension"):
            print(row["compania"], row["valor"])
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import TYPE_CHECKING, Any

from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource

if TYPE_CHECKING:
    from cerberus_compliance.client import AsyncCerberusClient, CerberusClient

__all__ = ["AsyncRentasResource", "RentasResource"]


def _build_params(
    *,
    compania: str | None,
    metrica: str | None,
    dimension_tipo: str | None,
    desde: str | None,
    hasta: str | None,
    q: str | None,
    limit: int | None,
    offset: int | None,
) -> dict[str, Any] | None:
    """Assemble the ``/rentas`` query-string dict, dropping ``None`` values.

    Returns ``None`` when every parameter is unset so the request URL
    stays a bare ``/rentas`` without a trailing ``?``.
    """
    params: dict[str, Any] = {}
    if compania is not None:
        params["compania"] = compania
    if metrica is not None:
        params["metrica"] = metrica
    if dimension_tipo is not None:
        params["dimension_tipo"] = dimension_tipo
    if desde is not None:
        params["desde"] = desde
    if hasta is not None:
        params["hasta"] = hasta
    if q is not None:
        params["q"] = q
    if limit is not None:
        params["limit"] = limit
    if offset is not None:
        params["offset"] = offset
    return params or None


class RentasResource(BaseResource):
    """Sync accessor for ``GET /rentas`` (rentas vitalicias CMF).

    The list endpoint returns ``{"items": [...], "total": int,
    "limit": int, "offset": int}``; pagination is offset-based rather
    than cursor-based. Requires the ``rentas:read`` scope.
    """

    _path_prefix = "/rentas"

    def __init__(self, client: CerberusClient) -> None:
        super().__init__(client)

    def list(
        self,
        *,
        compania: str | None = None,
        metrica: str | None = None,
        dimension_tipo: str | None = None,
        desde: str | None = None,
        hasta: str | None = None,
        q: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """List renta-vitalicia ranking rows, with optional filters.

        Args:
            compania: Exact company display name (equality, not substring).
                Use ``q`` for partial matches.
            metrica: Exact metric slug (e.g. ``"tasa_interes_media"``,
                ``"prima_unica"``); free-form ``str``, not a closed enum.
            dimension_tipo: Exact dimension discriminator (e.g. ``"pension"``,
                ``"intermediario"``); free-form ``str``.
            desde: Lower bound on ``periodo_hasta`` (ISO-8601 ``YYYY-MM-DD``);
                keeps rows with ``periodo_hasta >= desde``.
            hasta: Upper bound on ``periodo_hasta`` (ISO-8601 ``YYYY-MM-DD``);
                keeps rows with ``periodo_hasta <= hasta``.
            q: Case-insensitive substring over ``compania`` (``ILIKE``);
                combinable with ``compania``. Empty strings are ignored
                server-side.
            limit: Page size (server validation: ``1 <= limit <= 100``).
            offset: Zero-based offset (server validation: ``offset >= 0``).

        Returns:
            ``{"items": [...], "total": int, "limit": int, "offset": int}``
            — the raw offset/limit envelope. ``total`` is the global count
            of the filtered query, not the page length.
        """
        params = _build_params(
            compania=compania,
            metrica=metrica,
            dimension_tipo=dimension_tipo,
            desde=desde,
            hasta=hasta,
            q=q,
            limit=limit,
            offset=offset,
        )
        return self._client._request("GET", self._path_prefix, params=params)

    def iter_all(
        self,
        *,
        compania: str | None = None,
        metrica: str | None = None,
        dimension_tipo: str | None = None,
        desde: str | None = None,
        hasta: str | None = None,
        q: str | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Yield every matching row across all pages, paginating by offset.

        Uses a fixed page size of 100 (the server maximum) and increments
        ``offset`` until a page comes back shorter than the page size or
        empty. Yields each item dict; filters are forwarded unchanged.
        """
        page_size = 100
        offset = 0
        while True:
            body = self.list(
                compania=compania,
                metrica=metrica,
                dimension_tipo=dimension_tipo,
                desde=desde,
                hasta=hasta,
                q=q,
                limit=page_size,
                offset=offset,
            )
            items = self._extract_items(body)
            if not items:
                return
            yield from items
            if len(items) < page_size:
                return
            offset += page_size


class AsyncRentasResource(AsyncBaseResource):
    """Async mirror of :class:`RentasResource`."""

    _path_prefix = "/rentas"

    def __init__(self, client: AsyncCerberusClient) -> None:
        super().__init__(client)

    async def list(
        self,
        *,
        compania: str | None = None,
        metrica: str | None = None,
        dimension_tipo: str | None = None,
        desde: str | None = None,
        hasta: str | None = None,
        q: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """Async variant of :meth:`RentasResource.list`."""
        params = _build_params(
            compania=compania,
            metrica=metrica,
            dimension_tipo=dimension_tipo,
            desde=desde,
            hasta=hasta,
            q=q,
            limit=limit,
            offset=offset,
        )
        return await self._client._request("GET", self._path_prefix, params=params)

    async def iter_all(
        self,
        *,
        compania: str | None = None,
        metrica: str | None = None,
        dimension_tipo: str | None = None,
        desde: str | None = None,
        hasta: str | None = None,
        q: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Async variant of :meth:`RentasResource.iter_all`."""
        page_size = 100
        offset = 0
        while True:
            body = await self.list(
                compania=compania,
                metrica=metrica,
                dimension_tipo=dimension_tipo,
                desde=desde,
                hasta=hasta,
                q=q,
                limit=page_size,
                offset=offset,
            )
            items = self._extract_items(body)
            if not items:
                return
            for item in items:
                yield item
            if len(items) < page_size:
                return
            offset += page_size
