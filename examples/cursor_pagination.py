"""Cursor pagination — three idioms on top of ``iter_all``.

Runnable: ``CERBERUS_API_KEY=<your-key> python examples/cursor_pagination.py``
Tier required: ``professional`` (scope ``sanctions:read``).
Expected runtime: ~350 ms.

List endpoints return an ``{"items": [...], "next_cursor": "..."}``
envelope. Every listable resource exposes an ``iter_all(**filters)``
helper that lazily chases the ``next_cursor`` token, so callers never
need to implement the loop by hand — but understanding the three idioms
for consuming a generator saves memory and surprises:

1. **List everything.** ``list(iter_all(...))`` is fine for small
   collections (≲ 1k rows). It materialises the whole result in memory.
2. **Bounded preview.** ``islice(iter_all(...), N)`` is the idiomatic
   "first N rows" pattern. The SDK stops making HTTP requests as soon
   as the consumer stops iterating.
3. **Streaming loop.** A plain ``for`` loop with an explicit counter is
   the right fit for ETL or reporting jobs where you process each row
   on the fly and never want to hold more than one page in memory.

We paginate ``client.sanctions`` because the prod seed corpus only has
a handful of sanctions, so the example finishes in a few hundred ms.
The same three idioms work identically on ``entities``, ``regulations``,
``rpsf``, and ``normativa``.
"""

from __future__ import annotations

import logging
import sys
from itertools import islice
from typing import Any

from cerberus_compliance import CerberusAPIError, CerberusClient

logger = logging.getLogger("cerberus_compliance.examples.cursor_pagination")

PREVIEW_SIZE = 20


def _fmt(value: Any) -> str:
    """Render ``None`` as ``'-'`` and coerce everything else to ``str``."""
    return "-" if value is None else str(value)


def _print_header(title: str) -> None:
    """Print a wide headline above each section."""
    bar = "=" * 72
    print(f"\n{bar}\n{title}\n{bar}")


def _render(row: dict[str, Any]) -> str:
    """Fixed-width one-line rendering of a sanction row."""
    fecha = _fmt(row.get("fecha_resolucion"))
    estado = _fmt(row.get("estado"))
    multa = _fmt(row.get("multa_uf"))
    infra = _fmt(row.get("infraccion"))
    return f"  [{fecha}] estado={estado:10s} multa_uf={multa:8s} | {infra}"


def main() -> int:
    """Exercise the three pagination idioms; returns a POSIX exit code."""
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
    """Print the three pagination sections."""
    _print_header("1. list(iter_all()) — materialise the full corpus")
    everything = list(client.sanctions.iter_all())
    print(f"  {len(everything)} record(s) in total")
    for row in everything[:3]:
        print(_render(row))
    if len(everything) > 3:
        print(f"  ... ({len(everything) - 3} more)")

    _print_header(f"2. islice(iter_all(), {PREVIEW_SIZE}) — bounded preview")
    preview = list(islice(client.sanctions.iter_all(), PREVIEW_SIZE))
    print(f"  fetched {len(preview)} of at most {PREVIEW_SIZE} rows")
    for row in preview:
        print(_render(row))

    _print_header("3. streaming loop — one row at a time, break early")
    seen = 0
    active_seen = 0
    for row in client.sanctions.iter_all():
        seen += 1
        if row.get("estado") == "vigente":
            active_seen += 1
        if seen >= PREVIEW_SIZE:
            break
    print(f"  streamed {seen} row(s); {active_seen} were estado='vigente'")


if __name__ == "__main__":
    sys.exit(main())
