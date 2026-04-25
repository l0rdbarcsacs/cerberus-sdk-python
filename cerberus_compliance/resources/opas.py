"""Typed accessor for the Cerberus Compliance ``/opas`` resource.

OPAs (Ofertas Públicas de Adquisición) are public tender offers regulated
by CMF Title XXV of Ley 18.045. Each record describes the offer, the target
company, the offeror, acceptance period, and final outcome.

Example
-------
.. code-block:: python

    from cerberus_compliance import CerberusClient

    with CerberusClient() as client:
        page = client.opas.list(limit=10)
        offer = client.opas.get("opa-2024-001")
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource

__all__ = ["AsyncOPAsResource", "OPAsResource"]


def _clean_params(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Drop ``None`` values; return ``None`` when the dict is empty."""
    cleaned = {k: v for k, v in raw.items() if v is not None}
    return cleaned or None


class OPAsResource(BaseResource):
    """Sync accessor for the ``/opas`` endpoint family."""

    _path_prefix = "/opas"

    def list(self, **params: Any) -> list[dict[str, Any]]:
        """List OPA records matching ``**params``.

        Accepts arbitrary forward-compatible filters (e.g. ``limit``,
        ``offset``, ``target_rut``, ``offeror_rut``, ``year``).
        ``None`` values are stripped so callers can forward optional
        args through ``**kwargs``.
        """
        return self._list(params=_clean_params(params))

    def get(self, id_: str) -> dict[str, Any]:
        """Fetch a single OPA record by its canonical id."""
        return self._get(id_)

    def iter_all(self, **filters: Any) -> Iterator[dict[str, Any]]:
        """Cursor-paginate through every OPA record matching ``filters``."""
        return self._iter_all(params=_clean_params(filters))


class AsyncOPAsResource(AsyncBaseResource):
    """Async mirror of :class:`OPAsResource`."""

    _path_prefix = "/opas"

    async def list(self, **params: Any) -> list[dict[str, Any]]:
        """Async variant of :meth:`OPAsResource.list`."""
        return await self._list(params=_clean_params(params))

    async def get(self, id_: str) -> dict[str, Any]:
        """Async variant of :meth:`OPAsResource.get`."""
        return await self._get(id_)

    def iter_all(self, **filters: Any) -> AsyncIterator[dict[str, Any]]:
        """Async variant of :meth:`OPAsResource.iter_all`."""
        return self._iter_all(params=_clean_params(filters))
