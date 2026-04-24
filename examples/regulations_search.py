"""Browse and full-text search the CMF regulations catalogue.

Runnable: ``CERBERUS_API_KEY=<your-key> python examples/regulations_search.py``
Tier required: ``professional`` (scope ``regulations:read``).
Expected runtime: ~350 ms.

Walks the three idioms on ``client.regulations``:

1. ``client.regulations.list(limit=3)`` — catalogue page.
2. ``client.regulations.get(id)`` — detail fetch for the first result.
3. ``client.regulations.search(q="sanciones")`` — full-text search over
   the corpus. Returns ranked hits with a ``snippet`` preview.

The search backend is Postgres ``ts_rank``; the example prints the ranked
``snippet`` so partners can see what the API returns without having to
open the OpenAPI schema.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

from cerberus_compliance import CerberusAPIError, CerberusClient, NotFoundError

logger = logging.getLogger("cerberus_compliance.examples.regulations_search")

DEFAULT_QUERY = "sanciones"
LIST_PAGE_LIMIT = 3


def _fmt(value: Any) -> str:
    """Render ``None`` as ``'-'`` and coerce everything else to ``str``."""
    return "-" if value is None else str(value)


def _print_header(title: str) -> None:
    """Print a wide headline above each section."""
    bar = "=" * 72
    print(f"\n{bar}\n{title}\n{bar}")


def main(query: str) -> int:
    """Run the regulations walk-through against prod; returns an exit code."""
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    try:
        client = CerberusClient()
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    with client:
        try:
            _run(client, query)
        except CerberusAPIError as exc:
            print(f"error: api failure: {exc}", file=sys.stderr)
            return 1

    return 0


def _run(client: CerberusClient, query: str) -> None:
    """Print catalogue, detail, and search sections."""
    _print_header(f"1. regulations.list(limit={LIST_PAGE_LIMIT})")
    first_page = client.regulations.list(limit=LIST_PAGE_LIMIT)
    print(f"  returned {len(first_page)} records")
    for reg in first_page:
        cmf_id = _fmt(reg.get("cmf_id"))
        kind = _fmt(reg.get("type"))
        title = _fmt(reg.get("title"))
        estado = _fmt(reg.get("estado"))
        print(f"  - [{kind:8s}] {cmf_id:10s} estado={estado:10s} | {title}")

    if not first_page:
        print("  (empty catalogue — skipping detail lookup)")
        return

    first_id = first_page[0]["id"]
    _print_header(f"2. regulations.get({first_id!r})")
    try:
        detail = client.regulations.get(first_id)
    except NotFoundError as exc:
        print(f"  not found: {exc.detail}")
    else:
        for key in (
            "id",
            "cmf_id",
            "type",
            "title",
            "issued_at",
            "source_url",
            "ncg_number",
            "circular_number",
            "estado",
        ):
            print(f"  {key:18s}: {_fmt(detail.get(key))}")

    _print_header(f"3. regulations.search(q={query!r})")
    hits = client.regulations.search(query)
    if not hits:
        print(f"  (no hits for q={query!r})")
        return
    print(f"  {len(hits)} hit(s) for q={query!r}")
    for hit in hits:
        rank = hit.get("rank")
        rank_str = f"{rank:.3f}" if isinstance(rank, (int, float)) else "-"
        title = _fmt(hit.get("title"))
        snippet = _fmt(hit.get("snippet"))
        print(f"  - rank={rank_str} | {title}")
        print(f"    snippet: {snippet}")


if __name__ == "__main__":
    query_arg = (
        sys.argv[1] if len(sys.argv) > 1 else os.environ.get("CERBERUS_DEMO_QUERY", DEFAULT_QUERY)
    )
    sys.exit(main(query_arg))
