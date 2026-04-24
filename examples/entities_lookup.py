"""Resolve a Chilean entity end-to-end through the ``client.entities`` surface.

Runnable: ``CERBERUS_API_KEY=<your-key> python examples/entities_lookup.py``
Tier required: ``professional`` (scopes ``entities:read``, ``sanctions:read``).
Expected runtime: ~500 ms.

The example walks the most common lookup flow a design partner will write
against the entities sub-resource:

1. ``entities.by_rut(rut)`` — canonical RUT lookup that returns the entity
   header including the server-assigned ``id`` (UUID).
2. ``entities.get(id)`` — fetch the detailed entity record.
3. ``entities.directors(id)`` — list the current board.
4. ``entities.ownership(id)`` — return the LEI-backed parent/UBO chain.
5. ``entities.sanctions(id)`` — list sanctions against the entity (hits
   ``/sanctions/by-entity/{id}`` under the hood, per the v0.2.0 gap-audit
   fix).

The RUT used (``96.505.760-9``) is the production seed RUT for Falabella SA,
an IPSA issuer with 3 directors, an LEI, no active sanctions, and a recent
``hecho esencial``. Any other RUT in the directory will work — pass it as
the first positional CLI argument.
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

logger = logging.getLogger("cerberus_compliance.examples.entities_lookup")

DEFAULT_RUT = "96.505.760-9"  # Falabella SA — IPSA issuer, 3 directors, LEI.


def _fmt(value: Any) -> str:
    """Render ``None`` as ``'-'`` and coerce anything else to ``str``."""
    return "-" if value is None else str(value)


def _print_header(title: str) -> None:
    """Print a wide separator headline — keeps the CLI output scannable."""
    bar = "=" * 72
    print(f"\n{bar}\n{title}\n{bar}")


def main(rut: str) -> int:
    """Fetch + display the entity dossier for ``rut``; returns a POSIX exit code."""
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    try:
        client = CerberusClient()
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    with client:
        try:
            _run(client, rut)
        except NotFoundError as exc:
            print(f"error: entity not found for rut={rut!r}: {exc.detail}", file=sys.stderr)
            return 1
        except CerberusAPIError as exc:
            print(f"error: api failure: {exc}", file=sys.stderr)
            return 1

    return 0


def _run(client: CerberusClient, rut: str) -> None:
    """Perform the full entities walk-through and print the results."""
    _print_header(f"1. entities.by_rut({rut!r})")
    header = client.entities.by_rut(rut)
    entity_id = header["id"]
    print(f"  id           : {entity_id}")
    print(f"  rut          : {_fmt(header.get('rut'))}")
    print(f"  legal_name   : {_fmt(header.get('legal_name'))}")
    print(f"  fantasy_name : {_fmt(header.get('fantasy_name'))}")
    print(f"  entity_kind  : {_fmt(header.get('entity_kind'))}")
    print(f"  status       : {_fmt(header.get('status'))}")
    print(f"  lei          : {_fmt(header.get('lei'))}")
    print(f"  sanctions_ct : {_fmt(header.get('sanctions_count'))}")

    _print_header(f"2. entities.get({entity_id!r})")
    detail = client.entities.get(entity_id)
    for key in (
        "rut",
        "legal_name",
        "kind",
        "status",
        "lei",
        "active_sanctions_count",
        "director_count",
        "created_at",
    ):
        print(f"  {key:24s}: {_fmt(detail.get(key))}")

    _print_header(f"3. entities.directors({entity_id!r})")
    directors = client.entities.directors(entity_id)
    if not directors:
        print("  (no directors on record)")
    for d in directors:
        name = _fmt(d.get("persona_nombre"))
        cargo = _fmt(d.get("cargo"))
        prut = _fmt(d.get("persona_rut"))
        valid_from = _fmt(d.get("valid_from"))
        print(f"  - {name:40s} | {cargo:20s} | rut={prut:14s} | since={valid_from}")

    _print_header(f"4. entities.ownership({entity_id!r})")
    ownership = client.entities.ownership(entity_id)
    print(f"  subject_lei     : {_fmt(ownership.get('subject_lei'))}")
    direct_parent = ownership.get("direct_parent")
    if isinstance(direct_parent, dict):
        print(
            f"  direct_parent   : lei={_fmt(direct_parent.get('lei'))} "
            f"name={_fmt(direct_parent.get('legal_name'))}"
        )
    else:
        print("  direct_parent   : -")
    ultimate_parent = ownership.get("ultimate_parent")
    if isinstance(ultimate_parent, dict):
        print(
            f"  ultimate_parent : lei={_fmt(ultimate_parent.get('lei'))} "
            f"name={_fmt(ultimate_parent.get('legal_name'))}"
        )
    else:
        print("  ultimate_parent : -")

    _print_header(f"5. entities.sanctions({entity_id!r})  →  /sanctions/by-entity/{{id}}")
    sanctions = client.entities.sanctions(entity_id)
    if not sanctions:
        print("  (no sanctions — entity is clean in the CMF registry)")
    for s in sanctions:
        fecha = _fmt(s.get("fecha_resolucion"))
        estado = _fmt(s.get("estado"))
        multa = _fmt(s.get("multa_uf"))
        infra = _fmt(s.get("infraccion"))
        print(f"  - [{fecha}] estado={estado:10s} multa_uf={multa:8s} | {infra}")


if __name__ == "__main__":
    rut_arg = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("CERBERUS_DEMO_RUT", DEFAULT_RUT)
    sys.exit(main(rut_arg))
