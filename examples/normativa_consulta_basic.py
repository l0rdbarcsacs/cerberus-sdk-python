"""Browse CMF ``normativa en consulta`` — open / closed regulatory drafts.

Runnable: ``CERBERUS_API_KEY=<your-key> python examples/normativa_consulta_basic.py``
Tier required: ``professional`` (scope ``normativa:read``).
Expected runtime: ~300 ms.

The backend ingests ``normativa_tramite.php`` and
``normativa_tramite_cerrada.php`` every 2 hours. Each row is one CMF
consultation with ``fecha_apertura`` / ``fecha_cierre`` / ``estado`` and a
free-text ``mercado_label`` tagging the regulatory segment. Open
consultations are leading indicators of obligation changes 30-90 days
out; closed consultations tell you when the matching NCG / Circular
ships.

This example shows:

1. ``client.normativa_consulta.list(estado="abierta")`` — all currently
   open consultations.
2. ``client.normativa_consulta.list(estado="cerrada", limit=10)`` — the
   ten most-recently closed consultations.
3. A per-mercado rollup of the open consultations (what regulatory
   segments currently have the most movement).
"""

from __future__ import annotations

import logging
import os
import sys
from collections import Counter
from typing import Any

from cerberus_compliance import CerberusAPIError, CerberusClient

logger = logging.getLogger("cerberus_compliance.examples.normativa_consulta_basic")


def _fmt(value: Any) -> str:
    """Render ``None`` as ``'-'`` and coerce everything else to ``str``."""
    return "-" if value is None else str(value)


def _print_header(title: str) -> None:
    """Print a wide headline above each section."""
    bar = "=" * 72
    print(f"\n{bar}\n{title}\n{bar}")


def _render_row(row: dict[str, Any]) -> str:
    return (
        f"  [{_fmt(row.get('estado')):8s}] "
        f"open={_fmt(row.get('fecha_apertura')):10s} "
        f"close={_fmt(row.get('fecha_cierre')):10s} "
        f"mercado={_fmt(row.get('mercado_label')):20s} "
        f"| {_fmt(row.get('titulo'))}"
    )


def main() -> int:
    """Run the normativa-consulta walk-through; returns an exit code."""
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
    """Three-section view of the normativa-consulta catalogue."""
    _print_header("1. normativa_consulta.list(estado='abierta')")
    open_rows = client.normativa_consulta.list(estado="abierta", limit=50)
    print(f"  {len(open_rows)} open consultation(s)")
    for row in open_rows[:20]:
        print(_render_row(row))
    if len(open_rows) > 20:
        print(f"  ... ({len(open_rows) - 20} more)")

    _print_header("2. normativa_consulta.list(estado='cerrada', limit=10)")
    closed_rows = client.normativa_consulta.list(estado="cerrada", limit=10)
    print(f"  {len(closed_rows)} closed consultation(s)")
    for row in closed_rows:
        print(_render_row(row))

    _print_header("3. Rollup: open consultations by mercado")
    counter: Counter[str] = Counter(_fmt(row.get("mercado_label")) for row in open_rows)
    for mercado, count in counter.most_common():
        print(f"  {mercado:30s} {count:4d}")


if __name__ == "__main__":
    sys.exit(main())


__all__ = ["main"]

# Documents the expected env var — kept out of the function body so the
# example reads top-down.
_ = os.environ.get("CERBERUS_API_KEY")
