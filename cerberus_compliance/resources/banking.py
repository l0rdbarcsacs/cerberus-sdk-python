"""Typed accessor for the Cerberus Compliance ``/banking`` resource.

The banking resource exposes prudential indicators ("indicadores") that the
CMF / SBIF publishes per banking institution and period. Each row is a single
indicator value for one bank in one month: ``banco_codigo`` is the SBIF
institution code (e.g. ``"001"`` — *not* a RUT), ``indicador_tipo`` is a free
text dotted slug (e.g. ``"patrimonio_efectivo.total"``), ``periodo`` is a
``"YYYY-MM"`` string compared lexicographically (not a date), and ``valor`` is
a :class:`~decimal.Decimal` monetary/ratio value (never a ``float`` —
Cerberus rule).

The list endpoint uses classic offset/limit pagination and returns the
envelope ``{"items": [...], "total": int, "limit": int, "offset": int}``
directly — *not* the cursor-paginated shape used by most of the SDK. Rows are
ordered by ``periodo`` descending (most recent first). We surface the raw
envelope on :meth:`list_indicadores` and offer :meth:`iter_all_indicadores`
as an offset-based convenience that walks every page without exposing offsets
to the caller.

The ``banco`` and ``tipo`` filters are *exact* matches; use ``q`` for a
case-insensitive substring match on the bank name (the server ignores an
empty ``q`` string, unlike the other filters).

Example
-------
.. code-block:: python

    from cerberus_compliance import CerberusClient

    with CerberusClient() as client:
        page = client.banking.list_indicadores(banco="001", limit=50)
        for row in client.banking.iter_all_indicadores(
            tipo="patrimonio_efectivo.total"
        ):
            print(row["periodo"], row["valor"])
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import TYPE_CHECKING, Any

from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource

if TYPE_CHECKING:
    from cerberus_compliance.client import AsyncCerberusClient, CerberusClient

__all__ = ["AsyncBankingResource", "BankingResource"]


def _build_indicadores_params(
    *,
    banco: str | None,
    tipo: str | None,
    desde: str | None,
    hasta: str | None,
    q: str | None,
    limit: int | None,
    offset: int | None,
) -> dict[str, Any] | None:
    """Assemble the ``/banking/indicadores`` query-string dict, dropping ``None``.

    Returns ``None`` when every parameter is unset so the request URL stays a
    bare ``/banking/indicadores`` without a trailing ``?``.
    """
    params: dict[str, Any] = {}
    if banco is not None:
        params["banco"] = banco
    if tipo is not None:
        params["tipo"] = tipo
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


class BankingResource(BaseResource):
    """Sync accessor for ``GET /banking/indicadores``.

    The list endpoint returns the offset/limit envelope
    ``{"items": [...], "total": int, "limit": int, "offset": int}``;
    pagination is offset-based rather than cursor-based.
    """

    _path_prefix = "/banking/indicadores"

    def __init__(self, client: CerberusClient) -> None:
        super().__init__(client)

    def list_indicadores(
        self,
        *,
        banco: str | None = None,
        tipo: str | None = None,
        desde: str | None = None,
        hasta: str | None = None,
        q: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """List banking prudential indicators, optionally filtered.

        Args:
            banco: SBIF institution code, exact match (e.g. ``"001"``).
                This is *not* a RUT.
            tipo: Dotted indicator slug, exact match
                (e.g. ``"patrimonio_efectivo.total"``). Free text, not an enum.
            desde: Minimum period (inclusive), ``"YYYY-MM"``. Compared as a
                lexicographic string, not a date.
            hasta: Maximum period (inclusive), ``"YYYY-MM"``. Compared as a
                lexicographic string.
            q: Case-insensitive substring match on the bank name. An empty
                string is ignored server-side.
            limit: Page size (server caps at 1..100; default 20).
            offset: Zero-based offset (server requires ``>= 0``; default 0).

        Returns:
            ``{"items": [...], "total": int, "limit": int, "offset": int}`` —
            the raw offset/limit envelope. Rows are ordered by ``periodo``
            descending.
        """
        params = _build_indicadores_params(
            banco=banco,
            tipo=tipo,
            desde=desde,
            hasta=hasta,
            q=q,
            limit=limit,
            offset=offset,
        )
        return self._client._request("GET", self._path_prefix, params=params)

    def iter_all_indicadores(
        self,
        *,
        banco: str | None = None,
        tipo: str | None = None,
        desde: str | None = None,
        hasta: str | None = None,
        q: str | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Yield every indicator across all pages, paginating by offset.

        Uses a fixed page size of 100 and increments ``offset`` until the
        server returns an empty page. The same filters as
        :meth:`list_indicadores` are forwarded on every request.
        """
        page_size = 100
        offset = 0
        while True:
            body = self.list_indicadores(
                banco=banco,
                tipo=tipo,
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


class AsyncBankingResource(AsyncBaseResource):
    """Async mirror of :class:`BankingResource`."""

    _path_prefix = "/banking/indicadores"

    def __init__(self, client: AsyncCerberusClient) -> None:
        super().__init__(client)

    async def list_indicadores(
        self,
        *,
        banco: str | None = None,
        tipo: str | None = None,
        desde: str | None = None,
        hasta: str | None = None,
        q: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """Async variant of :meth:`BankingResource.list_indicadores`."""
        params = _build_indicadores_params(
            banco=banco,
            tipo=tipo,
            desde=desde,
            hasta=hasta,
            q=q,
            limit=limit,
            offset=offset,
        )
        return await self._client._request("GET", self._path_prefix, params=params)

    async def iter_all_indicadores(
        self,
        *,
        banco: str | None = None,
        tipo: str | None = None,
        desde: str | None = None,
        hasta: str | None = None,
        q: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Async variant of :meth:`BankingResource.iter_all_indicadores`."""
        page_size = 100
        offset = 0
        while True:
            body = await self.list_indicadores(
                banco=banco,
                tipo=tipo,
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
