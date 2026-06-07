"""Typed accessor for the Cerberus Compliance ``/scomp`` resource.

SCOMP (Sistema de Consultas y Ofertas de Montos de Pensión) statistics are
served by the API as a single unpivoted table of report cells. Each row is
one statistics cell keyed by ``(informe, periodo_desde, periodo_hasta, fila,
columna)`` carrying a numeric ``valor`` (a :class:`~decimal.Decimal` — map to
``Decimal`` / ``str``, never ``float``) plus a free-form ``meta`` JSON object.

The endpoint uses offset/limit pagination — *not* the cursor protocol used by
most of the SDK. The server returns the envelope
``{"items": [...], "total": N, "limit": L, "offset": O}`` directly, ordered by
``periodo_hasta`` descending (newest period first). We surface that raw
envelope on :meth:`list` and offer :meth:`iter_all` as an offset-based
convenience that walks every page without exposing offsets to the caller.

There are no path params and no RUT filter: ``fila`` / ``columna`` are label
strings, not entity RUTs. The optional date bounds (``desde`` / ``hasta``)
both constrain ``periodo_hasta`` despite the ``desde`` name; ``q`` is a
case-insensitive substring match on the ``informe`` report slug.

Example
-------
.. code-block:: python

    from cerberus_compliance import CerberusClient

    with CerberusClient() as client:
        page = client.scomp.list_estadisticas(q="afiliados", limit=50)
        for cell in client.scomp.iter_all_estadisticas(desde="2024-01-01"):
            print(cell["informe"], cell["fila"], cell["columna"], cell["valor"])
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import TYPE_CHECKING, Any

from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource

if TYPE_CHECKING:
    from cerberus_compliance.client import AsyncCerberusClient, CerberusClient

__all__ = ["AsyncSCOMPResource", "SCOMPResource"]


def _build_params(
    *,
    desde: str | None,
    hasta: str | None,
    q: str | None,
    limit: int | None,
    offset: int | None,
) -> dict[str, Any] | None:
    """Assemble the SCOMP query-string dict, dropping ``None`` values.

    Returns ``None`` when every filter is unset so the request URL stays a
    bare ``/scomp`` without a trailing ``?``.
    """
    params: dict[str, Any] = {}
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


class SCOMPResource(BaseResource):
    """Sync accessor for ``GET /scomp``.

    The list endpoint returns ``{"items": [...], "total": int, "limit": int,
    "offset": int}``; pagination is offset-based rather than cursor-based.
    """

    _path_prefix = "/scomp"

    def __init__(self, client: CerberusClient) -> None:
        super().__init__(client)

    def list_estadisticas(
        self,
        *,
        desde: str | None = None,
        hasta: str | None = None,
        q: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """List SCOMP statistics cells, optionally filtered.

        Args:
            desde: ISO-8601 lower bound on ``periodo_hasta`` (only cells whose
                ``periodo_hasta >= desde``). Despite the name this constrains
                ``periodo_hasta``, not ``periodo_desde``.
            hasta: ISO-8601 upper bound on ``periodo_hasta`` (only cells whose
                ``periodo_hasta <= hasta``).
            q: Case-insensitive substring match on the ``informe`` report
                slug. An empty string is ignored server-side.
            limit: Page size (server validates ``1 <= limit <= 100``).
            offset: Zero-based offset (server validates ``offset >= 0``).

        Returns:
            ``{"items": [...], "total": int, "limit": int, "offset": int}`` —
            the raw envelope.
        """
        params = _build_params(desde=desde, hasta=hasta, q=q, limit=limit, offset=offset)
        return self._client._request("GET", self._path_prefix, params=params)

    def iter_all_estadisticas(
        self,
        *,
        desde: str | None = None,
        hasta: str | None = None,
        q: str | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Yield every statistics cell across all pages, paginating by offset.

        Uses a fixed page size of 100 and increments ``offset`` until the
        server returns an empty page (or a short final page). Yields each
        cell dict.
        """
        page_size = 100
        offset = 0
        while True:
            body = self.list_estadisticas(
                desde=desde, hasta=hasta, q=q, limit=page_size, offset=offset
            )
            items = self._extract_items(body)
            if not items:
                return
            yield from items
            if len(items) < page_size:
                return
            offset += page_size


class AsyncSCOMPResource(AsyncBaseResource):
    """Async mirror of :class:`SCOMPResource`."""

    _path_prefix = "/scomp"

    def __init__(self, client: AsyncCerberusClient) -> None:
        super().__init__(client)

    async def list_estadisticas(
        self,
        *,
        desde: str | None = None,
        hasta: str | None = None,
        q: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """Async variant of :meth:`SCOMPResource.list_estadisticas`."""
        params = _build_params(desde=desde, hasta=hasta, q=q, limit=limit, offset=offset)
        return await self._client._request("GET", self._path_prefix, params=params)

    async def iter_all_estadisticas(
        self,
        *,
        desde: str | None = None,
        hasta: str | None = None,
        q: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Async variant of :meth:`SCOMPResource.iter_all_estadisticas`."""
        page_size = 100
        offset = 0
        while True:
            body = await self.list_estadisticas(
                desde=desde, hasta=hasta, q=q, limit=page_size, offset=offset
            )
            items = self._extract_items(body)
            if not items:
                return
            for item in items:
                yield item
            if len(items) < page_size:
                return
            offset += page_size
