"""Typed accessor for the Cerberus Compliance ``/tdc`` resource.

TDC (Tasa de Descuento de Cartera) records represent the CMF-published
portfolio discount rates used in pension fund and insurance portfolio
valuations. Each record carries the effective date, instrument category,
and published rate expressed as a string for exact decimal precision.

Example
-------
.. code-block:: python

    from cerberus_compliance import CerberusClient

    with CerberusClient() as client:
        rates = client.tdc.list(limit=50)
        rate = client.tdc.get("tdc-2024-01-15-rv")
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource

__all__ = ["AsyncTDCResource", "TDCResource"]


def _clean_params(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Drop ``None`` values; return ``None`` when the dict is empty."""
    cleaned = {k: v for k, v in raw.items() if v is not None}
    return cleaned or None


class TDCResource(BaseResource):
    """Sync accessor for the ``/tdc`` endpoint family."""

    _path_prefix = "/tdc"

    def list(self, **params: Any) -> list[dict[str, Any]]:
        """List TDC records matching ``**params``.

        Accepts arbitrary forward-compatible filters (e.g. ``limit``,
        ``offset``, ``from_date``, ``to_date``, ``category``).
        ``None`` values are stripped so callers can forward optional
        args through ``**kwargs``.
        """
        return self._list(params=_clean_params(params))

    def get(self, id_: str) -> dict[str, Any]:
        """Fetch a single TDC record by its canonical id."""
        return self._get(id_)

    def iter_all(self, **filters: Any) -> Iterator[dict[str, Any]]:
        """Cursor-paginate through every TDC record matching ``filters``."""
        return self._iter_all(params=_clean_params(filters))


class AsyncTDCResource(AsyncBaseResource):
    """Async mirror of :class:`TDCResource`."""

    _path_prefix = "/tdc"

    async def list(self, **params: Any) -> list[dict[str, Any]]:
        """Async variant of :meth:`TDCResource.list`."""
        return await self._list(params=_clean_params(params))

    async def get(self, id_: str) -> dict[str, Any]:
        """Async variant of :meth:`TDCResource.get`."""
        return await self._get(id_)

    def iter_all(self, **filters: Any) -> AsyncIterator[dict[str, Any]]:
        """Async variant of :meth:`TDCResource.iter_all`."""
        return self._iter_all(params=_clean_params(filters))
