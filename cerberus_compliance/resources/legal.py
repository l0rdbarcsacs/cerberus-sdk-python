"""Typed accessor for the Cerberus Compliance ``/legal/search`` resource.

Búsqueda semántica sobre el corpus legal consolidado de la BCN (leyes, decretos,
DFL, códigos) con filtros por faceta legal, estado y texto libre. Devuelve el
sobre paginado por cursor ``{"items": [...], "next_cursor": ..., "prev_cursor":
..., "limit": N}``. :meth:`LegalResource.iter_all` recorre la colección
siguiendo ``next_cursor``.

Example
-------
.. code-block:: python

    from cerberus_compliance import CerberusClient

    with CerberusClient() as client:
        page = client.legal.search(q="protección de datos", limit=10)
        for norma in client.legal.iter_all(facetas="proteccion_datos"):
            print(norma["numero"], norma["titulo"])
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import TYPE_CHECKING, Any

from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource

if TYPE_CHECKING:
    from cerberus_compliance.client import AsyncCerberusClient, CerberusClient

__all__ = ["AsyncLegalResource", "LegalResource"]


def _build_params(
    *,
    q: str | None,
    facetas: str | None,
    estado: str | None,
    cursor: str | None,
    limit: int | None,
) -> dict[str, Any] | None:
    """Assemble the ``/legal/search`` query dict, dropping ``None`` values."""
    params: dict[str, Any] = {}
    if q is not None:
        params["q"] = q
    if facetas is not None:
        params["facetas"] = facetas
    if estado is not None:
        params["estado"] = estado
    if cursor is not None:
        params["cursor"] = cursor
    if limit is not None:
        params["limit"] = limit
    return params or None


class LegalResource(BaseResource):
    """Sync accessor for ``GET /legal/search`` (scope ``legal:read``)."""

    _path_prefix = "/legal/search"

    def __init__(self, client: CerberusClient) -> None:
        super().__init__(client)

    def search(
        self,
        *,
        q: str | None = None,
        facetas: str | None = None,
        estado: str | None = None,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Search the consolidated legal corpus (``GET /legal/search``).

        Args:
            q: free-text query over title/full text.
            facetas: rama del derecho clasificada (faceta legal).
            estado: filtra por estado de la norma (p.ej. ``vigente``).
            cursor: opaque cursor from a prior page's ``next_cursor``.
            limit: page size.

        Returns:
            ``{"items": [...], "next_cursor": str|None,
            "prev_cursor": str|None, "limit": int}``.
        """
        params = _build_params(q=q, facetas=facetas, estado=estado, cursor=cursor, limit=limit)
        return self._client._request("GET", self._path_prefix, params=params)

    def iter_all(
        self,
        *,
        q: str | None = None,
        facetas: str | None = None,
        estado: str | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Yield every legal norm across all cursor pages of ``GET /legal/search``."""
        return self._iter_all(
            params=_build_params(q=q, facetas=facetas, estado=estado, cursor=None, limit=None)
        )


class AsyncLegalResource(AsyncBaseResource):
    """Async mirror of :class:`LegalResource`."""

    _path_prefix = "/legal/search"

    def __init__(self, client: AsyncCerberusClient) -> None:
        super().__init__(client)

    async def search(
        self,
        *,
        q: str | None = None,
        facetas: str | None = None,
        estado: str | None = None,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Async variant of :meth:`LegalResource.search`."""
        params = _build_params(q=q, facetas=facetas, estado=estado, cursor=cursor, limit=limit)
        return await self._client._request("GET", self._path_prefix, params=params)

    def iter_all(
        self,
        *,
        q: str | None = None,
        facetas: str | None = None,
        estado: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Async variant of :meth:`LegalResource.iter_all`."""
        return self._iter_all(
            params=_build_params(q=q, facetas=facetas, estado=estado, cursor=None, limit=None)
        )
