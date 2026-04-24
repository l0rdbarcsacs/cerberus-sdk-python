"""Typed accessor for the Cerberus Compliance ``/rpsf`` resource.

RPSF — *Registro Público de Servicios Financieros* — is the Chilean CMF
public registry of authorised financial-service providers. Each record
links an entity (by RUT) to one or more *servicios* (e.g. ``corredora``,
``agente``, ``custodia``), the governing framework (Ley 21.521 fintech
law, NCG 514…), and the current registration status.

The API exposes:

- ``GET /rpsf`` — list, with pagination + filters.
- ``GET /rpsf/{id}`` — fetch by internal RPSF id.
- ``GET /rpsf/by-entity/{entity_id}`` — list records for an entity.
- ``GET /rpsf/by-servicio/{servicio}`` — list records for a service class.

Example
-------
.. code-block:: python

    from cerberus_compliance import CerberusClient

    with CerberusClient() as client:
        for record in client.rpsf.iter_all(servicio="corredora"):
            print(record["entity_id"], record["status"])
"""

from __future__ import annotations

import builtins
from collections.abc import AsyncIterator, Iterator
from typing import Any
from urllib.parse import quote

from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource

__all__ = ["AsyncRPSFResource", "RPSFResource"]


def _clean_params(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Drop ``None`` values; return ``None`` when the dict is empty."""
    cleaned = {k: v for k, v in raw.items() if v is not None}
    return cleaned or None


class RPSFResource(BaseResource):
    """Sync accessor for the ``/rpsf`` endpoint family."""

    _path_prefix = "/rpsf"

    def list(self, **params: Any) -> list[dict[str, Any]]:
        """List RPSF records matching ``**params``.

        Accepts arbitrary forward-compatible filters (e.g. ``servicio``,
        ``status``, ``framework``, ``limit``). ``None`` values are
        stripped before the request so callers can pass optional args
        through ``**kwargs`` without polluting the query string.
        """
        return self._list(params=_clean_params(params))

    def get(self, id_: str) -> dict[str, Any]:
        """Fetch a single RPSF record by its internal id."""
        return self._get(id_)

    def by_entity(self, id_: str) -> builtins.list[dict[str, Any]]:
        """List every RPSF record attached to an entity.

        Issues ``GET /rpsf/by-entity/{id_}`` and unwraps the envelope
        defensively via :meth:`BaseResource._extract_items` so both
        ``{"data": [...]}`` and ``{"items": [...]}`` shapes are
        accepted.
        """
        body = self._client._request("GET", f"{self._path_prefix}/by-entity/{quote(id_, safe='')}")
        return self._extract_items(body)

    def by_servicio(self, servicio: str) -> builtins.list[dict[str, Any]]:
        """List every RPSF record for a given service class.

        Issues ``GET /rpsf/by-servicio/{servicio}``. The ``servicio``
        path segment is percent-encoded to survive values like
        ``"corredora de bolsa"``. The envelope is unwrapped via
        :meth:`BaseResource._extract_items` — both ``{"data"}`` and
        ``{"items"}`` shapes are accepted.
        """
        body = self._client._request(
            "GET", f"{self._path_prefix}/by-servicio/{quote(servicio, safe='')}"
        )
        return self._extract_items(body)

    def iter_all(self, **filters: Any) -> Iterator[dict[str, Any]]:
        """Cursor-paginate through every RPSF record matching ``filters``."""
        return self._iter_all(params=_clean_params(filters))


class AsyncRPSFResource(AsyncBaseResource):
    """Async mirror of :class:`RPSFResource`."""

    _path_prefix = "/rpsf"

    async def list(self, **params: Any) -> list[dict[str, Any]]:
        """Async variant of :meth:`RPSFResource.list`."""
        return await self._list(params=_clean_params(params))

    async def get(self, id_: str) -> dict[str, Any]:
        """Async variant of :meth:`RPSFResource.get`."""
        return await self._get(id_)

    async def by_entity(self, id_: str) -> builtins.list[dict[str, Any]]:
        """Async variant of :meth:`RPSFResource.by_entity`."""
        body = await self._client._request(
            "GET", f"{self._path_prefix}/by-entity/{quote(id_, safe='')}"
        )
        return self._extract_items(body)

    async def by_servicio(self, servicio: str) -> builtins.list[dict[str, Any]]:
        """Async variant of :meth:`RPSFResource.by_servicio`."""
        body = await self._client._request(
            "GET", f"{self._path_prefix}/by-servicio/{quote(servicio, safe='')}"
        )
        return self._extract_items(body)

    def iter_all(self, **filters: Any) -> AsyncIterator[dict[str, Any]]:
        """Async variant of :meth:`RPSFResource.iter_all`.

        Returns an :class:`AsyncIterator`; consume with ``async for``.
        """
        return self._iter_all(params=_clean_params(filters))
