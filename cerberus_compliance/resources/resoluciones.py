"""Typed accessor for the Cerberus Compliance ``/resoluciones`` resource.

Resoluciones are formal CMF resolutions — numbered administrative acts that
amend regulations, impose sanctions, or approve corporate operations. Each
record carries the resolution number, date, subject entity (if applicable),
and a structured summary.

Example
-------
.. code-block:: python

    from cerberus_compliance import CerberusClient

    with CerberusClient() as client:
        page = client.resoluciones.list(limit=20)
        detail = client.resoluciones.get("res-2024-0042")
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource

__all__ = ["AsyncResolucionesResource", "ResolucionesResource"]


def _clean_params(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Drop ``None`` values; return ``None`` when the dict is empty."""
    cleaned = {k: v for k, v in raw.items() if v is not None}
    return cleaned or None


class ResolucionesResource(BaseResource):
    """Sync accessor for the ``/resoluciones`` endpoint family."""

    _path_prefix = "/resoluciones"

    def list(self, **params: Any) -> list[dict[str, Any]]:
        """List resolucion records matching ``**params``.

        Accepts arbitrary forward-compatible filters (e.g. ``limit``,
        ``offset``, ``year``, ``entity_rut``). ``None`` values are stripped
        so callers can forward optional args through ``**kwargs``.
        """
        return self._list(params=_clean_params(params))

    def get(self, id_: str) -> dict[str, Any]:
        """Deprecated. Prod no longer exposes ``GET /resoluciones/{id}``.

        Use :meth:`list` with cursor-paginated ``**filters`` instead.
        """
        raise NotImplementedError(
            "GET /resoluciones/{id} is not a real API endpoint; "
            "use .list(**filters) with cursor pagination instead."
        )

    def iter_all(self, **filters: Any) -> Iterator[dict[str, Any]]:
        """Cursor-paginate through every resolucion record matching ``filters``."""
        return self._iter_all(params=_clean_params(filters))


class AsyncResolucionesResource(AsyncBaseResource):
    """Async mirror of :class:`ResolucionesResource`."""

    _path_prefix = "/resoluciones"

    async def list(self, **params: Any) -> list[dict[str, Any]]:
        """Async variant of :meth:`ResolucionesResource.list`."""
        return await self._list(params=_clean_params(params))

    async def get(self, id_: str) -> dict[str, Any]:
        """Deprecated. Prod no longer exposes ``GET /resoluciones/{id}``.

        Use :meth:`list` with cursor-paginated ``**filters`` instead.
        """
        raise NotImplementedError(
            "GET /resoluciones/{id} is not a real API endpoint; "
            "use .list(**filters) with cursor pagination instead."
        )

    def iter_all(self, **filters: Any) -> AsyncIterator[dict[str, Any]]:
        """Async variant of :meth:`ResolucionesResource.iter_all`."""
        return self._iter_all(params=_clean_params(filters))
