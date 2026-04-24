"""Browse CMF sanctions via the ``client.sanctions`` resource.

Runnable: ``CERBERUS_API_KEY=<your-key> python examples/sanctions_browse.py``
Tier required: ``professional`` (scopes ``sanctions:read``, ``entities:read``).
Expected runtime: ~400 ms.

The example demonstrates the three read idioms on the sanctions sub-resource:

1. ``client.sanctions.list()`` — paginated list with server-side filters
   (``source`` / ``target_id`` / ``active`` / ``limit``).
2. ``client.sanctions.get(id)`` — fetch a single sanction by its internal id.
3. ``client.entities.sanctions(entity_id)`` — every sanction tied to an
   entity. Under the hood this hits ``GET /v1/sanctions/by-entity/{id}``.

We use Enel Chile (RUT ``90.320.000-6``) to demonstrate the per-entity
flow, because the prod seed carries a *prescrita* (expired) historical
sanction for NCG 30 ``estados financieros`` filing. If the registry is
clean for a given RUT the example says so explicitly rather than crashing.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

from cerberus_compliance import (
    CerberusAPIError,
    CerberusClient,
    NotFoundError,
)

logger = logging.getLogger("cerberus_compliance.examples.sanctions_browse")

DEFAULT_RUT = "90.320.000-6"  # Enel Chile SA — has an historical CMF sanction.
LIST_PAGE_LIMIT = 5


def _fmt(value: Any) -> str:
    """Render ``None`` as ``'-'`` and coerce everything else to ``str``."""
    return "-" if value is None else str(value)


def _print_header(title: str) -> None:
    """Print a wide headline above each section."""
    bar = "=" * 72
    print(f"\n{bar}\n{title}\n{bar}")


def _render_sanction(sanction: dict[str, Any]) -> str:
    """Format a sanction row as a single fixed-width line."""
    return (
        f"  [{_fmt(sanction.get('fecha_resolucion'))}] "
        f"estado={_fmt(sanction.get('estado')):10s} "
        f"multa_uf={_fmt(sanction.get('multa_uf')):8s} "
        f"| {_fmt(sanction.get('infraccion'))}"
    )


def main(rut: str) -> int:
    """Run the full sanctions walk-through against prod; returns an exit code."""
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    try:
        client = CerberusClient()
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    with client:
        try:
            _run(client, rut)
        except CerberusAPIError as exc:
            print(f"error: api failure: {exc}", file=sys.stderr)
            return 1

    return 0


def _run(client: CerberusClient, rut: str) -> None:
    """Print (1) catalogue, (2) detail, (3) per-entity sanctions sections."""
    _print_header(f"1. sanctions.list(limit={LIST_PAGE_LIMIT})")
    first_page = client.sanctions.list(limit=LIST_PAGE_LIMIT)
    print(f"  returned {len(first_page)} records")
    for sanction in first_page:
        print(_render_sanction(sanction))

    if not first_page:
        print("  (no sanctions on the first page — skipping detail lookup)")
        return

    first_id = first_page[0]["id"]
    _print_header(f"2. sanctions.get({first_id!r})")
    try:
        detail = client.sanctions.get(first_id)
    except NotFoundError as exc:
        print(f"  not found: {exc.detail}")
    else:
        for key in (
            "id",
            "cmf_resolucion_id",
            "entity_id",
            "fecha_resolucion",
            "infraccion",
            "multa_uf",
            "multa_clp",
            "estado",
            "persona_natural_rut",
            "persona_natural_nombre",
        ):
            print(f"  {key:28s}: {_fmt(detail.get(key))}")

    _print_header(f"3. entities.sanctions(by rut={rut!r})")
    header = client.entities.by_rut(rut)
    entity_id = header["id"]
    print(f"  resolved {header['legal_name']} -> id={entity_id}")
    records = client.entities.sanctions(entity_id)
    if not records:
        print("  (no sanctions on record for this entity — registry is clean)")
    else:
        print(f"  {len(records)} sanction(s) against {header['legal_name']}")
        for sanction in records:
            print(_render_sanction(sanction))


if __name__ == "__main__":
    rut_arg = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("CERBERUS_DEMO_RUT", DEFAULT_RUT)
    sys.exit(main(rut_arg))
