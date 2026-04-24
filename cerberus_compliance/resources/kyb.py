"""Typed accessor for the Cerberus Compliance ``/kyb`` resource.

KYB — *Know Your Business* — is the flagship aggregate endpoint of the
Cerberus Compliance API. A single call to ``GET /v1/kyb/{rut}`` returns a
consolidated profile combining every signal the platform holds for the
target Chilean legal entity: canonical identifiers, risk score, directors,
LEI, active sanctions, applicable regulatory frameworks, recent material
events, and cache-freshness metadata.

The response shape is deliberately denormalised so downstream callers
(agents, dashboards, KPIs) can take a single round-trip to render an
entity view; the narrower sub-resources (``entities``, ``sanctions``,
``persons``…) remain available for callers that want one signal at a time.

Example
-------
.. code-block:: python

    from datetime import date
    from cerberus_compliance import CerberusClient

    with CerberusClient() as client:
        profile = client.kyb.get(
            "96.505.760-9",
            as_of=date(2024, 1, 1),
            include=["directors", "lei"],
        )
        print(profile["legal_name"], profile["risk_score"])

``as_of`` forces a point-in-time snapshot (ISO-8601 date). ``include`` is
a caller-ordered subset of optional dimensions — the server guarantees
that requested fields are always present in the response, even when empty.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource

if TYPE_CHECKING:
    from cerberus_compliance.client import AsyncCerberusClient, CerberusClient

__all__ = ["AsyncKYBResource", "KYBResource"]


def _build_params(*, as_of: date | None, include: Sequence[str] | None) -> dict[str, Any] | None:
    """Assemble the KYB query-string dict or ``None`` when empty.

    ``as_of`` is serialised as ``YYYY-MM-DD`` (ISO 8601 date, no time).
    ``include`` preserves caller order and is joined with commas, as the
    API expects a single comma-separated string rather than a repeated
    parameter. An empty ``include`` sequence is treated as absent.
    """
    params: dict[str, Any] = {}
    if as_of is not None:
        params["as_of"] = as_of.isoformat()
    if include:
        params["include"] = ",".join(include)
    return params or None


class KYBResource(BaseResource):
    """Sync accessor for ``GET /kyb/{rut}``.

    Exposes a single :meth:`get` method — the endpoint does not support
    listing or mutation. Use :attr:`cerberus_compliance.CerberusClient.entities`
    when you need to enumerate entities without going through KYB.
    """

    _path_prefix = "/kyb"

    def __init__(self, client: CerberusClient) -> None:
        super().__init__(client)

    def get(
        self,
        rut: str,
        *,
        as_of: date | None = None,
        include: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        """Fetch the aggregate KYB profile for ``rut``.

        Args:
            rut: Chilean tax id. Both dotted (``96.505.760-9``) and
                plain (``96505760-9``) forms are accepted; the SDK
                percent-encodes the value so dots survive round-trip.
            as_of: Point-in-time snapshot. Serialised as an ISO-8601
                date. ``None`` requests the live view.
            include: Optional dimensions to embed in the response
                (e.g. ``["directors", "lei"]``). Order is preserved
                on the wire and is documented as stable for the server.

        Returns:
            The parsed JSON document. Typical fields include
            ``legal_name``, ``rut``, ``risk_score``, ``cache_status``,
            plus any dimensions listed in ``include``.
        """
        path = f"{self._path_prefix}/{quote(rut, safe='')}"
        return self._client._request(
            "GET", path, params=_build_params(as_of=as_of, include=include)
        )


class AsyncKYBResource(AsyncBaseResource):
    """Async mirror of :class:`KYBResource`."""

    _path_prefix = "/kyb"

    def __init__(self, client: AsyncCerberusClient) -> None:
        super().__init__(client)

    async def get(
        self,
        rut: str,
        *,
        as_of: date | None = None,
        include: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        """Async variant of :meth:`KYBResource.get`."""
        path = f"{self._path_prefix}/{quote(rut, safe='')}"
        return await self._client._request(
            "GET", path, params=_build_params(as_of=as_of, include=include)
        )
