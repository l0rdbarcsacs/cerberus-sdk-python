"""Typed accessor for the Cerberus Compliance ``/ipsa`` resource.

IPSA exposes equity price-reaction analytics derived from the Cerberus
market-data pipeline, scoped to the IPSA-25 constituent universe.  Three
endpoints are published, all under the ``equity:read`` scope::

    GET /ipsa/risk-panel
    GET /ipsa/{ticker}/risk
    GET /event-study/{ticker_or_rut}?event=he|art12

``risk-panel`` returns realised-volatility / drawdown rows for every
known IPSA ticker plus an equal-weight index proxy.  ``{ticker}/risk``
returns the single-ticker risk block.  ``event-study`` computes
abnormal returns around CMF disclosure events (hechos esenciales or
Art.12 insider transactions) over the fixed ``['[-1,+1]', '[-1,+5]']``
trading-day windows.

The ``event-study`` path is a top-level sibling of ``/ipsa`` (it is
declared by FastAPI as ``/event-study/{ticker_or_rut}``), so it does not
share the :attr:`IPSAResource._path_prefix`.  It lives here because it
shares the ``equity:read`` scope and the IPSA / price-reaction domain.

All three responses are single object envelopes — there is no cursor
pagination, no ``items``/``next_cursor``.  Decimal-typed fields
(volatility, drawdown, returns, closes) are financial values: they are
serialised as JSON numbers/strings and surfaced verbatim; never coerce
them to ``float``.

Example
-------
.. code-block:: python

    from cerberus_compliance import CerberusClient

    with CerberusClient() as client:
        panel = client.ipsa.risk_panel()
        for row in panel["tickers"]:
            print(row["ticker"], row["realized_volatility_annualised"])

        study = client.ipsa.event_study("FALABELLA", event="he")
        for ev in study["events"]:
            print(ev["event_date"], ev["windows"])
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from cerberus_compliance.resources._base import (
    AsyncBaseResource,
    BaseResource,
    _encode_id,
)

if TYPE_CHECKING:
    from cerberus_compliance.client import AsyncCerberusClient, CerberusClient

__all__ = ["AsyncIPSAResource", "IPSAResource"]

# Documented enum for the event-study ``event`` query param.
EventType = Literal["he", "art12"]


class IPSAResource(BaseResource):
    """Sync accessor for the ``/ipsa`` and ``/event-study`` endpoint family."""

    _path_prefix = "/ipsa"

    def __init__(self, client: CerberusClient) -> None:
        super().__init__(client)

    def risk_panel(self) -> dict[str, Any]:
        """Return the IPSA-25 realised-risk panel.

        Iterates the fixed ``KNOWN_TICKERS`` set (sorted ascending) and
        returns, for each ticker with enough price history, its
        annualised realised volatility and max drawdown, alongside an
        equal-weight ``index_proxy`` block.  Tickers with fewer than two
        close bars in the trailing window are skipped gracefully and
        counted in ``tickers_skipped`` (the endpoint never 500s on thin
        history).

        Returns:
            The single object envelope (``window``,
            ``annualisation_factor``, ``tickers_total``,
            ``tickers_skipped``, ``index_proxy``, ``tickers``).  Decimal
            fields are nullable.
        """
        return self._client._request("GET", f"{self._path_prefix}/risk-panel")

    def ticker_risk(self, ticker: str) -> dict[str, Any]:
        """Return the realised-risk block for a single IPSA ticker.

        Args:
            ticker: An IPSA-25 ticker (e.g. ``"FALABELLA"``).  Case is
                normalised server-side, so any case is accepted.  The
                value is percent-encoded so symbols containing ``.`` or
                ``/`` round-trip cleanly.

        Returns:
            The single object envelope (``window``,
            ``annualisation_factor``, ``risk``).  Decimal fields are
            nullable.

        Raises:
            NotFoundError: ``404`` when ``ticker`` is not in the IPSA-25
                ``KNOWN_TICKERS`` list (i.e. a typo).
            ValidationError: ``422`` when ``ticker`` is known but has
                insufficient price history (not yet backfilled).
        """
        path = f"{self._path_prefix}/{_encode_id(ticker)}/risk"
        return self._client._request("GET", path)

    def event_study(
        self,
        ticker_or_rut: str,
        *,
        event: EventType = "he",
    ) -> dict[str, Any]:
        """Return the abnormal-return event study for an issuer.

        Args:
            ticker_or_rut: An IPSA ticker (e.g. ``"FALABELLA"``) or a RUT
                in any format (``90.413.000-1`` / ``90413000-1`` /
                ``90413000``), resolved to an issuer server-side.  The
                value is percent-encoded.
            event: Disclosure event family to study.  ``"he"`` (default)
                = hechos esenciales; ``"art12"`` = Art.12 insider
                transactions.  Case-insensitive server-side; an
                unrecognised value yields ``422``.

        Returns:
            The single object envelope (``identifier``, ``ticker``,
            ``rut``, ``entity_id``, ``event_type``, ``method``,
            ``windows_requested``, ``events_total``, ``events_studied``,
            ``events_skipped``, ``events``).  Each studied event carries
            one window per fully-covered ``[-1,+1]`` / ``[-1,+5]`` pair.
            Decimal close/return fields; ``entity_id`` is a string UUID.

        Raises:
            NotFoundError: ``404`` when ``ticker_or_rut`` cannot be
                resolved to an issuer.
            ValidationError: ``422`` when ``event`` is not ``"he"`` or
                ``"art12"``.
        """
        path = f"/event-study/{_encode_id(ticker_or_rut)}"
        return self._client._request("GET", path, params={"event": event})


class AsyncIPSAResource(AsyncBaseResource):
    """Async mirror of :class:`IPSAResource`."""

    _path_prefix = "/ipsa"

    def __init__(self, client: AsyncCerberusClient) -> None:
        super().__init__(client)

    async def risk_panel(self) -> dict[str, Any]:
        """Async variant of :meth:`IPSAResource.risk_panel`."""
        return await self._client._request("GET", f"{self._path_prefix}/risk-panel")

    async def ticker_risk(self, ticker: str) -> dict[str, Any]:
        """Async variant of :meth:`IPSAResource.ticker_risk`."""
        path = f"{self._path_prefix}/{_encode_id(ticker)}/risk"
        return await self._client._request("GET", path)

    async def event_study(
        self,
        ticker_or_rut: str,
        *,
        event: EventType = "he",
    ) -> dict[str, Any]:
        """Async variant of :meth:`IPSAResource.event_study`."""
        path = f"/event-study/{_encode_id(ticker_or_rut)}"
        return await self._client._request("GET", path, params={"event": event})
