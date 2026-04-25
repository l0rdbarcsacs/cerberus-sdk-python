"""Typed accessor for the Cerberus Compliance ``/dictamenes`` resource.

Dictámenes are formal legal opinions and rulings issued by the CMF
(Comisión para el Mercado Financiero) in response to queries from
regulated entities, legal practitioners, or the public. Each record
carries the ruling number, issue date, requesting party category,
subject matter, and the full ruling text or structured summary.

Example
-------
.. code-block:: python

    from cerberus_compliance import CerberusClient

    with CerberusClient() as client:
        rulings = client.dictamenes.list(limit=20)
        ruling = client.dictamenes.get("dict-2024-0045")
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource

__all__ = ["AsyncDictamenesResource", "DictamenesResource"]


def _clean_params(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Drop ``None`` values; return ``None`` when the dict is empty."""
    cleaned = {k: v for k, v in raw.items() if v is not None}
    return cleaned or None


class DictamenesResource(BaseResource):
    """Sync accessor for the ``/dictamenes`` endpoint family."""

    _path_prefix = "/dictamenes"

    def list(self, **params: Any) -> list[dict[str, Any]]:
        """List dictamen records matching ``**params``.

        Accepts arbitrary forward-compatible filters (e.g. ``limit``,
        ``offset``, ``year``, ``subject``, ``requestor_type``).
        ``None`` values are stripped so callers can forward optional
        args through ``**kwargs``.
        """
        return self._list(params=_clean_params(params))

    def get(self, id_: str) -> dict[str, Any]:
        """Fetch a single dictamen by its canonical id."""
        return self._get(id_)

    def iter_all(self, **filters: Any) -> Iterator[dict[str, Any]]:
        """Cursor-paginate through every dictamen record matching ``filters``."""
        return self._iter_all(params=_clean_params(filters))


class AsyncDictamenesResource(AsyncBaseResource):
    """Async mirror of :class:`DictamenesResource`."""

    _path_prefix = "/dictamenes"

    async def list(self, **params: Any) -> list[dict[str, Any]]:
        """Async variant of :meth:`DictamenesResource.list`."""
        return await self._list(params=_clean_params(params))

    async def get(self, id_: str) -> dict[str, Any]:
        """Async variant of :meth:`DictamenesResource.get`."""
        return await self._get(id_)

    def iter_all(self, **filters: Any) -> AsyncIterator[dict[str, Any]]:
        """Async variant of :meth:`DictamenesResource.iter_all`."""
        return self._iter_all(params=_clean_params(filters))
