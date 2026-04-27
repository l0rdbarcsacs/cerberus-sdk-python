"""Fetch IPSA-25 daily OHLCV via the equity endpoint.

The equity surface wraps Yahoo Finance ``.SN`` tickers and resolves the
``entity_id`` against ``cmf_entities`` so the same dossier you pulled
via :py:meth:`KYBResource.get` lines up with its market data.

Run:
    CERBERUS_API_KEY=ck_live_... python examples/equity_prices.py
"""

from __future__ import annotations

import os

from cerberus_compliance import CerberusClient


def main() -> None:
    client = CerberusClient(api_key=os.environ["CERBERUS_API_KEY"])

    # FALABELLA last 5 trading days.  ``from_`` becomes the wire param
    # ``from`` (Python keyword); the SDK handles the rename.
    resp = client.equity.prices(
        "FALABELLA",
        from_="2026-04-20",
        to="2026-04-27",
    )
    print(f"Ticker:    {resp['ticker']}")
    print(f"entity_id: {resp.get('entity_id') or '<unmatched>'}")
    print(f"Source:    {resp['source']}")
    print()
    print(f"{'Date':<12}{'Open':>10}{'High':>10}{'Low':>10}{'Close':>10}{'Volume':>14}")
    for bar in resp["prices"]:
        print(
            f"{bar['date']:<12}"
            f"{bar['open']:>10}"
            f"{bar['high']:>10}"
            f"{bar['low']:>10}"
            f"{bar['close']:>10}"
            f"{int(bar['volume']):>14,}"
        )


if __name__ == "__main__":
    main()
