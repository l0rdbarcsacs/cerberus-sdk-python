"""Fetch a natural-person regulatory profile.

Runnable: ``CERBERUS_API_KEY=<your-key> python examples/persons_profile.py``
Tier required: ``professional`` (scope ``persons:read``).
Expected runtime: ~300 ms.

Natural persons (``personas naturales``) are identified by their Chilean
RUT. The only production endpoint on the ``/persons`` namespace is
``GET /persons/{rut}/regulatory-profile``, which returns:

- ``rut`` / ``nombre_completo`` — canonical identifiers.
- ``cargos_vigentes`` — active director/officer positions at Chilean
  entities, each carrying ``entity_id`` + ``entity_name`` + ``cargo``.
- ``cargos_historicos_count`` — how many past positions are on file.
- ``sanciones_personales_count`` — CMF personal sanctions on the RUT.
- ``pep_lite_flag`` + ``pep_lite_reasons`` — the Cerberus PEP-lite signal
  (lightweight politically-exposed-person heuristic). A ``True`` flag does
  *not* mean the person is a PEP under Ley 19.913; it means a KYC review
  is recommended.

We use ``11.111.111-1`` (Carlos Heller Solari — president of Falabella in
the seed corpus) as the demo RUT because the profile carries an active
directorship and a PEP-lite flag with reasons, so the example prints
something visibly useful.

Migration note: ``client.persons.list()`` / ``client.persons.get()`` are
deprecated — they never backed a real endpoint. Use
``regulatory_profile(rut)`` when you already know the RUT, or
``client.entities.directors(id)`` to enumerate personas tied to an entity.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

from cerberus_compliance import CerberusAPIError, CerberusClient, NotFoundError

logger = logging.getLogger("cerberus_compliance.examples.persons_profile")

DEFAULT_RUT = "11.111.111-1"  # Carlos Heller Solari — director of Falabella.


def _fmt(value: Any) -> str:
    """Render ``None`` as ``'-'`` and coerce anything else to ``str``."""
    return "-" if value is None else str(value)


def _print_header(title: str) -> None:
    """Print a wide headline above each section."""
    bar = "=" * 72
    print(f"\n{bar}\n{title}\n{bar}")


def main(rut: str) -> int:
    """Fetch the profile for ``rut`` and print a compliance summary."""
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    try:
        client = CerberusClient()
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    with client:
        try:
            profile = client.persons.regulatory_profile(rut)
        except NotFoundError as exc:
            print(f"error: no profile for rut={rut!r}: {exc.detail}", file=sys.stderr)
            return 1
        except CerberusAPIError as exc:
            print(f"error: api failure: {exc}", file=sys.stderr)
            return 1

    _render(profile)
    return 0


def _render(profile: dict[str, Any]) -> None:
    """Pretty-print the regulatory profile."""
    _print_header(f"persons.regulatory_profile({profile.get('rut')!r})")
    print(f"  rut             : {_fmt(profile.get('rut'))}")
    print(f"  nombre_completo : {_fmt(profile.get('nombre_completo'))}")
    print(f"  cargos_hist_ct  : {_fmt(profile.get('cargos_historicos_count'))}")
    print(f"  sanciones_ct    : {_fmt(profile.get('sanciones_personales_count'))}")
    print(f"  pep_lite_flag   : {_fmt(profile.get('pep_lite_flag'))}")
    print(f"  cache_status    : {_fmt(profile.get('cache_status'))}")
    print(f"  request_id      : {_fmt(profile.get('request_id'))}")

    reasons = profile.get("pep_lite_reasons")
    if isinstance(reasons, list) and reasons:
        print("\n  PEP-lite reasons:")
        for reason in reasons:
            print(f"    - {_fmt(reason)}")

    cargos = profile.get("cargos_vigentes")
    if isinstance(cargos, list) and cargos:
        print("\n  Active positions:")
        for cargo in cargos:
            entity_name = _fmt(cargo.get("entity_name"))
            entity_rut = _fmt(cargo.get("entity_rut"))
            role = _fmt(cargo.get("cargo"))
            since = _fmt(cargo.get("fecha_inicio"))
            print(f"    - {role:15s} @ {entity_name:45s} (rut={entity_rut}) since {since}")
    elif isinstance(cargos, list):
        print("\n  (no active positions on record)")


if __name__ == "__main__":
    rut_arg = (
        sys.argv[1]
        if len(sys.argv) > 1
        else os.environ.get("CERBERUS_DEMO_PERSONA_RUT", DEFAULT_RUT)
    )
    sys.exit(main(rut_arg))
