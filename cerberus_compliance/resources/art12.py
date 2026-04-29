"""Typed accessor for the Cerberus Compliance ``/art12`` resource.

Art.12 records correspond to Artículo 12 of Ley 18.045 — disclosure
filings by controllers and major shareholders who acquire or dispose of
significant stakes (5 %+) in publicly traded Chilean companies. Each
record includes the filer, the target company, transaction date, stake
percentage, and transaction type.

Example
-------
.. code-block:: python

    from cerberus_compliance import CerberusClient

    with CerberusClient() as client:
        filings = client.art12.list(limit=20)
        filing = client.art12.get("art12-2024-00123")
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource

__all__ = ["Art12Resource", "AsyncArt12Resource"]


def _clean_params(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Drop ``None`` values; return ``None`` when the dict is empty."""
    cleaned = {k: v for k, v in raw.items() if v is not None}
    return cleaned or None


class Art12Resource(BaseResource):
    """Sync accessor for the ``/art12`` endpoint family."""

    _path_prefix = "/art12"

    def list(self, **params: Any) -> list[dict[str, Any]]:
        """List Art.12 filing records matching ``**params``.

        Accepts arbitrary forward-compatible filters (e.g. ``limit``,
        ``offset``, ``filer_rut``, ``target_rut``, ``from_date``,
        ``to_date``). ``None`` values are stripped so callers can forward
        optional args through ``**kwargs``.
        """
        return self._list(params=_clean_params(params))

    def get(self, id_: str) -> dict[str, Any]:
        """Deprecated. Prod no longer exposes ``GET /art12/{id}``.

        Use :meth:`list` with cursor-paginated ``**filters`` instead.
        """
        raise NotImplementedError(
            "GET /art12/{id} is not a real API endpoint; "
            "use .list(**filters) with cursor pagination instead."
        )

    def iter_all(self, **filters: Any) -> Iterator[dict[str, Any]]:
        """Cursor-paginate through every Art.12 filing matching ``filters``."""
        return self._iter_all(params=_clean_params(filters))


class AsyncArt12Resource(AsyncBaseResource):
    """Async mirror of :class:`Art12Resource`."""

    _path_prefix = "/art12"

    async def list(self, **params: Any) -> list[dict[str, Any]]:
        """Async variant of :meth:`Art12Resource.list`."""
        return await self._list(params=_clean_params(params))

    async def get(self, id_: str) -> dict[str, Any]:
        """Deprecated. Prod no longer exposes ``GET /art12/{id}``.

        Use :meth:`list` with cursor-paginated ``**filters`` instead.
        """
        raise NotImplementedError(
            "GET /art12/{id} is not a real API endpoint; "
            "use .list(**filters) with cursor pagination instead."
        )

    def iter_all(self, **filters: Any) -> AsyncIterator[dict[str, Any]]:
        """Async variant of :meth:`Art12Resource.iter_all`."""
        return self._iter_all(params=_clean_params(filters))
