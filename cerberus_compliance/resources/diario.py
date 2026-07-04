"""Typed accessor for the Cerberus Compliance ``/diario`` resource.

The *Diario Oficial* feed surfaces the corporate-lifecycle events Chilean
entities publish in the official gazette — incorporations, amendments,
mergers, dissolutions, and the like. The Cerberus API exposes a single
listing at ``GET /diario`` (scope ``diario:read``) with rich filters
(``rut``, ``tipo``, ``desde``/``hasta`` date window, free-text ``q`` over
``razon_social``, resolved ``entity_id``) over a fixed ``fecha_publicacion``
descending sort.

Pagination is *offset-based* (``limit`` / ``offset``), **not** the cursor
envelope used by most of the SDK; each call returns the raw
``{"items": [...], "total": N, "limit": L, "offset": O}`` dict.
:meth:`DiarioResource.iter_all` walks the collection by advancing
``offset`` until ``offset >= total`` (or an empty page).

Each item carries an optional ``sii`` identity block (M5) joined by
``rut_canonical`` against the SII records. Note (Ley 21.719): the SII
tributary lifecycle ``estado`` is **never** exposed here.

Example
-------
.. code-block:: python

    from cerberus_compliance import CerberusClient

    with CerberusClient() as client:
        page = client.diario.list_eventos(tipo="fusion", desde="2026-01-01")
        for evento in client.diario.iter_all(rut="76.543.210-9"):
            print(evento["fecha_publicacion"], evento["razon_social"])
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import TYPE_CHECKING, Any, Literal

from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource

if TYPE_CHECKING:
    from cerberus_compliance.client import AsyncCerberusClient, CerberusClient

__all__ = [
    "AsyncDiarioResource",
    "DiarioEventoTipo",
    "DiarioNormaTipo",
    "DiarioResource",
]

#: Tipo de instrumento de una norma del Cuerpo I del Diario Oficial
#: (``DoNormaTipo``). Un valor fuera del enum produce un **422**.
DiarioNormaTipo = Literal[
    "ley",
    "decreto_supremo",
    "dfl",
    "decreto_ley",
    "resolucion_exenta",
    "reglamento",
    "otro",
]


def _build_normas_params(
    *,
    tipo: DiarioNormaTipo | None,
    desde: str | None,
    hasta: str | None,
    faceta: str | None,
    q: str | None,
    limit: int | None,
    offset: int | None,
) -> dict[str, Any] | None:
    """Assemble the ``/diario/normas`` query dict, dropping ``None`` values."""
    params: dict[str, Any] = {}
    if tipo is not None:
        params["tipo"] = tipo
    if desde is not None:
        params["desde"] = desde
    if hasta is not None:
        params["hasta"] = hasta
    if faceta is not None:
        params["faceta"] = faceta
    if q is not None:
        params["q"] = q
    if limit is not None:
        params["limit"] = limit
    if offset is not None:
        params["offset"] = offset
    return params or None


#: The ``DoEventoTipo`` StrEnum that classifies each *Diario Oficial*
#: corporate-lifecycle event. Unlike the advisory taxonomies elsewhere in
#: the SDK, an out-of-enum value here yields a **422** (FastAPI validation),
#: so this alias is enforced on the wire.
DiarioEventoTipo = Literal[
    "constitucion",
    "modificacion",
    "transformacion",
    "disolucion",
    "fusion",
    "division",
    "liquidacion",
    "otro",
]


def _build_params(
    *,
    rut: str | None,
    tipo: DiarioEventoTipo | None,
    desde: str | None,
    hasta: str | None,
    q: str | None,
    entity_id: str | None,
    limit: int | None,
    offset: int | None,
) -> dict[str, Any] | None:
    """Assemble the ``/diario`` query-string dict, dropping ``None`` values.

    Returns ``None`` when every filter is unset so the request URL stays a
    bare ``/diario`` without a trailing ``?``.
    """
    params: dict[str, Any] = {}
    if rut is not None:
        params["rut"] = rut
    if tipo is not None:
        params["tipo"] = tipo
    if desde is not None:
        params["desde"] = desde
    if hasta is not None:
        params["hasta"] = hasta
    if q is not None:
        params["q"] = q
    if entity_id is not None:
        params["entity_id"] = entity_id
    if limit is not None:
        params["limit"] = limit
    if offset is not None:
        params["offset"] = offset
    return params or None


class DiarioResource(BaseResource):
    """Synchronous accessor for ``GET /diario`` (scope ``diario:read``).

    The listing returns the raw offset-paginated envelope
    ``{"items": [...], "total": int, "limit": int, "offset": int}``;
    pagination is offset-based rather than cursor-based, and results are
    ordered by ``fecha_publicacion`` descending (newest first).
    """

    _path_prefix = "/diario"

    def __init__(self, client: CerberusClient) -> None:
        super().__init__(client)

    def list_eventos(
        self,
        *,
        rut: str | None = None,
        tipo: DiarioEventoTipo | None = None,
        desde: str | None = None,
        hasta: str | None = None,
        q: str | None = None,
        entity_id: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """List *Diario Oficial* corporate-lifecycle events (``GET /diario``).

        Args:
            rut: Any RUT format (dots/DV optional); canonicalised
                server-side and matched against ``rut_canonical``. A
                canonicalisation failure yields an empty page
                (``items=[]``, ``total=0``) rather than a 422/404.
            tipo: One of the :data:`DiarioEventoTipo` labels. An
                out-of-enum value yields a **422** (FastAPI validation).
            desde: ISO-8601 ``YYYY-MM-DD``; ``fecha_publicacion >= desde``
                (inclusive).
            hasta: ISO-8601 ``YYYY-MM-DD``; ``fecha_publicacion <= hasta``
                (inclusive).
            q: Case-insensitive substring (ILIKE) over ``razon_social``;
                only applied when truthy.
            entity_id: Resolved FK to ``cmf_entities`` (very sparse — the
                Diario rarely prints a RUT). Must be a valid UUID or 422.
            limit: Page size (1-100, default 20 server-side); out of range
                yields 422.
            offset: Zero-based row offset (>= 0); offset-based pagination.

        Returns:
            ``{"items": [...], "total": int, "limit": int,
            "offset": int}`` — the raw envelope.
        """
        params = _build_params(
            rut=rut,
            tipo=tipo,
            desde=desde,
            hasta=hasta,
            q=q,
            entity_id=entity_id,
            limit=limit,
            offset=offset,
        )
        return self._client._request("GET", self._path_prefix, params=params)

    def iter_all(
        self,
        *,
        rut: str | None = None,
        tipo: DiarioEventoTipo | None = None,
        desde: str | None = None,
        hasta: str | None = None,
        q: str | None = None,
        entity_id: str | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Yield every event across all pages of ``GET /diario``.

        Uses a fixed page size of 100 and advances ``offset`` until the
        server reports ``offset >= total`` (or an empty page). Filters
        match :meth:`list_eventos`.
        """
        page_size = 100
        offset = 0
        while True:
            body = self.list_eventos(
                rut=rut,
                tipo=tipo,
                desde=desde,
                hasta=hasta,
                q=q,
                entity_id=entity_id,
                limit=page_size,
                offset=offset,
            )
            items = self._extract_items(body)
            if not items:
                return
            yield from items
            offset += len(items)
            total = body.get("total")
            if isinstance(total, int) and offset >= total:
                return
            if len(items) < page_size:
                return

    def list_normas(
        self,
        *,
        tipo: DiarioNormaTipo | None = None,
        desde: str | None = None,
        hasta: str | None = None,
        faceta: str | None = None,
        q: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """List general norms from the DO's Cuerpo I (``GET /diario/normas``).

        Leyes, decretos, DFL, resoluciones exentas y reglamentos publicados en
        la Sección Normas Generales, con sus facetas legales clasificadas.

        Args:
            tipo: One of :data:`DiarioNormaTipo`; out-of-enum yields **422**.
            desde/hasta: ISO-8601 ``YYYY-MM-DD`` sobre ``fecha_publicacion``.
            faceta: rama del derecho clasificada (solapamiento de facetas).
            q: substring case-insensitive sobre el título.
            limit: page size (1-100, default 20); offset: base-cero.

        Returns:
            ``{"items": [...], "total": int, "limit": int, "offset": int}``.
        """
        params = _build_normas_params(
            tipo=tipo, desde=desde, hasta=hasta, faceta=faceta, q=q, limit=limit, offset=offset
        )
        return self._client._request("GET", f"{self._path_prefix}/normas", params=params)

    def iter_all_normas(
        self,
        *,
        tipo: DiarioNormaTipo | None = None,
        desde: str | None = None,
        hasta: str | None = None,
        faceta: str | None = None,
        q: str | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Yield every norm across all pages of ``GET /diario/normas``."""
        page_size = 100
        offset = 0
        while True:
            body = self.list_normas(
                tipo=tipo,
                desde=desde,
                hasta=hasta,
                faceta=faceta,
                q=q,
                limit=page_size,
                offset=offset,
            )
            items = self._extract_items(body)
            if not items:
                return
            yield from items
            offset += len(items)
            total = body.get("total")
            if isinstance(total, int) and offset >= total:
                return
            if len(items) < page_size:
                return


class AsyncDiarioResource(AsyncBaseResource):
    """Asynchronous mirror of :class:`DiarioResource`.

    Every method is awaitable; :meth:`iter_all` returns an
    :class:`~collections.abc.AsyncIterator` rather than a coroutine.
    """

    _path_prefix = "/diario"

    def __init__(self, client: AsyncCerberusClient) -> None:
        super().__init__(client)

    async def list_eventos(
        self,
        *,
        rut: str | None = None,
        tipo: DiarioEventoTipo | None = None,
        desde: str | None = None,
        hasta: str | None = None,
        q: str | None = None,
        entity_id: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """Async variant of :meth:`DiarioResource.list_eventos`."""
        params = _build_params(
            rut=rut,
            tipo=tipo,
            desde=desde,
            hasta=hasta,
            q=q,
            entity_id=entity_id,
            limit=limit,
            offset=offset,
        )
        return await self._client._request("GET", self._path_prefix, params=params)

    async def iter_all(
        self,
        *,
        rut: str | None = None,
        tipo: DiarioEventoTipo | None = None,
        desde: str | None = None,
        hasta: str | None = None,
        q: str | None = None,
        entity_id: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Async variant of :meth:`DiarioResource.iter_all`."""
        page_size = 100
        offset = 0
        while True:
            body = await self.list_eventos(
                rut=rut,
                tipo=tipo,
                desde=desde,
                hasta=hasta,
                q=q,
                entity_id=entity_id,
                limit=page_size,
                offset=offset,
            )
            items = self._extract_items(body)
            if not items:
                return
            for item in items:
                yield item
            offset += len(items)
            total = body.get("total")
            if isinstance(total, int) and offset >= total:
                return
            if len(items) < page_size:
                return

    async def list_normas(
        self,
        *,
        tipo: DiarioNormaTipo | None = None,
        desde: str | None = None,
        hasta: str | None = None,
        faceta: str | None = None,
        q: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """Async variant of :meth:`DiarioResource.list_normas`."""
        params = _build_normas_params(
            tipo=tipo, desde=desde, hasta=hasta, faceta=faceta, q=q, limit=limit, offset=offset
        )
        return await self._client._request("GET", f"{self._path_prefix}/normas", params=params)

    async def iter_all_normas(
        self,
        *,
        tipo: DiarioNormaTipo | None = None,
        desde: str | None = None,
        hasta: str | None = None,
        faceta: str | None = None,
        q: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Async variant of :meth:`DiarioResource.iter_all_normas`."""
        page_size = 100
        offset = 0
        while True:
            body = await self.list_normas(
                tipo=tipo,
                desde=desde,
                hasta=hasta,
                faceta=faceta,
                q=q,
                limit=page_size,
                offset=offset,
            )
            items = self._extract_items(body)
            if not items:
                return
            for item in items:
                yield item
            offset += len(items)
            total = body.get("total")
            if isinstance(total, int) and offset >= total:
                return
            if len(items) < page_size:
                return
