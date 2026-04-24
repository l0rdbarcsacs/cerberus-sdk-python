"""Explore the CMF Registro Público de Servicios Financieros (RPSF).

Runnable: ``CERBERUS_API_KEY=<your-key> python examples/rpsf_explore.py``
Tier required: ``professional`` (scope ``rpsf:read``).
Expected runtime: ~500 ms.

RPSF is the CMF public registry of authorised financial-service providers
under Ley 21.521 (fintech law) and the corresponding NCG norms. Each
record links an entity to one or more *servicios* (``corredora``,
``agente``, ``custodia_instrumentos_financieros``,
``plataforma_financiamiento_colectivo``…) with a registration status.

This example demonstrates:

1. ``client.rpsf.list(limit=...)`` — paginated catalogue.
2. ``client.rpsf.by_servicio("plataforma_financiamiento_colectivo")`` —
   every registered crowdfunding platform. Handy for market-mapping.
3. ``client.rpsf.by_entity(entity_id)`` — every inscription an entity
   holds (can span multiple services).
4. ``client.rpsf.get(id)`` — single inscription by its RPSF id.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

from cerberus_compliance import CerberusAPIError, CerberusClient, NotFoundError

logger = logging.getLogger("cerberus_compliance.examples.rpsf_explore")

DEFAULT_SERVICIO = "plataforma_financiamiento_colectivo"
LIST_PAGE_LIMIT = 5


def _fmt(value: Any) -> str:
    """Render ``None`` as ``'-'`` and coerce everything else to ``str``."""
    return "-" if value is None else str(value)


def _print_header(title: str) -> None:
    """Print a wide headline above each section."""
    bar = "=" * 72
    print(f"\n{bar}\n{title}\n{bar}")


def _render_row(row: dict[str, Any]) -> str:
    """Format a single RPSF row as a fixed-width line."""
    active = row.get("is_active")
    active_s = "yes" if active else ("no" if active is False else "-")
    return (
        f"  [{_fmt(row.get('fecha_inscripcion'))}] "
        f"active={active_s:3s} "
        f"servicio={_fmt(row.get('servicio')):40s} "
        f"resolucion={_fmt(row.get('resolucion_inscripcion'))}"
    )


def main(servicio: str) -> int:
    """Run the full RPSF walk-through against prod; returns an exit code."""
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    try:
        client = CerberusClient()
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    with client:
        try:
            _run(client, servicio)
        except CerberusAPIError as exc:
            print(f"error: api failure: {exc}", file=sys.stderr)
            return 1

    return 0


def _run(client: CerberusClient, servicio: str) -> None:
    """Print the four RPSF sections."""
    _print_header(f"1. rpsf.list(limit={LIST_PAGE_LIMIT})")
    page = client.rpsf.list(limit=LIST_PAGE_LIMIT)
    print(f"  returned {len(page)} records")
    for row in page:
        print(_render_row(row))

    _print_header(f"2. rpsf.by_servicio({servicio!r})")
    rows = client.rpsf.by_servicio(servicio)
    print(f"  {len(rows)} record(s) for servicio={servicio!r}")
    for row in rows:
        print(_render_row(row))

    if not rows:
        print("  (no inscriptions — cannot demo rpsf.by_entity without a target)")
        return

    target_entity_id = rows[0]["entity_id"]
    _print_header(f"3. rpsf.by_entity({target_entity_id!r})")
    entity_rows = client.rpsf.by_entity(target_entity_id)
    print(f"  {len(entity_rows)} inscription(s) for entity {target_entity_id}")
    for row in entity_rows:
        print(_render_row(row))

    _print_header(f"4. rpsf.get({rows[0]['id']!r})")
    try:
        detail = client.rpsf.get(rows[0]["id"])
    except NotFoundError as exc:
        print(f"  not found: {exc.detail}")
    else:
        for key in (
            "id",
            "entity_id",
            "servicio",
            "fecha_inscripcion",
            "fecha_cancelacion",
            "resolucion_inscripcion",
            "is_active",
        ):
            print(f"  {key:24s}: {_fmt(detail.get(key))}")


if __name__ == "__main__":
    servicio_arg = (
        sys.argv[1]
        if len(sys.argv) > 1
        else os.environ.get("CERBERUS_DEMO_SERVICIO", DEFAULT_SERVICIO)
    )
    sys.exit(main(servicio_arg))
