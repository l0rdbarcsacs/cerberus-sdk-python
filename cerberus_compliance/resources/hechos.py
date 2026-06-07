"""Typed accessor for the Cerberus Compliance ``/hechos`` resource family.

*Hechos esenciales* are the material-event disclosures Chilean issuers,
banks, and other supervised entities file with the CMF. The Cerberus API
splits them across three sibling routers, each with its own scope and a
slightly different item schema:

* ``GET /hechos`` (``hechos:read``) — issuer disclosures, with a
  structured ``event_type`` taxonomy and an aggregate
  ``GET /hechos/event-types`` distribution.
* ``GET /hechos/bancos`` (``hechos_bancos:read``) — banking-supervision
  disclosures sourced from ``datosbanco.cmfchile.cl``.
* ``GET /hechos/otros`` (``hechos_otros:read``) — non-issuer/non-bank
  entities (insurers, AGFs, brokers, residual ``otro``).

Every listing uses *offset-based* pagination (``limit`` / ``offset``),
**not** the cursor envelope used elsewhere in the SDK; each call returns
the raw ``{"items": [...], "total": N, "limit": L, "offset": O}`` dict.
:meth:`HechosResource.iter_all` walks the main ``/hechos`` collection by
advancing ``offset`` until ``offset >= total``.

Beware the per-router contract drift: ``/hechos/otros`` treats ``hasta``
as **inclusive** (``<=``) and filters ``q`` over ``entidad_nombre``,
whereas ``/hechos`` and ``/hechos/bancos`` use an **exclusive** ``hasta``
(``<``) and filter ``q`` over ``asunto``.

Example
-------
.. code-block:: python

    from cerberus_compliance import CerberusClient

    with CerberusClient() as client:
        page = client.hechos.list_hechos(rut="76.543.210-9", event_type="dividend")
        dist = client.hechos.hechos_event_type_distribution(desde="2026-01-01")
        for hecho in client.hechos.iter_all(q="aumento de capital"):
            print(hecho["publicacion_at"], hecho["asunto"])
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any, Literal

from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource

__all__ = ["AsyncHechosResource", "HechoEventType", "HechosResource"]

#: Structured ``event_type`` taxonomy (B4) for issuer *hechos esenciales*.
#: An unknown value yields an empty page server-side (no 422), so the
#: alias is advisory rather than strictly enforced on the wire.
HechoEventType = Literal[
    "dividend",
    "m_and_a",
    "board_change",
    "financial_results",
    "capital_increase",
    "rating_change",
    "litigation",
    "bond_issuance",
    "shareholder_meeting",
    "regulatory_filing",
    "other",
]


class HechosResource(BaseResource):
    """Synchronous accessor for the ``/hechos`` router family.

    Each listing returns the raw offset-paginated envelope
    ``{"items": [...], "total": int, "limit": int, "offset": int}``.
    The three listings carry distinct scopes (``hechos:read``,
    ``hechos_bancos:read``, ``hechos_otros:read``) and item schemas.
    """

    _path_prefix = "/hechos"

    def list_hechos(
        self,
        *,
        rut: str | None = None,
        desde: str | None = None,
        hasta: str | None = None,
        q: str | None = None,
        event_type: HechoEventType | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """List issuer *hechos esenciales* (``GET /hechos``).

        Args:
            rut: Any RUT format (dots/DV optional); canonicalised
                server-side. A canonicalisation failure yields an empty
                page (``items=[]``, ``total=0``), not a 422.
            desde: ISO-8601 ``YYYY-MM-DD``; ``publicacion_at >= desde``
                (inclusive).
            hasta: ISO-8601 ``YYYY-MM-DD``; ``publicacion_at < hasta``
                (**exclusive**).
            q: Case-insensitive substring (ILIKE) over ``asunto``.
            event_type: One of the :data:`HechoEventType` labels; an
                unknown value yields an empty page rather than a 422.
            limit: Page size (1-100); out of range yields 422.
            offset: Zero-based row offset (>= 0); offset-based pagination.

        Returns:
            ``{"items": [...], "total": int, "limit": int,
            "offset": int}`` — the raw envelope.
        """
        params: dict[str, Any] = {}
        if rut is not None:
            params["rut"] = rut
        if desde is not None:
            params["desde"] = desde
        if hasta is not None:
            params["hasta"] = hasta
        if q is not None:
            params["q"] = q
        if event_type is not None:
            params["event_type"] = event_type
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        return self._client._request("GET", self._path_prefix, params=params or None)

    def iter_all(
        self,
        *,
        rut: str | None = None,
        desde: str | None = None,
        hasta: str | None = None,
        q: str | None = None,
        event_type: HechoEventType | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Yield every issuer *hecho* across all pages of ``GET /hechos``.

        Uses a fixed page size of 100 and advances ``offset`` until the
        server reports ``offset >= total`` (or an empty page). Filters
        match :meth:`list_hechos`.
        """
        page_size = 100
        offset = 0
        while True:
            body = self.list_hechos(
                rut=rut,
                desde=desde,
                hasta=hasta,
                q=q,
                event_type=event_type,
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

    def hechos_event_type_distribution(
        self,
        *,
        desde: str | None = None,
        hasta: str | None = None,
    ) -> dict[str, Any]:
        """Aggregate ``event_type`` distribution (``GET /hechos/event-types``).

        Public anonymised aggregate (Ley 21.719): bucket counts over the
        non-reserved corpus only — no names, RUTs, or per-entity data.
        Not paginated.

        Args:
            desde: ISO-8601 ``YYYY-MM-DD``; ``publicacion_at >= desde``
                (inclusive).
            hasta: ISO-8601 ``YYYY-MM-DD``; ``publicacion_at < hasta``
                (**exclusive**).

        Returns:
            ``{"total": int, "buckets": [{"event_type": str | None,
            "count": int}]}`` — buckets ordered by ``count`` descending;
            the ``null`` bucket holds not-yet-typed events.
        """
        params: dict[str, Any] = {}
        if desde is not None:
            params["desde"] = desde
        if hasta is not None:
            params["hasta"] = hasta
        return self._client._request(
            "GET", f"{self._path_prefix}/event-types", params=params or None
        )

    def list_hechos_bancos(
        self,
        *,
        entity_id: str | None = None,
        rut: str | None = None,
        nombre: str | None = None,
        desde: str | None = None,
        hasta: str | None = None,
        q: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """List banking-supervision *hechos* (``GET /hechos/bancos``).

        Scope ``hechos_bancos:read`` (distinct from ``hechos:read``).
        Item schema differs from ``/hechos``: ``fecha_publicacion`` /
        ``fecha_hecho`` (``date``) and ``documento_url`` instead of
        ``publicacion_at`` / ``source_url``.

        Args:
            entity_id: Resolved bank FK (``cmf_entities.id``); an invalid
                UUID yields 422 (validated by FastAPI).
            rut: Any RUT format; canonicalised best-effort (bank rows use
                synthetic placeholder RUTs). Failure yields an empty page.
            nombre: Case-insensitive substring (ILIKE) over
                ``entidad_nombre`` — a parameter **separate** from ``q``.
            desde: ISO-8601 ``YYYY-MM-DD``; ``fecha_publicacion >= desde``
                (inclusive).
            hasta: ISO-8601 ``YYYY-MM-DD``; ``fecha_publicacion < hasta``
                (**exclusive**).
            q: Case-insensitive substring (ILIKE) over ``asunto``.
            limit: Page size (1-100).
            offset: Zero-based row offset (>= 0).

        Returns:
            ``{"items": [...], "total": int, "limit": int,
            "offset": int}`` — the raw envelope.
        """
        params: dict[str, Any] = {}
        if entity_id is not None:
            params["entity_id"] = entity_id
        if rut is not None:
            params["rut"] = rut
        if nombre is not None:
            params["nombre"] = nombre
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
        return self._client._request("GET", f"{self._path_prefix}/bancos", params=params or None)

    def list_hechos_otros(
        self,
        *,
        rut: str | None = None,
        entity_kind: str | None = None,
        desde: str | None = None,
        hasta: str | None = None,
        q: str | None = None,
        entity_id: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """List non-issuer/non-bank *hechos* (``GET /hechos/otros``).

        Scope ``hechos_otros:read``. Covers insurers, AGFs, brokers, and
        a residual ``otro`` kind. The item schema adds ``entity_kind``
        and ``created_at`` (``datetime``).

        Contract drift vs. its siblings: ``hasta`` is **inclusive**
        (``<=``), ``q`` matches ``entidad_nombre`` (not ``asunto``), and
        an ``entity_kind`` filter is available.

        Args:
            rut: Any RUT format; canonicalised, matched over
                ``entidad_rut`` (many synthetic placeholder RUTs). Failure
                yields an empty page.
            entity_kind: Exact match over ``entity_kind``
                (``aseguradora``, ``agf``, ``corredor_bolsa``, ``otro``).
                Not validated against an enum: an unknown value simply
                matches nothing (empty page), not a 422.
            desde: ISO-8601 ``YYYY-MM-DD``; ``fecha_publicacion >= desde``
                (inclusive).
            hasta: ISO-8601 ``YYYY-MM-DD``; ``fecha_publicacion <= hasta``
                (**inclusive** — differs from the sibling routers).
            q: Case-insensitive substring (ILIKE) over ``entidad_nombre``.
            entity_id: Resolved FK (``cmf_entities.id``); an invalid UUID
                yields 422.
            limit: Page size (1-100).
            offset: Zero-based row offset (>= 0).

        Returns:
            ``{"items": [...], "total": int, "limit": int,
            "offset": int}`` — the raw envelope.
        """
        params: dict[str, Any] = {}
        if rut is not None:
            params["rut"] = rut
        if entity_kind is not None:
            params["entity_kind"] = entity_kind
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
        return self._client._request("GET", f"{self._path_prefix}/otros", params=params or None)


class AsyncHechosResource(AsyncBaseResource):
    """Asynchronous mirror of :class:`HechosResource`.

    Every method is awaitable; :meth:`iter_all` returns an
    :class:`~collections.abc.AsyncIterator` rather than a coroutine.
    """

    _path_prefix = "/hechos"

    async def list_hechos(
        self,
        *,
        rut: str | None = None,
        desde: str | None = None,
        hasta: str | None = None,
        q: str | None = None,
        event_type: HechoEventType | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """Async variant of :meth:`HechosResource.list_hechos`."""
        params: dict[str, Any] = {}
        if rut is not None:
            params["rut"] = rut
        if desde is not None:
            params["desde"] = desde
        if hasta is not None:
            params["hasta"] = hasta
        if q is not None:
            params["q"] = q
        if event_type is not None:
            params["event_type"] = event_type
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        return await self._client._request("GET", self._path_prefix, params=params or None)

    async def iter_all(
        self,
        *,
        rut: str | None = None,
        desde: str | None = None,
        hasta: str | None = None,
        q: str | None = None,
        event_type: HechoEventType | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Async variant of :meth:`HechosResource.iter_all`."""
        page_size = 100
        offset = 0
        while True:
            body = await self.list_hechos(
                rut=rut,
                desde=desde,
                hasta=hasta,
                q=q,
                event_type=event_type,
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

    async def hechos_event_type_distribution(
        self,
        *,
        desde: str | None = None,
        hasta: str | None = None,
    ) -> dict[str, Any]:
        """Async variant of :meth:`HechosResource.hechos_event_type_distribution`."""
        params: dict[str, Any] = {}
        if desde is not None:
            params["desde"] = desde
        if hasta is not None:
            params["hasta"] = hasta
        return await self._client._request(
            "GET", f"{self._path_prefix}/event-types", params=params or None
        )

    async def list_hechos_bancos(
        self,
        *,
        entity_id: str | None = None,
        rut: str | None = None,
        nombre: str | None = None,
        desde: str | None = None,
        hasta: str | None = None,
        q: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """Async variant of :meth:`HechosResource.list_hechos_bancos`."""
        params: dict[str, Any] = {}
        if entity_id is not None:
            params["entity_id"] = entity_id
        if rut is not None:
            params["rut"] = rut
        if nombre is not None:
            params["nombre"] = nombre
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
        return await self._client._request(
            "GET", f"{self._path_prefix}/bancos", params=params or None
        )

    async def list_hechos_otros(
        self,
        *,
        rut: str | None = None,
        entity_kind: str | None = None,
        desde: str | None = None,
        hasta: str | None = None,
        q: str | None = None,
        entity_id: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """Async variant of :meth:`HechosResource.list_hechos_otros`."""
        params: dict[str, Any] = {}
        if rut is not None:
            params["rut"] = rut
        if entity_kind is not None:
            params["entity_kind"] = entity_kind
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
        return await self._client._request(
            "GET", f"{self._path_prefix}/otros", params=params or None
        )
