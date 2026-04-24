"""Fetch CMF indicadores (UF / UTM / USD / EUR / IPC / TMC).

Runnable: ``CERBERUS_API_KEY=<your-key> python examples/indicadores_basic.py``
Tier required: ``starter`` (single-date ``get``) or ``professional``
(historical ``history``).
Expected runtime: ~400 ms.

The Cerberus Compliance API proxies the CMF Indicadores API v3
(``api.cmfchile.cl/api-sbifv3/recursos_api/``) and caches responses
server-side. Values are returned as **strings** with CMF-published
precision — use ``Decimal(value)`` if you need numeric math.

This example walks through:

1. ``client.indicadores.get("UF")`` — latest UF value.
2. ``client.indicadores.get("UF", date="YYYY-MM-DD")`` — point-in-time.
3. ``client.indicadores.get("USD", date=...)`` — observed USD/CLP rate.
4. ``client.indicadores.history("UF", from_=..., to=...)`` — historical
   range as ``[{"date": ..., "value": ...}]`` rows.
"""

from __future__ import annotations

import logging
import os
import sys
from decimal import Decimal
from typing import Any

from cerberus_compliance import CerberusAPIError, CerberusClient, NotFoundError

logger = logging.getLogger("cerberus_compliance.examples.indicadores_basic")

SNAPSHOT_DATE = "2026-04-24"


def _fmt(value: Any) -> str:
    """Render ``None`` as ``'-'`` and coerce everything else to ``str``."""
    return "-" if value is None else str(value)


def _print_header(title: str) -> None:
    """Print a wide headline above each section."""
    bar = "=" * 72
    print(f"\n{bar}\n{title}\n{bar}")


def main() -> int:
    """Run the indicadores walk-through against prod; returns an exit code."""
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    try:
        client = CerberusClient()
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    with client:
        try:
            _run(client)
        except CerberusAPIError as exc:
            print(f"error: api failure: {exc}", file=sys.stderr)
            return 1

    return 0


def _run(client: CerberusClient) -> None:
    """Print latest + point-in-time + USD + historical series."""
    _print_header("1. indicadores.get('UF') — latest UF")
    try:
        uf = client.indicadores.get("UF")
    except NotFoundError:
        print("  (no UF value in current corpus)")
        return
    print(f"  date         : {_fmt(uf.get('date'))}")
    print(f"  value (str)  : {_fmt(uf.get('value'))}")
    raw_value = uf.get("value")
    if isinstance(raw_value, str):
        decimal_value = Decimal(raw_value)
        print(f"  value (Decimal): {decimal_value}")

    _print_header(f"2. indicadores.get('UF', date='{SNAPSHOT_DATE}')")
    try:
        snap = client.indicadores.get("UF", date=SNAPSHOT_DATE)
    except NotFoundError:
        print(f"  (no UF value for {SNAPSHOT_DATE})")
    else:
        print(f"  date  : {_fmt(snap.get('date'))}")
        print(f"  value : {_fmt(snap.get('value'))}")

    _print_header(f"3. indicadores.get('USD', date='{SNAPSHOT_DATE}')")
    try:
        usd = client.indicadores.get("USD", date=SNAPSHOT_DATE)
    except NotFoundError:
        print(f"  (no USD value for {SNAPSHOT_DATE} — weekend/holiday?)")
    else:
        for key in ("date", "value", "currency", "unit"):
            print(f"  {key:10s}: {_fmt(usd.get(key))}")

    _print_header("4. indicadores.history('UF', 2026-01-01 .. 2026-04-30)")
    try:
        series = client.indicadores.history("UF", from_="2026-01-01", to="2026-04-30")
    except CerberusAPIError as exc:
        print(f"  error: {exc}")
        return
    print(f"  rows returned: {len(series)}")
    if series:
        first = series[0]
        last = series[-1]
        print(f"  first : {_fmt(first.get('date'))}  {_fmt(first.get('value'))}")
        print(f"  last  : {_fmt(last.get('date'))}  {_fmt(last.get('value'))}")


if __name__ == "__main__":
    sys.exit(main())


__all__ = ["main"]  # re-exported for notebook callers; keep linted.

# The env-lookup below is intentionally a no-op that documents the expected
# env var — kept out of the function body so the example reads top-down.
_ = os.environ.get("CERBERUS_API_KEY")
