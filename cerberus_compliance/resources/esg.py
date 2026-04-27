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
from typing import Any, Literal

from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource, _encode_id

__all__ = ["AsyncESGResource", "ESGRankingDirection", "ESGResource"]

ESGRankingDirection = Literal["asc", "desc"]
"""Sort direction for :meth:`ESGResource.rankings`.

``"desc"`` (the default) returns the highest values first — the typical
"top performers" view; ``"asc"`` returns the lowest values first, which
is what callers usually want for reverse indicators like emissions
intensity.
"""


def _build_rankings_params(
    *,
    indicator: str,
    year: int,
    top_n: int,
    direction: ESGRankingDirection,
    industry: str | None,
) -> dict[str, Any]:
    """Assemble the ``/esg/rankings`` query string.

    ``indicator``, ``year``, ``top_n`` and ``direction`` are always
    forwarded; ``industry`` is dropped when ``None`` so the wire URL
    stays minimal.
    """
    params: dict[str, Any] = {
        "indicator": indicator,
        "year": year,
        "top_n": top_n,
        "direction": direction,
    }
    if industry is not None:
        params["industry"] = industry
    return params


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

    def rankings(
        self,
        *,
        indicator: str,
        year: int,
        top_n: int = 20,
        direction: ESGRankingDirection = "desc",
        industry: str | None = None,
    ) -> dict[str, Any]:
        """Return the top-N emisores ranked by an ESG indicator.

        Issues ``GET /esg/rankings``.

        Args:
            indicator: Indicator code (e.g. ``"scope1_emissions"``,
                ``"board_independence_pct"``). Forwarded verbatim.
            year: Fiscal year to rank against (e.g. ``2023``).
            top_n: Page size; defaults to 20.
            direction: ``"desc"`` (default) for highest-first,
                ``"asc"`` for lowest-first.
            industry: Optional industry-code filter (e.g.
                ``"banking"``). Dropped from the wire URL when
                ``None``.

        Returns:
            ``{"indicator_code": str, "indicator_name": str,
            "fiscal_year": int, "unit": str, "direction": str,
            "rankings": [{"rank": int, "emisor_rut": str,
            "emisor_nombre": str, "value": <num|str>,
            "industry": str}, ...]}``.
        """
        params = _build_rankings_params(
            indicator=indicator,
            year=year,
            top_n=top_n,
            direction=direction,
            industry=industry,
        )
        return self._client._request("GET", f"{self._path_prefix}/rankings", params=params)


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

    async def rankings(
        self,
        *,
        indicator: str,
        year: int,
        top_n: int = 20,
        direction: ESGRankingDirection = "desc",
        industry: str | None = None,
    ) -> dict[str, Any]:
        """Async variant of :meth:`ESGResource.rankings`."""
        params = _build_rankings_params(
            indicator=indicator,
            year=year,
            top_n=top_n,
            direction=direction,
            industry=industry,
        )
        return await self._client._request("GET", f"{self._path_prefix}/rankings", params=params)
