"""Typed accessors for the Cerberus Compliance ``/ratings`` surface.

Credit ratings are sourced from the CMF's public rating-history feed and
exposed across two complementary surfaces:

* **Per-entity, scoped** — :meth:`RatingsResource.get_entity_ratings`
  (``GET /entities/{rut}/ratings``) returns only an anonymous boolean
  guardrail (``has_rating`` + a static ``methodology_url``); under Ley
  21.719 it NEVER carries the rating value/agency for a named entity.
  :meth:`RatingsResource.get_entity_ratings_timeline`
  (``GET /entities/{rut}/ratings-timeline``) is the *valued* per-entity
  view — agency, rating, action and band — allowed only for scoped
  (authenticated) customers under the ``entities:read`` scope.
* **Anonymised aggregates** — :meth:`RatingsResource.get_ratings_distribution`
  (``GET /ratings/distribution``) and
  :meth:`RatingsResource.get_ratings_migration`
  (``GET /ratings/migration``) return population-wide statistics with no
  entity names, RUTs, or per-entity values.

The timeline endpoint returns ``200`` with ``has_ratings=false`` and an
empty ``entries`` list when an entity has no ratings on file (NOT a
``404``); callers must distinguish "no data" from "bad RUT" via the
``has_ratings`` flag rather than the HTTP status.

Example
-------
.. code-block:: python

    from cerberus_compliance import CerberusClient

    with CerberusClient() as client:
        meta = client.ratings.get_entity_ratings("96505760-9")
        timeline = client.ratings.get_entity_ratings_timeline("96505760-9")
        dist = client.ratings.get_ratings_distribution(tipo="instrument")
        churn = client.ratings.get_ratings_migration(period_days=365)
"""

from __future__ import annotations

from typing import Any, Literal

from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource, _encode_id

__all__ = ["AsyncRatingsResource", "RatingsDistributionType", "RatingsResource"]

RatingsDistributionType = Literal["instrument", "insurer"]
"""Optional ``tipo`` filter for :meth:`RatingsResource.get_ratings_distribution`.

``"instrument"`` narrows to instrument-type ratings; ``"insurer"``
narrows to insurer ratings. Omit (pass ``None``) for the combined
distribution. The server does NOT 422-validate this value — an
unrecognised ``tipo`` simply yields an empty list — so the enum here is
advisory rather than strictly enforced on the wire.
"""


class RatingsResource(BaseResource):
    """Sync accessor for the ``/ratings`` endpoint family.

    Combines the per-entity surfaces mounted under ``/entities/{rut}``
    (the boolean guardrail and the scoped timeline) with the anonymised
    aggregate surfaces under ``/ratings`` (distribution and migration).
    """

    _path_prefix = "/ratings"

    def get_entity_ratings(self, rut: str) -> dict[str, Any]:
        """Return the anonymous rating guardrail for an entity.

        Issues ``GET /entities/{rut}/ratings``. The ``rut`` is
        percent-encoded so any RUT format survives the round-trip.

        Returns:
            ``{"rut": str, "has_rating": bool, "methodology_url": str}``.
            Under Ley 21.719 this NEVER carries the rating value or
            agency for a named entity — only whether ANY rating exists.
            For the valued view use :meth:`get_entity_ratings_timeline`.
        """
        path = f"/entities/{_encode_id(rut)}/ratings"
        return self._client._request("GET", path)

    def get_entity_ratings_timeline(self, rut: str) -> dict[str, Any]:
        """Return the full rating history (valued) for an entity.

        Issues ``GET /entities/{rut}/ratings-timeline``. This is a
        scoped/authenticated surface that DOES carry the rating value,
        agency, and action. Returns ``200`` with ``has_ratings=false``
        and empty ``entries`` (NOT ``404``) when the entity has no
        ratings on file.

        Returns:
            ``{"rut": str, "has_ratings": bool, "entries": [{"agency":
            str, "rating": str, "fecha": str|None, "action": str,
            "band": str, "outlook": str|None, "instrument":
            str|None}, ...]}``. No pagination — the full history is
            returned in one response.
        """
        path = f"/entities/{_encode_id(rut)}/ratings-timeline"
        return self._client._request("GET", path)

    def get_ratings_distribution(
        self,
        *,
        tipo: RatingsDistributionType | None = None,
    ) -> list[dict[str, Any]]:
        """Return the anonymised rating-bucket distribution.

        Issues ``GET /ratings/distribution``. The response is a bare JSON
        array (no envelope, no cursor, no pagination); it is normalised
        via :meth:`~cerberus_compliance.resources._base.BaseResource._extract_items`.

        Args:
            tipo: Optional filter — ``"instrument"`` or ``"insurer"``.
                Dropped from the wire URL when ``None``. An unrecognised
                value returns an empty list (the server does not 422).

        Returns:
            ``[{"bucket": str, "count": int, "pct": float}, ...]``
            ordered by descending ``count`` then ``bucket`` ascending.
            Anonymised — no entity names/RUTs/per-entity values.
        """
        params: dict[str, Any] = {}
        if tipo is not None:
            params["tipo"] = tipo
        body = self._client._request(
            "GET", f"{self._path_prefix}/distribution", params=params or None
        )
        return self._extract_items(body)

    def get_ratings_migration(self, *, period_days: int = 365) -> dict[str, Any]:
        """Return anonymised rating-migration (churn) counts.

        Issues ``GET /ratings/migration``. Counts upgrades, downgrades,
        and affirmations across the whole population within a look-back
        window ending today (UTC).

        Args:
            period_days: Look-back window in days; the server enforces
                ``1 <= period_days <= 1825`` (a 422 is returned out of
                range — this cap is NOT validated client-side). Defaults
                to ``365``.

        Returns:
            ``{"period_days": int, "from_date": str, "to_date": str,
            "upgrades": int, "downgrades": int, "affirmations": int,
            "total_actions": int}`` where ``from_date``/``to_date`` are
            ``YYYY-MM-DD`` dates. Anonymised — population-wide counts
            only, no entity names/RUTs/values.
        """
        params: dict[str, Any] = {"period_days": period_days}
        return self._client._request("GET", f"{self._path_prefix}/migration", params=params)


class AsyncRatingsResource(AsyncBaseResource):
    """Async mirror of :class:`RatingsResource`."""

    _path_prefix = "/ratings"

    async def get_entity_ratings(self, rut: str) -> dict[str, Any]:
        """Async variant of :meth:`RatingsResource.get_entity_ratings`."""
        path = f"/entities/{_encode_id(rut)}/ratings"
        return await self._client._request("GET", path)

    async def get_entity_ratings_timeline(self, rut: str) -> dict[str, Any]:
        """Async variant of :meth:`RatingsResource.get_entity_ratings_timeline`."""
        path = f"/entities/{_encode_id(rut)}/ratings-timeline"
        return await self._client._request("GET", path)

    async def get_ratings_distribution(
        self,
        *,
        tipo: RatingsDistributionType | None = None,
    ) -> list[dict[str, Any]]:
        """Async variant of :meth:`RatingsResource.get_ratings_distribution`."""
        params: dict[str, Any] = {}
        if tipo is not None:
            params["tipo"] = tipo
        body = await self._client._request(
            "GET", f"{self._path_prefix}/distribution", params=params or None
        )
        return self._extract_items(body)

    async def get_ratings_migration(self, *, period_days: int = 365) -> dict[str, Any]:
        """Async variant of :meth:`RatingsResource.get_ratings_migration`."""
        params: dict[str, Any] = {"period_days": period_days}
        return await self._client._request("GET", f"{self._path_prefix}/migration", params=params)
