"""Typed accessor for the Cerberus Compliance ``/comunicaciones`` resource.

Comunicaciones are official CMF communications — numbered circulars,
letters, and notices addressed to regulated entities or published for
general market information. Each record carries the communication number,
issue date, addressee category, subject, and a structured body summary.

Example
-------
.. code-block:: python

    from cerberus_compliance import CerberusClient

    with CerberusClient() as client:
        circulars = client.comunicaciones.list(limit=20)
        circular = client.comunicaciones.get("com-2024-0123")
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource

__all__ = ["AsyncComunicacionesResource", "ComunicacionesResource"]


def _clean_params(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Drop ``None`` values; return ``None`` when the dict is empty."""
    cleaned = {k: v for k, v in raw.items() if v is not None}
    return cleaned or None


class ComunicacionesResource(BaseResource):
    """Sync accessor for the ``/comunicaciones`` endpoint family."""

    _path_prefix = "/comunicaciones"

    def list(self, **params: Any) -> list[dict[str, Any]]:
        """List comunicaciones records matching ``**params``.

        Accepts arbitrary forward-compatible filters (e.g. ``limit``,
        ``offset``, ``year``, ``addressee_type``, ``subject``).
        ``None`` values are stripped so callers can forward optional
        args through ``**kwargs``.
        """
        return self._list(params=_clean_params(params))

    def get(self, id_: str) -> dict[str, Any]:
        """Deprecated. Prod no longer exposes ``GET /comunicaciones/{id}``.

        Use :meth:`list` with cursor-paginated ``**filters`` instead.
        """
        raise NotImplementedError(
            "GET /comunicaciones/{id} is not a real API endpoint; "
            "use .list(**filters) with cursor pagination instead."
        )

    def iter_all(self, **filters: Any) -> Iterator[dict[str, Any]]:
        """Cursor-paginate through every comunicacion record matching ``filters``."""
        return self._iter_all(params=_clean_params(filters))


class AsyncComunicacionesResource(AsyncBaseResource):
    """Async mirror of :class:`ComunicacionesResource`."""

    _path_prefix = "/comunicaciones"

    async def list(self, **params: Any) -> list[dict[str, Any]]:
        """Async variant of :meth:`ComunicacionesResource.list`."""
        return await self._list(params=_clean_params(params))

    async def get(self, id_: str) -> dict[str, Any]:
        """Deprecated. Prod no longer exposes ``GET /comunicaciones/{id}``.

        Use :meth:`list` with cursor-paginated ``**filters`` instead.
        """
        raise NotImplementedError(
            "GET /comunicaciones/{id} is not a real API endpoint; "
            "use .list(**filters) with cursor pagination instead."
        )

    def iter_all(self, **filters: Any) -> AsyncIterator[dict[str, Any]]:
        """Async variant of :meth:`ComunicacionesResource.iter_all`."""
        return self._iter_all(params=_clean_params(filters))
