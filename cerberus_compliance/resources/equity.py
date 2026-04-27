"""Typed accessor for the Cerberus Compliance ``/equity`` resource.

Equity exposes time-series price data for Chilean and international
tickers ingested by the Cerberus market-data pipeline.  A single endpoint
is currently published::

    GET /equity/{ticker}/prices?from=YYYY-MM-DD&to=YYYY-MM-DD

The response is a flat OHLCV envelope::

    {
      "ticker": "FALABELLA",
      "entity_id": "ent_…",
      "from": "2024-01-01",
      "to": "2024-03-31",
      "source": "lva",
      "prices": [{"date": "2024-01-02", "open": ..., "close": ..., "volume": ...}, ...],
      "total": 62
    }

Example
-------
.. code-block:: python

    from cerberus_compliance import CerberusClient

    with CerberusClient() as client:
        series = client.equity.prices("FALABELLA", from_="2024-01-01", to="2024-03-31")
        for bar in series["prices"]:
            print(bar["date"], bar["close"])
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cerberus_compliance.resources._base import (
    AsyncBaseResource,
    BaseResource,
    _encode_id,
)

if TYPE_CHECKING:
    from cerberus_compliance.client import AsyncCerberusClient, CerberusClient

__all__ = ["AsyncEquityResource", "EquityResource"]


def _build_price_params(*, from_: str | None, to: str | None) -> dict[str, Any] | None:
    """Build the query-string dict for ``/equity/{ticker}/prices``.

    Python forbids ``from`` as a keyword argument name, so the caller-side
    parameter is ``from_`` and we rename it to the wire ``"from"`` here.
    Both ends accept ``None`` to mean "no constraint" — those entries
    are dropped before they reach the URL.
    """
    params: dict[str, Any] = {}
    if from_ is not None:
        params["from"] = from_
    if to is not None:
        params["to"] = to
    return params or None


class EquityResource(BaseResource):
    """Sync accessor for the ``/equity`` endpoint family."""

    _path_prefix = "/equity"

    def __init__(self, client: CerberusClient) -> None:
        super().__init__(client)

    def prices(
        self,
        ticker: str,
        *,
        from_: str | None = None,
        to: str | None = None,
    ) -> dict[str, Any]:
        """Return the OHLCV time series for ``ticker``.

        Args:
            ticker: Exchange-listed ticker (e.g. ``"FALABELLA"``,
                ``"LTM"``).  The value is percent-encoded so symbols
                containing ``.`` or ``/`` round-trip cleanly.
            from_: Inclusive lower bound on the price date as
                ``YYYY-MM-DD``.  ``None`` means "earliest available".
                Renamed from the wire field ``"from"`` because that
                clashes with the Python keyword.
            to: Inclusive upper bound on the price date as
                ``YYYY-MM-DD``.  ``None`` means "latest available".

        Returns:
            The full envelope (``ticker``, ``entity_id``, ``from``,
            ``to``, ``source``, ``prices``, ``total``).
        """
        path = f"{self._path_prefix}/{_encode_id(ticker)}/prices"
        return self._client._request("GET", path, params=_build_price_params(from_=from_, to=to))


class AsyncEquityResource(AsyncBaseResource):
    """Async mirror of :class:`EquityResource`."""

    _path_prefix = "/equity"

    def __init__(self, client: AsyncCerberusClient) -> None:
        super().__init__(client)

    async def prices(
        self,
        ticker: str,
        *,
        from_: str | None = None,
        to: str | None = None,
    ) -> dict[str, Any]:
        """Async variant of :meth:`EquityResource.prices`."""
        path = f"{self._path_prefix}/{_encode_id(ticker)}/prices"
        return await self._client._request(
            "GET", path, params=_build_price_params(from_=from_, to=to)
        )
