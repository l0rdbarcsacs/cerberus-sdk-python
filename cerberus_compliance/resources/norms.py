"""``/norms`` sub-resource — citation graph over Chilean CMF norms.

A *norm* is a regulatory instrument (NCG, circular, oficio, ...) parsed
from the CMF corpus. This resource exposes two read-only, **public**
aggregate endpoints over the resolved citation links between sanctions /
dictámenes and the norms they invoke:

* ``GET /norms/top-cited`` — the most-cited norms, ranked by
  ``citation_count`` descending (then ``regulation_id`` ascending),
  returned as a plain envelope ``{"norms": [...], "total": N}``.
* ``GET /norms/{regulation_id}/citations`` — the citing rows that point
  at a single norm, returned as ``{"regulation_id": ..., "ncg_number":
  ..., "circular_number": ..., "citations": [...], "total": N}``.

Both endpoints are **counts/aggregates only** — no entity or person
names are exposed, per Ley 21.719. Only *resolved* citation links
(``resolved=True``) are counted. ``total`` is the number of rows in the
returned page (bounded by ``limit``), **not** a grand total: neither
endpoint is cursor-paginated.

Both flavours require the ``regulations:read`` scope.

Example
-------
.. code-block:: python

    from cerberus_compliance import CerberusClient

    with CerberusClient(api_key="ck_live_...") as client:
        ranking = client.norms.top_cited(limit=10)
        for norm in ranking["norms"]:
            print(norm["title"], norm["citation_count"])

        detail = client.norms.citations("0f....-uuid", limit=200)
        for row in detail["citations"]:
            print(row["source_table"], row["raw_citation"])
"""

from __future__ import annotations

from typing import Any, Literal

from cerberus_compliance.resources._base import (
    AsyncBaseResource,
    BaseResource,
    _encode_id,
)

__all__ = [
    "AsyncNormsResource",
    "NormsResource",
    "RegulationType",
]

RegulationType = Literal["ncg", "circular", "oficio", "other"]
"""The ``type`` discriminator on a top-cited norm row.

Mirrors the server-side ``RegulationType`` enum: ``ncg``, ``circular``,
``oficio`` or ``other``. Modelled as a string ``Literal`` rather than
free text so callers get autocomplete and mypy coverage.
"""


def _build_params(**raw: Any) -> dict[str, Any] | None:
    """Assemble a query-parameter dict, dropping any values that are ``None``.

    Returns ``None`` when no parameters remain so the transport layer can
    skip emitting an empty query string.
    """
    params = {key: value for key, value in raw.items() if value is not None}
    return params or None


class NormsResource(BaseResource):
    """Sync accessor for the ``/norms`` citation endpoints.

    Exposes :meth:`top_cited` (ranked aggregate) and :meth:`citations`
    (per-norm citing rows). Both return the raw server envelope as a
    ``dict``; neither is cursor-paginated, so there is no ``iter_all``.
    """

    _path_prefix = "/norms"

    def top_cited(self, *, limit: int | None = None) -> dict[str, Any]:
        """Return the most-cited norms, ranked by ``citation_count``.

        Issues ``GET /norms/top-cited``. The response is a plain envelope
        ``{"norms": [...], "total": N}`` where ``total`` equals the number
        of rows in this page (bounded by ``limit``), **not** a grand
        total. Norms are ordered by ``citation_count`` descending then
        ``regulation_id`` ascending; only resolved citation links count.

        Args:
            limit: Optional page size. The server bounds it to ``[1, 100]``
                and defaults to ``20`` when omitted; out-of-range values
                yield ``422`` server-side. ``None`` is dropped from the
                query string.

        Returns:
            The parsed JSON body (see the module docstring for the shape).
        """
        params = _build_params(limit=limit)
        return self._client._request("GET", f"{self._path_prefix}/top-cited", params=params)

    def citations(self, regulation_id: str, *, limit: int | None = None) -> dict[str, Any]:
        """Return the citing rows that point at a single norm.

        Issues ``GET /norms/{regulation_id}/citations``. Returns ``200``
        with an empty ``citations`` list (``total=0``) when the norm
        exists but no resolved citation points at it. ``total`` is the
        number of rows in this page (bounded by ``limit``), **not** a
        grand total; only resolved links are returned, ordered by
        ``source_table`` then ``source_id`` ascending.

        Args:
            regulation_id: The norm's UUID. Percent-encoded into the path.
                A malformed UUID yields ``422`` and a well-formed-but-
                unknown UUID yields ``404`` server-side.
            limit: Optional cap on citing rows. The server bounds it to
                ``[1, 500]`` and defaults to ``500`` when omitted;
                out-of-range values yield ``422`` server-side. ``None`` is
                dropped from the query string.

        Returns:
            The parsed JSON body (see the module docstring for the shape).
        """
        path = f"{self._path_prefix}/{_encode_id(regulation_id)}/citations"
        params = _build_params(limit=limit)
        return self._client._request("GET", path, params=params)


class AsyncNormsResource(AsyncBaseResource):
    """Async mirror of :class:`NormsResource`."""

    _path_prefix = "/norms"

    async def top_cited(self, *, limit: int | None = None) -> dict[str, Any]:
        """Async variant of :meth:`NormsResource.top_cited`."""
        params = _build_params(limit=limit)
        return await self._client._request("GET", f"{self._path_prefix}/top-cited", params=params)

    async def citations(self, regulation_id: str, *, limit: int | None = None) -> dict[str, Any]:
        """Async variant of :meth:`NormsResource.citations`."""
        path = f"{self._path_prefix}/{_encode_id(regulation_id)}/citations"
        params = _build_params(limit=limit)
        return await self._client._request("GET", path, params=params)
