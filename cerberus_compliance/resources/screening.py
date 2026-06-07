"""Typed accessor for the Cerberus Compliance ``/screening`` resource.

Screening surfaces sanction-contagion exposure derived from the entity
knowledge graph: how close a given Chilean legal entity (or person) is
to a sanctioned counterparty, traversing the contagion edge types
``DIRECTS`` / ``INTERLOCKS_WITH`` / ``MEMBER_OF`` / ``CONTROLS`` up to
two hops.

Two surfaces are exposed:

* :meth:`ScreeningResource.get_exposure` (``GET
  /screening/{rut}/exposure``) — the per-named, authenticated view.
  Requires the ``screening:read`` scope. It names the sanctioned
  counterparties connected to a single entity (Ley 21.719: a CUST /
  authenticated surface).
* :meth:`ScreeningResource.get_exposure_distribution` (``GET
  /screening/exposure/distribution``) — a public, anonymised histogram
  of exposure scores across all scored entities. Counts only; never any
  entity name, RUT, or per-named score.

Neither surface is paginated or streamed.

Example
-------
.. code-block:: python

    from cerberus_compliance import CerberusClient

    with CerberusClient() as client:
        exposure = client.screening.get_exposure("96505760-9")
        if exposure["has_exposure"]:
            for node in exposure["connected_sanctioned"]:
                print(node["name"], node["hop_distance"])
        histogram = client.screening.get_exposure_distribution()
"""

from __future__ import annotations

from typing import Any

from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource, _encode_id

__all__ = ["AsyncScreeningResource", "ScreeningResource"]


class ScreeningResource(BaseResource):
    """Sync accessor for the ``/screening`` endpoint family.

    The two methods mirror the two router surfaces: :meth:`get_exposure`
    for the authenticated per-named view and
    :meth:`get_exposure_distribution` for the public anonymised
    histogram.
    """

    _path_prefix = "/screening"

    def get_exposure(self, rut: str) -> dict[str, Any]:
        """Fetch sanction-contagion exposure for a single entity by RUT.

        Issues ``GET /screening/{rut}/exposure``. Requires the
        ``screening:read`` scope.

        The ``rut`` is forwarded verbatim (any accepted format) but
        percent-encoded for the path so it cannot escape the prefix; the
        server canonicalises it. An unparseable RUT raises
        :class:`~cerberus_compliance.errors.ValidationError` (HTTP 422).

        The endpoint returns ``200`` with ``has_exposure=False`` and an
        empty ``connected_sanctioned`` list when no sanctioned node is
        within two hops — it does *not* return ``404`` in that case.

        Returns:
            ``{"rut": str, "node_type": str | None, "has_exposure":
            bool, "exposure_score": float, "connected_sanctioned":
            [{"node_type": str, "rut": str | None, "name": str | None,
            "sanction_source": "cmf_entity" | "cmf_persona" |
            "external", "sanction_detail": str | None, "hop_distance":
            int, "relationship_path": [str], "node_exposure_score":
            float}, ...]}``.
        """
        path = f"{self._path_prefix}/{_encode_id(rut)}/exposure"
        return self._client._request("GET", path)

    def get_exposure_distribution(self) -> dict[str, Any]:
        """Fetch the public anonymised exposure-score histogram.

        Issues ``GET /screening/exposure/distribution``. Requires the
        ``screening:read`` scope. Takes no path or query params and
        carries no request body.

        Buckets whose count falls below ``suppression_threshold`` (fixed
        at ``5`` in the current impl) are omitted entirely, so the
        ``buckets`` list may contain fewer than four entries and is not
        guaranteed to cover all of ``none``/``low``/``medium``/``high``.

        Returns:
            ``{"total_scored": int, "suppression_threshold": int,
            "buckets": [{"bucket": str, "count": int}, ...]}``.
        """
        return self._client._request("GET", f"{self._path_prefix}/exposure/distribution")


class AsyncScreeningResource(AsyncBaseResource):
    """Async mirror of :class:`ScreeningResource`."""

    _path_prefix = "/screening"

    async def get_exposure(self, rut: str) -> dict[str, Any]:
        """Async variant of :meth:`ScreeningResource.get_exposure`."""
        path = f"{self._path_prefix}/{_encode_id(rut)}/exposure"
        return await self._client._request("GET", path)

    async def get_exposure_distribution(self) -> dict[str, Any]:
        """Async variant of :meth:`ScreeningResource.get_exposure_distribution`."""
        return await self._client._request("GET", f"{self._path_prefix}/exposure/distribution")
