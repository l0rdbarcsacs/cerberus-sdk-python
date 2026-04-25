"""Typed accessor for the Cerberus Compliance ``/esg/{rut}`` resource.

ESG records expose the environmental, social, and governance profile
for a Chilean legal entity as derived from CMF NCG 461 disclosures.
NCG 461 (issued 2023) requires publicly listed companies to publish
annual sustainability reports; the Cerberus platform aggregates these
disclosures and exposes them as structured JSON keyed on the entity's
RUT.

Unlike most other resources the ESG surface is entity-centric (keyed
on RUT) rather than a paginated collection. The ``get(rut)`` method
returns the full consolidated ESG dossier; the ``list`` method is
provided for callers who need to enumerate all entities with ESG data.

Example
-------
.. code-block:: python

    from cerberus_compliance import CerberusClient

    with CerberusClient() as client:
        profile = client.esg.get("96505760-9")
        all_profiles = client.esg.list(limit=50)
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource, _encode_id

__all__ = ["AsyncESGResource", "ESGResource"]


def _clean_params(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Drop ``None`` values; return ``None`` when the dict is empty."""
    cleaned = {k: v for k, v in raw.items() if v is not None}
    return cleaned or None


class ESGResource(BaseResource):
    """Sync accessor for the ``/esg`` endpoint family.

    The primary method is :meth:`get` (``GET /esg/{rut}``), which
    returns the full ESG dossier for a single entity. :meth:`list`
    enumerates all entities that have published ESG data under NCG 461.
    """

    _path_prefix = "/esg"

    def get(self, rut: str) -> dict[str, Any]:
        """Fetch the ESG dossier for a single entity by its RUT.

        The ``rut`` is percent-encoded to prevent path traversal.
        Returns the full NCG 461 disclosure profile for the entity.
        """
        path = f"{self._path_prefix}/{_encode_id(rut)}"
        return self._client._request("GET", path)

    def list(self, **params: Any) -> list[dict[str, Any]]:
        """List ESG profiles matching ``**params``.

        Accepts arbitrary forward-compatible filters (e.g. ``limit``,
        ``offset``, ``sector``). ``None`` values are stripped so callers
        can forward optional args through ``**kwargs``.
        """
        return self._list(params=_clean_params(params))

    def iter_all(self, **filters: Any) -> Iterator[dict[str, Any]]:
        """Cursor-paginate through every ESG profile matching ``filters``."""
        return self._iter_all(params=_clean_params(filters))


class AsyncESGResource(AsyncBaseResource):
    """Async mirror of :class:`ESGResource`."""

    _path_prefix = "/esg"

    async def get(self, rut: str) -> dict[str, Any]:
        """Async variant of :meth:`ESGResource.get`."""
        path = f"{self._path_prefix}/{_encode_id(rut)}"
        return await self._client._request("GET", path)

    async def list(self, **params: Any) -> list[dict[str, Any]]:
        """Async variant of :meth:`ESGResource.list`."""
        return await self._list(params=_clean_params(params))

    def iter_all(self, **filters: Any) -> AsyncIterator[dict[str, Any]]:
        """Async variant of :meth:`ESGResource.iter_all`."""
        return self._iter_all(params=_clean_params(filters))
