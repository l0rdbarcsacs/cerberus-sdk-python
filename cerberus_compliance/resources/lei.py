"""Typed accessor for the Cerberus Compliance ``/lei`` resource (SDK-01).

The ``/lei`` family exposes the GLEIF **Legal Entity Identifier** registry
mirrored into ``cmf_lei_records``: each record carries the 20-char ISO 17442
code, the legal name/address, the GLEIF registration status, the direct and
ultimate parent LEI, and the Chilean RUT extracted from the GLEIF record when
present.

Unlike the cursor-paginated collections, ``/lei`` paginates by ``limit`` /
``offset`` and returns an ``{items, total, limit, offset}`` envelope, so
:meth:`LeiResource.iter_all` walks by offset rather than cursor.

Example
-------
.. code-block:: python

    from cerberus_compliance import CerberusClient

    with CerberusClient() as client:
        page = client.lei.list(jurisdiction="CL", limit=50)
        record = client.lei.get("5493001KJTIIGC8Y1R12")
        for rec in client.lei.iter_all(registration_status="ISSUED"):
            ...
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource

__all__ = ["AsyncLeiResource", "LeiResource"]

#: Server-side page cap for ``GET /v1/lei`` (``le=100``); the default iteration
#: page size for :meth:`LeiResource.iter_all`.
_MAX_PAGE_SIZE = 100


def _list_params(
    *,
    jurisdiction: str | None,
    registration_status: str | None,
    rut: str | None,
    limit: int | None,
    offset: int | None,
) -> dict[str, Any] | None:
    """Assemble the ``GET /lei`` query dict, dropping ``None`` values."""
    raw: dict[str, Any] = {
        "jurisdiction": jurisdiction,
        "registration_status": registration_status,
        "rut": rut,
        "limit": limit,
        "offset": offset,
    }
    cleaned = {k: v for k, v in raw.items() if v is not None}
    return cleaned or None


class LeiResource(BaseResource):
    """Synchronous accessor for the ``/lei`` GLEIF registry endpoint family."""

    _path_prefix = "/lei"

    def list(
        self,
        *,
        jurisdiction: str | None = None,
        registration_status: str | None = None,
        rut: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[dict[str, Any]]:
        """List LEI records matching the supplied filters.

        Args:
            jurisdiction: ISO 3166-1 alpha-2 jurisdiction (e.g. ``"CL"``).
            registration_status: GLEIF status (e.g. ``"ISSUED"``, ``"LAPSED"``).
            rut: Chilean RUT extracted from the GLEIF record; canonicalised
                server-side so dotted / DV-less inputs still match.
            limit: Page size (server default 20, max 100).
            offset: Zero-based offset.

        Returns:
            The ``items`` array of the paginated envelope.
        """
        return self._list(
            params=_list_params(
                jurisdiction=jurisdiction,
                registration_status=registration_status,
                rut=rut,
                limit=limit,
                offset=offset,
            )
        )

    def get(self, lei: str) -> dict[str, Any]:
        """Fetch a single LEI record by its 20-char code (case-insensitive)."""
        return self._get(lei)

    def iter_all(
        self,
        *,
        jurisdiction: str | None = None,
        registration_status: str | None = None,
        rut: str | None = None,
        page_size: int = _MAX_PAGE_SIZE,
    ) -> Iterator[dict[str, Any]]:
        """Walk every matching LEI record, paginating by ``offset``.

        ``/lei`` is not cursor-paginated, so this issues successive
        ``?limit=&offset=`` requests until a short page (or ``offset >=
        total``) signals the end.
        """
        offset = 0
        while True:
            body = self._client._request(
                "GET",
                self._path_prefix,
                params=_list_params(
                    jurisdiction=jurisdiction,
                    registration_status=registration_status,
                    rut=rut,
                    limit=page_size,
                    offset=offset,
                ),
            )
            items = self._extract_items(body)
            yield from items
            offset += len(items)
            total = body.get("total")
            if not items or len(items) < page_size or (isinstance(total, int) and offset >= total):
                return


class AsyncLeiResource(AsyncBaseResource):
    """Asynchronous mirror of :class:`LeiResource`."""

    _path_prefix = "/lei"

    async def list(
        self,
        *,
        jurisdiction: str | None = None,
        registration_status: str | None = None,
        rut: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[dict[str, Any]]:
        """Async variant of :meth:`LeiResource.list`."""
        return await self._list(
            params=_list_params(
                jurisdiction=jurisdiction,
                registration_status=registration_status,
                rut=rut,
                limit=limit,
                offset=offset,
            )
        )

    async def get(self, lei: str) -> dict[str, Any]:
        """Async variant of :meth:`LeiResource.get`."""
        return await self._get(lei)

    async def iter_all(
        self,
        *,
        jurisdiction: str | None = None,
        registration_status: str | None = None,
        rut: str | None = None,
        page_size: int = _MAX_PAGE_SIZE,
    ) -> AsyncIterator[dict[str, Any]]:
        """Async variant of :meth:`LeiResource.iter_all` (paginates by offset)."""
        offset = 0
        while True:
            body = await self._client._request(
                "GET",
                self._path_prefix,
                params=_list_params(
                    jurisdiction=jurisdiction,
                    registration_status=registration_status,
                    rut=rut,
                    limit=page_size,
                    offset=offset,
                ),
            )
            items = self._extract_items(body)
            for item in items:
                yield item
            offset += len(items)
            total = body.get("total")
            if not items or len(items) < page_size or (isinstance(total, int) and offset >= total):
                return
