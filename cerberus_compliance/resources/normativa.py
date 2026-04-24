"""Typed accessor for the Cerberus Compliance ``/normativa`` resource.

Normativa records are the authoritative regulatory texts the platform
tracks — Chilean laws (Ley 21.521, Ley 21.719), CMF norms (NCG 514,
NCG 454), plus anchor-point international frameworks (SOX, MiFID). Each
record carries the canonical citation, a structured summary, and the
``/normativa/{id}/mercado`` sub-endpoint which resolves the market
segments a given norm applies to.

Example
-------
.. code-block:: python

    from cerberus_compliance import CerberusClient

    with CerberusClient() as client:
        norm = client.normativa.get("ley-21521")
        segments = client.normativa.mercado("ley-21521")
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource, _encode_id

__all__ = ["AsyncNormativaResource", "NormativaResource"]


def _clean_params(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Drop ``None`` values; return ``None`` when the dict is empty."""
    cleaned = {k: v for k, v in raw.items() if v is not None}
    return cleaned or None


class NormativaResource(BaseResource):
    """Sync accessor for the ``/normativa`` endpoint family."""

    _path_prefix = "/normativa"

    def list(self, **params: Any) -> list[dict[str, Any]]:
        """List normativa records matching ``**params``.

        Accepts arbitrary forward-compatible filters (e.g. ``framework``,
        ``country``, ``active``, ``limit``). ``None`` values are stripped
        so callers can forward optional args through ``**kwargs``.
        """
        return self._list(params=_clean_params(params))

    def get(self, id_: str) -> dict[str, Any]:
        """Fetch a single normativa record by its canonical id."""
        return self._get(id_)

    def mercado(self, id_: str) -> dict[str, Any]:
        """Return the market-segment mapping for a normativa record.

        Issues ``GET /normativa/{id}/mercado`` and returns the parsed
        JSON body verbatim — the endpoint is an aggregate document, not
        a list envelope, so we do not unwrap ``data``.
        """
        path = f"{self._path_prefix}/{_encode_id(id_)}/mercado"
        return self._client._request("GET", path)

    def iter_all(self, **filters: Any) -> Iterator[dict[str, Any]]:
        """Cursor-paginate through every normativa record matching ``filters``."""
        return self._iter_all(params=_clean_params(filters))


class AsyncNormativaResource(AsyncBaseResource):
    """Async mirror of :class:`NormativaResource`."""

    _path_prefix = "/normativa"

    async def list(self, **params: Any) -> list[dict[str, Any]]:
        """Async variant of :meth:`NormativaResource.list`."""
        return await self._list(params=_clean_params(params))

    async def get(self, id_: str) -> dict[str, Any]:
        """Async variant of :meth:`NormativaResource.get`."""
        return await self._get(id_)

    async def mercado(self, id_: str) -> dict[str, Any]:
        """Async variant of :meth:`NormativaResource.mercado`."""
        path = f"{self._path_prefix}/{_encode_id(id_)}/mercado"
        return await self._client._request("GET", path)

    def iter_all(self, **filters: Any) -> AsyncIterator[dict[str, Any]]:
        """Async variant of :meth:`NormativaResource.iter_all`."""
        return self._iter_all(params=_clean_params(filters))
