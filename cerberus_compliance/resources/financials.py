"""Typed accessors for the Cerberus Compliance ``/entities/.../financials`` resource.

The financials surface exposes IFRS-derived financial intelligence for a
Chilean legal entity (keyed on RUT) plus two public aggregate views. All
per-entity endpoints are constructed from the latest published IFRS
filings the Cerberus platform has ingested from CMF disclosures:

* :meth:`FinancialsResource.get_summary` — latest-period key account line
  items.
* :meth:`FinancialsResource.get_ratios` — the five headline liquidity /
  leverage / margin ratios, latest plus full history.
* :meth:`FinancialsResource.get_distress` — Altman Z'' emerging-market
  distress score (per-named; banks and insurers are excluded).
* :meth:`FinancialsResource.get_benchmark` — the entity's ratios placed
  against its CIIU-2 sector peer set.
* :meth:`FinancialsResource.get_timeseries` — multi-period key-account and
  ratio series.

Two endpoints are public aggregates that never expose entity names or
RUTs (the Ley 21.719 boundary):

* :meth:`FinancialsResource.get_distress_histogram` — zone-bucket counts.
* :meth:`FinancialsResource.get_sector_stats` — per-sector ratio
  distributions.

Every per-entity endpoint returns ``200`` even for a bad or unknown RUT —
the body carries a ``has_*`` flag (``has_ifrs`` / ``has_distress`` /
``has_benchmark``) so callers can distinguish "no data" from "bad RUT"
without catching a :class:`~cerberus_compliance.errors.NotFoundError`. All
monetary and ratio fields arrive as JSON strings encoding
:class:`decimal.Decimal` values and should be parsed as ``Decimal``,
never ``float``.

Example
-------
.. code-block:: python

    from cerberus_compliance import CerberusClient

    with CerberusClient() as client:
        summary = client.financials.get_summary("96505760-9")
        ratios = client.financials.get_ratios("96505760-9")
        histogram = client.financials.get_distress_histogram()
"""

from __future__ import annotations

from typing import Any

from cerberus_compliance.resources._base import (
    AsyncBaseResource,
    BaseResource,
    _encode_id,
)

__all__ = ["AsyncFinancialsResource", "FinancialsResource"]


def _aggregate_params(periodo: str | None) -> dict[str, Any] | None:
    """Build the query for the public aggregate endpoints.

    ``periodo`` (an ``YYYYMM`` IFRS period) is dropped when ``None`` so
    the server falls back to its default (per-issuer latest scoring for
    the histogram, most-recent built snapshot for sector stats).
    """
    if periodo is None:
        return None
    return {"periodo": periodo}


class FinancialsResource(BaseResource):
    """Synchronous accessor for the financials endpoint family.

    Per-entity methods are keyed on RUT (accepted dotted ``61.703.000-1``,
    canonical ``61703000-1``, or bare body ``61703000``); the two
    aggregate methods (:meth:`get_distress_histogram`,
    :meth:`get_sector_stats`) take no path params and never expose
    entity-level identifiers.
    """

    _path_prefix = "/entities"

    def get_summary(self, rut: str) -> dict[str, Any]:
        """Return the latest-period IFRS key-account summary for an entity.

        Issues ``GET /entities/{rut}/financials``. The ``rut`` is
        percent-encoded. Returns ``200`` with ``has_ifrs=false``,
        ``periodo=null`` and ``key_accounts=[]`` for an entity without
        published IFRS filings (or a bad RUT) — never a ``404``.

        Returns:
            ``{"rut": str, "periodo": str | None, "has_ifrs": bool,
            "key_accounts": [{"cuenta_codigo": str, "valor": Decimal,
            "cuenta_descripcion": str, "tipo_estado": str,
            "tipo_norma": str}, ...]}``. ``valor`` is a JSON string
            encoding a :class:`~decimal.Decimal`.
        """
        path = f"{self._path_prefix}/{_encode_id(rut)}/financials"
        return self._client._request("GET", path)

    def get_ratios(self, rut: str) -> dict[str, Any]:
        """Return the five headline financial ratios for an entity.

        Issues ``GET /entities/{rut}/financials/ratios``. Returns the
        latest period plus the full history (ascending by ``periodo``).
        Each of the five ratios is null-safe: a missing input line item
        yields ``null`` for that ratio rather than a ``500``. Returns
        ``200`` with ``has_ifrs=false``, ``latest=null`` and
        ``periods=[]`` when the entity has no IFRS filings.

        Returns:
            ``{"rut": str, "has_ifrs": bool, "latest": RatioPeriod | None,
            "periods": [RatioPeriod]}`` where ``RatioPeriod`` carries
            ``periodo``, ``tipo_norma`` and the five ``Decimal | None``
            ratios (``current_ratio``, ``debt_to_equity``, ``debt_ratio``,
            ``operating_margin``, ``net_margin``).
        """
        path = f"{self._path_prefix}/{_encode_id(rut)}/financials/ratios"
        return self._client._request("GET", path)

    def get_distress(self, rut: str) -> dict[str, Any]:
        """Return the Altman Z'' distress score for an entity.

        Issues ``GET /entities/{rut}/financials/distress``. Banks and
        insurers are excluded from scoring (``excluded=true``,
        ``zone="excluded"``, ``excluded_reason`` set). Returns ``200``
        with ``has_distress=false`` (never ``404``) when there are no
        IFRS filings or the balance sheet is incomplete. For the public
        aggregate use :meth:`get_distress_histogram`.

        Returns:
            ``{"rut": str, "has_distress": bool, "excluded": bool,
            "excluded_reason": str | None, "periodo": str | None,
            "tipo_norma": str | None, "z_score": Decimal | None,
            "zone": "safe" | "grey" | "distress" | "excluded" | None,
            "x1_working_capital_to_ta": Decimal | None,
            "x2_retained_earnings_to_ta": Decimal | None,
            "x3_ebit_to_ta": Decimal | None,
            "x4_equity_to_liabilities": Decimal | None}``.
        """
        path = f"{self._path_prefix}/{_encode_id(rut)}/financials/distress"
        return self._client._request("GET", path)

    def get_benchmark(self, rut: str) -> dict[str, Any]:
        """Return the entity's ratios benchmarked against its sector.

        Issues ``GET /entities/{rut}/financials/benchmark``. Places the
        entity's latest-period ratios against its CIIU-2 sector peer set;
        ``percentile`` is ``0``-``100`` within that set. ``value`` /
        ``percentile`` / ``sector`` are ``null`` when the entity has no
        value for a ratio or the sector bucket was suppressed (every
        published sector distribution has ``n_entities>=5``). Returns
        ``200`` with ``has_benchmark=false`` and ``ratios=[]`` (never
        ``404``) when there is no IFRS data, no resolvable sector, or no
        published sector stats. Public counterpart:
        :meth:`get_sector_stats`.

        Returns:
            ``{"rut": str, "has_benchmark": bool, "periodo": str | None,
            "sector_division": str | None, "sector_label": str | None,
            "ratios": [EntityRatioVsSector]}``.
        """
        path = f"{self._path_prefix}/{_encode_id(rut)}/financials/benchmark"
        return self._client._request("GET", path)

    def get_timeseries(self, rut: str) -> dict[str, Any]:
        """Return the multi-period key-account and ratio series for an entity.

        Issues ``GET /entities/{rut}/financials/timeseries``. Points are
        ordered ascending by ``periodo``; each point carries total
        assets/liabilities/equity, current assets/liabilities, revenue,
        plus ``current_ratio`` and ``debt_to_equity`` (only these two
        ratios, not the full five). Returns ``200`` with
        ``has_ifrs=false`` and ``points=[]`` (never ``404``) when the
        entity has no IFRS filings.

        Returns:
            ``{"rut": str, "has_ifrs": bool, "points": [TimeseriesPoint]}``
            where each ``TimeseriesPoint`` carries ``periodo``,
            ``tipo_norma`` and ``Decimal | None`` account/ratio fields.
        """
        path = f"{self._path_prefix}/{_encode_id(rut)}/financials/timeseries"
        return self._client._request("GET", path)

    def get_distress_histogram(self, *, periodo: str | None = None) -> dict[str, Any]:
        """Return the public distress-zone histogram (no entity names/RUTs).

        Issues ``GET /entities/financials/distress/histogram``. This is the
        only public distress surface (Ley 21.719 boundary). The ``zone``
        enum here is only ``safe`` / ``grey`` / ``distress`` (no
        ``excluded`` bucket); banks and insurers are excluded from scoring
        before counting. Any zone bucket below ``suppression_threshold``
        (5) entities is omitted, so callers must not assume all three
        zones are present.

        Args:
            periodo: Optional ``YYYYMM`` IFRS period. Omit for per-issuer
                latest scoring (each issuer scored at its own latest
                ``periodo``, higher coverage); when pinned, honours
                exactly that one global period. Dropped from the wire URL
                when ``None``.

        Returns:
            ``{"periodo": str | None, "total_scored": int,
            "suppression_threshold": int, "buckets": [{"zone": "safe" |
            "grey" | "distress", "count": int}, ...]}``.
        """
        return self._client._request(
            "GET",
            f"{self._path_prefix}/financials/distress/histogram",
            params=_aggregate_params(periodo),
        )

    def get_sector_stats(self, *, periodo: str | None = None) -> dict[str, Any]:
        """Return the public per-sector ratio distributions (no entity names/RUTs).

        Issues ``GET /entities/financials/sector-stats``. Served from the
        pre-materialized ``sector_ratio_stats`` table; every returned
        distribution has ``n_entities>=5`` (build-time suppression, with
        ``suppression_threshold`` echoed for transparency). Returns
        ``200`` with ``sectors=[]`` (never ``404``) when the snapshot has
        never been built.

        Args:
            periodo: Optional ``YYYYMM`` IFRS period. Omit for the
                most-recent built period. Dropped from the wire URL when
                ``None``.

        Returns:
            ``{"periodo": str | None, "suppression_threshold": int,
            "sectors": [{"sector_division": str, "sector_label": str,
            "ratios": [{"ratio_name": str, "n_entities": int, "median":
            Decimal, "p25": Decimal, "p75": Decimal, "mean": Decimal},
            ...]}, ...]}``.
        """
        return self._client._request(
            "GET",
            f"{self._path_prefix}/financials/sector-stats",
            params=_aggregate_params(periodo),
        )


class AsyncFinancialsResource(AsyncBaseResource):
    """Asynchronous mirror of :class:`FinancialsResource`."""

    _path_prefix = "/entities"

    async def get_summary(self, rut: str) -> dict[str, Any]:
        """Async variant of :meth:`FinancialsResource.get_summary`."""
        path = f"{self._path_prefix}/{_encode_id(rut)}/financials"
        return await self._client._request("GET", path)

    async def get_ratios(self, rut: str) -> dict[str, Any]:
        """Async variant of :meth:`FinancialsResource.get_ratios`."""
        path = f"{self._path_prefix}/{_encode_id(rut)}/financials/ratios"
        return await self._client._request("GET", path)

    async def get_distress(self, rut: str) -> dict[str, Any]:
        """Async variant of :meth:`FinancialsResource.get_distress`."""
        path = f"{self._path_prefix}/{_encode_id(rut)}/financials/distress"
        return await self._client._request("GET", path)

    async def get_benchmark(self, rut: str) -> dict[str, Any]:
        """Async variant of :meth:`FinancialsResource.get_benchmark`."""
        path = f"{self._path_prefix}/{_encode_id(rut)}/financials/benchmark"
        return await self._client._request("GET", path)

    async def get_timeseries(self, rut: str) -> dict[str, Any]:
        """Async variant of :meth:`FinancialsResource.get_timeseries`."""
        path = f"{self._path_prefix}/{_encode_id(rut)}/financials/timeseries"
        return await self._client._request("GET", path)

    async def get_distress_histogram(self, *, periodo: str | None = None) -> dict[str, Any]:
        """Async variant of :meth:`FinancialsResource.get_distress_histogram`."""
        return await self._client._request(
            "GET",
            f"{self._path_prefix}/financials/distress/histogram",
            params=_aggregate_params(periodo),
        )

    async def get_sector_stats(self, *, periodo: str | None = None) -> dict[str, Any]:
        """Async variant of :meth:`FinancialsResource.get_sector_stats`."""
        return await self._client._request(
            "GET",
            f"{self._path_prefix}/financials/sector-stats",
            params=_aggregate_params(periodo),
        )
