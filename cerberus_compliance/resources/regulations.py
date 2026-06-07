"""``/regulations`` sub-resource — regulatory-compliance applicability.

A *regulation* record answers the question: *which normative framework
(Chilean Ley 21.521 / Ley 21.719 / NCG 514, or international SOX / MiFID)
applies to which entity, and with what status?* The API exposes two
read-only endpoints — ``GET /regulations`` (list, filterable by
``entity_id`` and ``framework``) and ``GET /regulations/<id>`` (detail).

Both sync and async flavours of the resource delegate to the cursor-
pagination helpers on :class:`~cerberus_compliance.resources._base.BaseResource`
/ :class:`~cerberus_compliance.resources._base.AsyncBaseResource`.

Example
-------
.. code-block:: python

    from cerberus_compliance import CerberusClient

    client = CerberusClient(api_key="ck_live_...")
    regs = client.regulations.list(entity_id="ent_1", framework="Ley21521")

    for rec in client.regulations.iter_all(framework="SOX"):
        ...
"""

from __future__ import annotations

import builtins
from collections.abc import AsyncIterator, Iterator
from typing import Any, Literal

from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource, _encode_id

__all__ = [
    "AsyncRegulationsResource",
    "RegulationFramework",
    "RegulationType",
    "RegulationsResource",
]

RegulationFramework = Literal["Ley21521", "Ley21719", "NCG514", "SOX", "MiFID"]
"""Supported regulatory frameworks recognised by the Cerberus API."""

RegulationType = Literal["ncg", "circular", "oficio", "other"]
"""Normative-document types recognised by the Cerberus API.

Mirrors the backend ``RegulationType`` enum. ``dictamen`` / ``instructivo``
are documented as forward-compatible values but are not emitted yet, so they
are intentionally absent from this literal.
"""


def _build_params(**raw: Any) -> dict[str, Any] | None:
    """Assemble a query-parameter dict, dropping any values that are ``None``.

    Returns ``None`` when no parameters remain so the transport layer can
    skip emitting an empty query string.
    """
    params = {key: value for key, value in raw.items() if value is not None}
    return params or None


class RegulationsResource(BaseResource):
    """Sync accessor for the ``/regulations`` endpoint.

    Exposes :meth:`list`, :meth:`get`, and :meth:`iter_all` over the
    shared :class:`BaseResource` helpers.
    """

    _path_prefix = "/regulations"

    def list(
        self,
        *,
        entity_id: str | None = None,
        framework: RegulationFramework | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return a single page of regulation records.

        All filters are optional; ``None`` values are omitted from the
        outgoing query string. The server decides the default page size
        when ``limit`` is not supplied.
        """
        params = _build_params(entity_id=entity_id, framework=framework, limit=limit)
        return self._list(params=params)

    def get(self, id_: str) -> dict[str, Any]:
        """Fetch a single regulation record by its identifier."""
        return self._get(id_)

    def search(self, q: str, **params: Any) -> builtins.list[dict[str, Any]]:
        """Full-text search of regulation records.

        Issues ``GET /regulations/search?q=<q>`` and unwraps the
        envelope via :meth:`BaseResource._extract_items` so both
        ``{"data": [...]}`` and ``{"items": [...]}`` shapes are
        accepted. Extra ``**params`` (e.g. ``framework``, ``limit``)
        are forwarded verbatim; ``None`` values are stripped.
        """
        query: dict[str, Any] = {"q": q}
        query.update({k: v for k, v in params.items() if v is not None})
        body = self._client._request("GET", f"{self._path_prefix}/search", params=query)
        return self._extract_items(body)

    def lineage(self, regulation_id: str) -> dict[str, Any]:
        """Return the supersession chain for a single regulation.

        Issues ``GET /regulations/<regulation_id>/lineage`` and returns the
        aggregate object verbatim — ``{"id", "supersedes", "superseded_by"}``,
        where each entry of ``supersedes`` / ``superseded_by`` is a
        ``RegulationLineageRef`` (``id``, ``type``, ``title``,
        ``ncg_number``, ``circular_number``, ``estado``). The response is a
        single JSON object, not a paginated list or envelope.

        ``regulation_id`` must be a parseable UUID server-side; a non-UUID
        value yields a ``422`` from the API. The path segment is
        percent-encoded so callers can pass the raw identifier.
        """
        path = f"{self._path_prefix}/{_encode_id(regulation_id)}/lineage"
        return self._client._request("GET", path)

    def iter_all(self, **filters: Any) -> Iterator[dict[str, Any]]:
        """Cursor-paginate through every matching regulation record.

        Accepts the same filters as :meth:`list` (``entity_id``,
        ``framework``, ``limit``) via keyword arguments, plus any
        forward-compatible server-side filters the caller wishes to
        pass through. ``None`` values are stripped; the server's
        cursor is forwarded automatically on each subsequent page.
        """
        return self._iter_all(params=_build_params(**filters))


class AsyncRegulationsResource(AsyncBaseResource):
    """Async mirror of :class:`RegulationsResource`."""

    _path_prefix = "/regulations"

    async def list(
        self,
        *,
        entity_id: str | None = None,
        framework: RegulationFramework | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Async variant of :meth:`RegulationsResource.list`."""
        params = _build_params(entity_id=entity_id, framework=framework, limit=limit)
        return await self._list(params=params)

    async def get(self, id_: str) -> dict[str, Any]:
        """Async variant of :meth:`RegulationsResource.get`."""
        return await self._get(id_)

    async def search(self, q: str, **params: Any) -> builtins.list[dict[str, Any]]:
        """Async variant of :meth:`RegulationsResource.search`."""
        query: dict[str, Any] = {"q": q}
        query.update({k: v for k, v in params.items() if v is not None})
        body = await self._client._request("GET", f"{self._path_prefix}/search", params=query)
        return self._extract_items(body)

    async def lineage(self, regulation_id: str) -> dict[str, Any]:
        """Async variant of :meth:`RegulationsResource.lineage`."""
        path = f"{self._path_prefix}/{_encode_id(regulation_id)}/lineage"
        return await self._client._request("GET", path)

    def iter_all(self, **filters: Any) -> AsyncIterator[dict[str, Any]]:
        """Async variant of :meth:`RegulationsResource.iter_all`.

        Returns an :class:`AsyncIterator`; consume with ``async for``.
        """
        return self._iter_all(params=_build_params(**filters))
