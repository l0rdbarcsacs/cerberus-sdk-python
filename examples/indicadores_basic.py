"""Fetch BCCh indicadores by ``series_id`` and discover series via ``buscar``.

Runnable: ``CERBERUS_API_KEY=<your-key> python examples/indicadores_basic.py``
Tier required: ``starter`` (single-date ``get``) or ``professional``
(historical ``history`` / ``forecast``).
Expected runtime: ~2 s.

The Cerberus Compliance API serves the Banco Central de Chile (BCCh)
statistical database (~25 000 series), cached server-side. The canonical
handle for a series is its BCCh ``series_id`` — a dotted code such as
``F073.UFF.PRE.Z.D`` (Unidad de fomento) — and every response carries
``title_es``, the human-readable label. Values are returned as **strings**
with the exact upstream-published precision — use ``Decimal(value)`` if
you need numeric math.

This example walks through:

1. ``client.indicadores.get("F073.UFF.PRE.Z.D")`` — latest UF value.
2. ``client.indicadores.get("F073.UFF.PRE.Z.D", date="YYYY-MM-DD")`` —
   point-in-time.
3. ``client.indicadores.get("F073.TCO.PRE.Z.D", date=...)`` — observed
   USD/CLP rate.
4. ``client.indicadores.history("F073.UFF.PRE.Z.D", from_=..., to=...)``
   — historical range as ``[{"date": ..., "value": ...}]`` rows.
5. ``client.indicadores.buscar(q="cobre")`` — discover a ``series_id``
   by keyword, then feed it to ``get`` and ``forecast``.
"""

from __future__ import annotations

import logging
import sys
from decimal import Decimal
from typing import Any

from cerberus_compliance import CerberusAPIError, CerberusClient, NotFoundError

logger = logging.getLogger("cerberus_compliance.examples.indicadores_basic")

UF_SERIES_ID = "F073.UFF.PRE.Z.D"  # Unidad de fomento (UF)
USD_SERIES_ID = "F073.TCO.PRE.Z.D"  # Tipo de cambio nominal (dólar observado)
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
    """Print latest + point-in-time + USD + history + buscar/forecast demo."""
    _print_header(f"1. indicadores.get('{UF_SERIES_ID}') — latest UF")
    try:
        uf = client.indicadores.get(UF_SERIES_ID)
    except NotFoundError:
        print("  (no UF value in current corpus)")
        return
    print(f"  title_es     : {_fmt(uf.get('title_es'))}")
    print(f"  date         : {_fmt(uf.get('date'))}")
    print(f"  value (str)  : {_fmt(uf.get('value'))}")
    raw_value = uf.get("value")
    if isinstance(raw_value, str):
        decimal_value = Decimal(raw_value)
        print(f"  value (Decimal): {decimal_value}")

    _print_header(f"2. indicadores.get('{UF_SERIES_ID}', date='{SNAPSHOT_DATE}')")
    try:
        snap = client.indicadores.get(UF_SERIES_ID, date=SNAPSHOT_DATE)
    except NotFoundError:
        print(f"  (no UF value for {SNAPSHOT_DATE})")
    else:
        print(f"  date  : {_fmt(snap.get('date'))}")
        print(f"  value : {_fmt(snap.get('value'))}")

    _print_header(f"3. indicadores.get('{USD_SERIES_ID}', date='{SNAPSHOT_DATE}') — USD/CLP")
    try:
        usd = client.indicadores.get(USD_SERIES_ID, date=SNAPSHOT_DATE)
    except NotFoundError:
        print(f"  (no USD value for {SNAPSHOT_DATE} — weekend/holiday?)")
    else:
        for key in ("title_es", "date", "value"):
            print(f"  {key:10s}: {_fmt(usd.get(key))}")

    _print_header(f"4. indicadores.history('{UF_SERIES_ID}', 2026-01-01 .. 2026-04-30)")
    try:
        series = client.indicadores.history(UF_SERIES_ID, from_="2026-01-01", to="2026-04-30")
    except CerberusAPIError as exc:
        print(f"  error: {exc}")
        return
    print(f"  rows returned: {len(series)}")
    if series:
        first = series[0]
        last = series[-1]
        print(f"  first : {_fmt(first.get('date'))}  {_fmt(first.get('value'))}")
        print(f"  last  : {_fmt(last.get('date'))}  {_fmt(last.get('value'))}")

    _print_header("5. indicadores.buscar(q='cobre') — discovery over ~25k BCCh series")
    matches = client.indicadores.buscar(q="cobre", limit=5)
    print(f"  matches returned: {len(matches)}")
    if not matches:
        print("  (no series matched 'cobre')")
        return
    for row in matches[:3]:
        title = _fmt(row.get("title_es"))
        if len(title) > 56:
            title = f"{title[:53]}..."
        print(f"  - {_fmt(row.get('series_id')):38s} {title}")
    discovered_id = matches[0].get("series_id")
    if not isinstance(discovered_id, str) or not discovered_id:
        print("  (first match carries no series_id — skipping get/forecast demo)")
        return

    _print_header(f"6. indicadores.get('{discovered_id}') — latest discovered value")
    try:
        latest = client.indicadores.get(discovered_id)
    except NotFoundError:
        print("  (series has no observations in current corpus)")
    else:
        print(f"  title_es : {_fmt(latest.get('title_es'))}")
        print(f"  date     : {_fmt(latest.get('date'))}")
        print(f"  value    : {_fmt(latest.get('value'))}")

    _print_header(f"7. indicadores.forecast('{discovered_id}') — TimesFM projection")
    try:
        forecast = client.indicadores.forecast(discovered_id)
    except NotFoundError:
        print("  (no historical data to forecast from)")
    except CerberusAPIError as exc:
        print(f"  (forecast unavailable: {exc})")
    else:
        print(f"  model        : {_fmt(forecast.get('model'))}")
        print(f"  horizon      : {_fmt(forecast.get('horizon'))}")
        print(f"  interval_pct : {_fmt(forecast.get('interval_pct'))}")
        points = forecast.get("points")
        if isinstance(points, list) and points:
            head = points[0]
            if isinstance(head, dict):
                point_value = head.get("point")
                print(
                    f"  step 1       : point={_fmt(point_value)}"
                    f" lower={_fmt(head.get('lower'))} upper={_fmt(head.get('upper'))}"
                )
                if isinstance(point_value, str):
                    print(f"  step 1 (Decimal): {Decimal(point_value)}")


if __name__ == "__main__":
    sys.exit(main())


__all__ = ["main"]  # re-exported for notebook callers; keep linted.
