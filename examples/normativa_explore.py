"""Browse the regulatory-text catalogue via ``client.normativa``.

Runnable: ``CERBERUS_API_KEY=<your-key> python examples/normativa_explore.py``
Tier required: ``professional`` (scope ``normativa:read``).
Expected runtime: ~400 ms.

A *normativa* record is an authoritative regulatory text the Cerberus
platform tracks — Chilean Ley 21.521, Ley 21.719, CMF ``oficios
circulares``, NCG norms (NCG 380 / NCG 461 / NCG 514 …) and anchor-point
international frameworks. Each record has an associated market-segment
mapping returned by ``/normativa/{id}/mercado``.

This example exercises:

1. ``client.normativa.list(limit=...)`` — paginated catalogue.
2. ``client.normativa.get(id)`` — single record with full text.
3. ``client.normativa.mercado(id)`` — the market segment classification
   for the record (``mercado_code``, confidence, method).
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

from cerberus_compliance import CerberusAPIError, CerberusClient, NotFoundError

logger = logging.getLogger("cerberus_compliance.examples.normativa_explore")

LIST_PAGE_LIMIT = 3


def _fmt(value: Any) -> str:
    """Render ``None`` as ``'-'`` and coerce everything else to ``str``."""
    return "-" if value is None else str(value)


def _print_header(title: str) -> None:
    """Print a wide headline above each section."""
    bar = "=" * 72
    print(f"\n{bar}\n{title}\n{bar}")


def main(norma_id: str | None) -> int:
    """Run the normativa walk-through; resolves an id from the catalogue when missing."""
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    try:
        client = CerberusClient()
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    with client:
        try:
            _run(client, norma_id)
        except CerberusAPIError as exc:
            print(f"error: api failure: {exc}", file=sys.stderr)
            return 1

    return 0


def _run(client: CerberusClient, norma_id: str | None) -> None:
    """Print catalogue, detail, and mercado mapping sections."""
    _print_header(f"1. normativa.list(limit={LIST_PAGE_LIMIT})")
    page = client.normativa.list(limit=LIST_PAGE_LIMIT)
    print(f"  returned {len(page)} records")
    for row in page:
        kind = _fmt(row.get("type"))
        cmf_id = _fmt(row.get("cmf_id"))
        title = _fmt(row.get("title"))
        issued = _fmt(row.get("issued_at"))
        print(f"  - [{kind:8s}] {cmf_id:10s} issued={issued[:10]} | {title}")

    # Pick the first catalogue entry when the caller did not supply one.
    target_id = norma_id or (page[0]["id"] if page else None)
    if target_id is None:
        print("  (empty catalogue — cannot demo detail / mercado endpoints)")
        return

    _print_header(f"2. normativa.get({target_id!r})")
    try:
        detail = client.normativa.get(target_id)
    except NotFoundError as exc:
        print(f"  not found: {exc.detail}")
        return

    for key in (
        "id",
        "cmf_id",
        "type",
        "title",
        "issued_at",
        "source_url",
        "ncg_number",
        "circular_number",
        "mercado_code",
        "mercado_label",
        "supersedes_regulation_id",
        "superseded_by_regulation_id",
    ):
        print(f"  {key:28s}: {_fmt(detail.get(key))}")

    full_text = detail.get("full_text")
    if isinstance(full_text, str):
        preview = full_text[:240].replace("\n", " ") + ("…" if len(full_text) > 240 else "")
        print(f"  full_text (preview)         : {preview}")

    _print_header(f"3. normativa.mercado({target_id!r})")
    mercado = client.normativa.mercado(target_id)
    for key in ("mercado_code", "mercado_label", "confidence", "method"):
        print(f"  {key:14s}: {_fmt(mercado.get(key))}")


if __name__ == "__main__":
    norma_arg = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("CERBERUS_DEMO_NORMA_ID")
    sys.exit(main(norma_arg))
