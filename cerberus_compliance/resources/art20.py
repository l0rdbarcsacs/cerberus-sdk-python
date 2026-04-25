"""Typed accessor for the Cerberus Compliance ``/art20`` resource.

Art.20 records correspond to Artículo 20 of Ley 18.045 — material event
(hecho esencial) disclosures that publicly listed Chilean companies must
file with the CMF within one business day of a significant corporate event
(mergers, changes of control, material contracts, litigation, etc.). Each
record includes the filing entity, event date, filing date, and a
structured event summary.

Example
-------
.. code-block:: python

    from cerberus_compliance import CerberusClient

    with CerberusClient() as client:
        events = client.art20.list(limit=20, entity_rut="96505760-9")
        event = client.art20.get("art20-2024-001234")
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource

__all__ = ["Art20Resource", "AsyncArt20Resource"]


def _clean_params(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Drop ``None`` values; return ``None`` when the dict is empty."""
    cleaned = {k: v for k, v in raw.items() if v is not None}
    return cleaned or None


class Art20Resource(BaseResource):
    """Sync accessor for the ``/art20`` endpoint family."""

    _path_prefix = "/art20"

    def list(self, **params: Any) -> list[dict[str, Any]]:
        """List Art.20 hecho-esencial records matching ``**params``.

        Accepts arbitrary forward-compatible filters (e.g. ``limit``,
        ``offset``, ``entity_rut``, ``from_date``, ``to_date``,
        ``event_type``). ``None`` values are stripped so callers can
        forward optional args through ``**kwargs``.
        """
        return self._list(params=_clean_params(params))

    def get(self, id_: str) -> dict[str, Any]:
        """Fetch a single Art.20 hecho-esencial by its canonical id."""
        return self._get(id_)

    def iter_all(self, **filters: Any) -> Iterator[dict[str, Any]]:
        """Cursor-paginate through every Art.20 record matching ``filters``."""
        return self._iter_all(params=_clean_params(filters))


class AsyncArt20Resource(AsyncBaseResource):
    """Async mirror of :class:`Art20Resource`."""

    _path_prefix = "/art20"

    async def list(self, **params: Any) -> list[dict[str, Any]]:
        """Async variant of :meth:`Art20Resource.list`."""
        return await self._list(params=_clean_params(params))

    async def get(self, id_: str) -> dict[str, Any]:
        """Async variant of :meth:`Art20Resource.get`."""
        return await self._get(id_)

    def iter_all(self, **filters: Any) -> AsyncIterator[dict[str, Any]]:
        """Async variant of :meth:`Art20Resource.iter_all`."""
        return self._iter_all(params=_clean_params(filters))
