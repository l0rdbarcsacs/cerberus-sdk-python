"""Typed accessor for the Cerberus Compliance ``/normativa/historic`` resource.

The historic normativa resource exposes the point-in-time version history
of CMF regulatory texts. While ``/normativa`` returns the current
(live) version of each norm, ``/normativa/historic`` returns the full
edit trail — each record is a snapshot of a regulation at a specific
effective date, enabling callers to reconstruct the regulatory state as
it existed at any past moment.

This is particularly useful for:

* Retroactive compliance checks (what was the rule on date X?).
* Change-log diffing across CMF norm versions.
* Audit trails for regulated entities.

Example
-------
.. code-block:: python

    from cerberus_compliance import CerberusClient

    with CerberusClient() as client:
        history = client.normativa_historic.list(regulation_id="ncg-461")
        snapshot = client.normativa_historic.get("ncg-461-v2023-06-01")
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource

__all__ = ["AsyncNormativaHistoricResource", "NormativaHistoricResource"]


def _clean_params(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Drop ``None`` values; return ``None`` when the dict is empty."""
    cleaned = {k: v for k, v in raw.items() if v is not None}
    return cleaned or None


class NormativaHistoricResource(BaseResource):
    """Sync accessor for the ``/normativa/historic`` endpoint family."""

    _path_prefix = "/normativa/historic"

    def list(self, **params: Any) -> list[dict[str, Any]]:
        """List historic normativa snapshots matching ``**params``.

        Accepts arbitrary forward-compatible filters (e.g. ``limit``,
        ``offset``, ``regulation_id``, ``as_of``, ``framework``).
        ``None`` values are stripped so callers can forward optional
        args through ``**kwargs``.
        """
        return self._list(params=_clean_params(params))

    def get(self, id_: str) -> dict[str, Any]:
        """Fetch a single historic normativa snapshot by its canonical id."""
        return self._get(id_)

    def iter_all(self, **filters: Any) -> Iterator[dict[str, Any]]:
        """Cursor-paginate through every historic snapshot matching ``filters``."""
        return self._iter_all(params=_clean_params(filters))


class AsyncNormativaHistoricResource(AsyncBaseResource):
    """Async mirror of :class:`NormativaHistoricResource`."""

    _path_prefix = "/normativa/historic"

    async def list(self, **params: Any) -> list[dict[str, Any]]:
        """Async variant of :meth:`NormativaHistoricResource.list`."""
        return await self._list(params=_clean_params(params))

    async def get(self, id_: str) -> dict[str, Any]:
        """Async variant of :meth:`NormativaHistoricResource.get`."""
        return await self._get(id_)

    def iter_all(self, **filters: Any) -> AsyncIterator[dict[str, Any]]:
        """Async variant of :meth:`NormativaHistoricResource.iter_all`."""
        return self._iter_all(params=_clean_params(filters))
