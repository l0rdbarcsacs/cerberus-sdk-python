"""KYB (Know Your Business) quickstart for the Cerberus Compliance SDK.

Given a Chilean tax id (RUT), resolve the corresponding entity and print a
human-readable summary covering:

* The entity header (id, legal name, RUT, regulated sector).
* The five most recent material/essential facts.
* Currently active sanctions.
* Directors on record.
* Regulatory profile (regulator, license, status).

Usage::

    export CERBERUS_API_KEY=ck_live_...
    python examples/kyb_quickstart.py --rut 76.086.428-5

    # or, equivalently:
    python -m examples.kyb_quickstart --rut 76.086.428-5

Optional flags ``--base-url`` and ``--api-key`` override the defaults for
staging / local runs. Install ``rich`` (``pip install rich``) for prettier
output; plain text is used automatically when ``rich`` is unavailable.

This example targets the foundation-only surface of the SDK (Instance A).
Once ``feat/resources-1`` (Instance B) lands with typed sub-resource
accessors, the ``client._request`` calls below should be migrated to
``client.entities.get(...)``, ``client.entities.material_events.list(...)``,
etc. — see the ``TODO(#P4-B-merge)`` markers.
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import TYPE_CHECKING, Any

from cerberus_compliance import (
    AuthError,
    CerberusAPIError,
    CerberusClient,
    RateLimitError,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

try:
    from rich.console import Console
    from rich.table import Table

    _RICH_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency branch
    Console = None  # type: ignore[assignment, misc]
    Table = None  # type: ignore[assignment, misc]
    _RICH_AVAILABLE = False


logger = logging.getLogger("cerberus_compliance.examples.kyb_quickstart")


# --------------------------------------------------------------------------- #
# CLI                                                                         #
# --------------------------------------------------------------------------- #


def _build_parser() -> argparse.ArgumentParser:
    """Build the argparse parser for the KYB quickstart CLI."""
    parser = argparse.ArgumentParser(
        prog="kyb_quickstart",
        description="KYB quickstart: resolve a Chilean RUT and print a compliance summary.",
    )
    parser.add_argument(
        "--rut",
        required=True,
        help="Chilean tax id (RUT) to resolve, e.g. 76.086.428-5.",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="Override the Cerberus API base URL (defaults to production).",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="Cerberus API key. Falls back to the CERBERUS_API_KEY env var.",
    )
    return parser


# --------------------------------------------------------------------------- #
# API calls (low-level: use _request until Instance B merges)                 #
# --------------------------------------------------------------------------- #


def _unwrap_list(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract a ``list[dict]`` from a ``{"data": [...]}`` list envelope."""
    data = payload.get("data", [])
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def resolve_entity(client: CerberusClient, rut: str) -> dict[str, Any] | None:
    """Resolve the first entity matching ``rut``.

    Returns ``None`` when no entity is found.
    """
    # TODO(#P4-B-merge): switch to client.entities.get(rut=...) once feat/resources-1 lands.
    payload = client._request(
        "GET",
        "/entities",
        params={"rut": rut, "limit": 1},
    )
    entities = _unwrap_list(payload)
    return entities[0] if entities else None


def list_material_events(client: CerberusClient, entity_id: str) -> list[dict[str, Any]]:
    """Return the five most recent material/essential facts for an entity."""
    # TODO(#P4-B-merge): switch to client.entities.material_events.list(...) once
    # feat/resources-1 lands.
    payload = client._request(
        "GET",
        f"/entities/{entity_id}/material_events",
        params={"limit": 5},
    )
    return _unwrap_list(payload)


def list_active_sanctions(client: CerberusClient, entity_id: str) -> list[dict[str, Any]]:
    """Return the entity's currently active sanctions."""
    # TODO(#P4-B-merge): switch to client.entities.sanctions.list(active=True) once
    # feat/resources-1 lands.
    payload = client._request(
        "GET",
        f"/entities/{entity_id}/sanctions",
        params={"active": "true"},
    )
    return _unwrap_list(payload)


def list_directors(client: CerberusClient, entity_id: str) -> list[dict[str, Any]]:
    """Return the entity's directors on record."""
    # TODO(#P4-B-merge): switch to client.entities.directors.list(...) once
    # feat/resources-1 lands.
    payload = client._request("GET", f"/entities/{entity_id}/directors")
    return _unwrap_list(payload)


def fetch_regulations(client: CerberusClient, entity_id: str) -> list[dict[str, Any]]:
    """Return the entity's regulatory profile (regulator, license, status)."""
    # TODO(#P4-B-merge): switch to client.entities.regulations.list(...) once
    # feat/resources-1 lands.
    payload = client._request("GET", f"/entities/{entity_id}/regulations")
    return _unwrap_list(payload)


# --------------------------------------------------------------------------- #
# Rendering                                                                   #
# --------------------------------------------------------------------------- #


def _as_str(value: Any) -> str:
    """Coerce an arbitrary JSON value to a display string."""
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (str, int, float)):
        return str(value)
    return repr(value)


def _render_rich(
    entity: dict[str, Any],
    events: list[dict[str, Any]],
    sanctions: list[dict[str, Any]],
    directors: list[dict[str, Any]],
    regulations: list[dict[str, Any]],
) -> None:
    """Render the KYB summary using the optional ``rich`` library.

    Only invoked when :data:`_RICH_AVAILABLE` is ``True``, so the ``rich``
    symbols imported at module top are guaranteed to be real classes here.
    """
    console = Console()

    header = Table(title="Entity", show_header=False, header_style="bold cyan")
    header.add_column("Field", style="bold")
    header.add_column("Value")
    header.add_row("id", _as_str(entity.get("id")))
    header.add_row("legal_name", _as_str(entity.get("legal_name") or entity.get("name")))
    header.add_row("rut", _as_str(entity.get("rut")))
    header.add_row("sector", _as_str(entity.get("sector")))
    header.add_row("status", _as_str(entity.get("status")))
    console.print(header)

    events_table = Table(title="Recent material events (max 5)", header_style="bold magenta")
    events_table.add_column("date")
    events_table.add_column("category")
    events_table.add_column("title", overflow="fold")
    for event in events:
        events_table.add_row(
            _as_str(event.get("event_date") or event.get("date")),
            _as_str(event.get("category")),
            _as_str(event.get("title") or event.get("summary")),
        )
    if not events:
        events_table.add_row("-", "-", "(no events)")
    console.print(events_table)

    sanctions_table = Table(title="Active sanctions", header_style="bold red")
    sanctions_table.add_column("issued")
    sanctions_table.add_column("regulator")
    sanctions_table.add_column("reason", overflow="fold")
    for sanction in sanctions:
        sanctions_table.add_row(
            _as_str(sanction.get("issued_at") or sanction.get("date")),
            _as_str(sanction.get("regulator")),
            _as_str(sanction.get("reason") or sanction.get("summary")),
        )
    if not sanctions:
        sanctions_table.add_row("-", "-", "(no active sanctions)")
    console.print(sanctions_table)

    directors_table = Table(title="Directors", header_style="bold green")
    directors_table.add_column("name")
    directors_table.add_column("role")
    directors_table.add_column("rut")
    for director in directors:
        directors_table.add_row(
            _as_str(director.get("name") or director.get("full_name")),
            _as_str(director.get("role") or director.get("title")),
            _as_str(director.get("rut")),
        )
    if not directors:
        directors_table.add_row("-", "-", "(no directors on record)")
    console.print(directors_table)

    regulations_table = Table(title="Regulatory profile", header_style="bold yellow")
    regulations_table.add_column("regulator")
    regulations_table.add_column("license")
    regulations_table.add_column("status")
    for regulation in regulations:
        regulations_table.add_row(
            _as_str(regulation.get("regulator")),
            _as_str(regulation.get("license") or regulation.get("license_number")),
            _as_str(regulation.get("status")),
        )
    if not regulations:
        regulations_table.add_row("-", "-", "(no regulations on record)")
    console.print(regulations_table)


def _render_plain(
    entity: dict[str, Any],
    events: list[dict[str, Any]],
    sanctions: list[dict[str, Any]],
    directors: list[dict[str, Any]],
    regulations: list[dict[str, Any]],
) -> None:
    """Render the KYB summary as plain text (rich-less fallback)."""
    lines: list[str] = []
    lines.append("=" * 72)
    lines.append("ENTITY")
    lines.append("-" * 72)
    lines.append(f"id         : {_as_str(entity.get('id'))}")
    lines.append(f"legal_name : {_as_str(entity.get('legal_name') or entity.get('name'))}")
    lines.append(f"rut        : {_as_str(entity.get('rut'))}")
    lines.append(f"sector     : {_as_str(entity.get('sector'))}")
    lines.append(f"status     : {_as_str(entity.get('status'))}")

    lines.append("")
    lines.append("RECENT MATERIAL EVENTS (max 5)")
    lines.append("-" * 72)
    if not events:
        lines.append("  (no events)")
    for event in events:
        date = _as_str(event.get("event_date") or event.get("date"))
        category = _as_str(event.get("category"))
        title = _as_str(event.get("title") or event.get("summary"))
        lines.append(f"  [{date}] ({category}) {title}")

    lines.append("")
    lines.append("ACTIVE SANCTIONS")
    lines.append("-" * 72)
    if not sanctions:
        lines.append("  (no active sanctions)")
    for sanction in sanctions:
        issued = _as_str(sanction.get("issued_at") or sanction.get("date"))
        regulator = _as_str(sanction.get("regulator"))
        reason = _as_str(sanction.get("reason") or sanction.get("summary"))
        lines.append(f"  [{issued}] {regulator}: {reason}")

    lines.append("")
    lines.append("DIRECTORS")
    lines.append("-" * 72)
    if not directors:
        lines.append("  (no directors on record)")
    for director in directors:
        name = _as_str(director.get("name") or director.get("full_name"))
        role = _as_str(director.get("role") or director.get("title"))
        rut = _as_str(director.get("rut"))
        lines.append(f"  {name} ({role}) - {rut}")

    lines.append("")
    lines.append("REGULATORY PROFILE")
    lines.append("-" * 72)
    if not regulations:
        lines.append("  (no regulations on record)")
    for regulation in regulations:
        regulator = _as_str(regulation.get("regulator"))
        license_ = _as_str(regulation.get("license") or regulation.get("license_number"))
        status = _as_str(regulation.get("status"))
        lines.append(f"  {regulator} | license={license_} | status={status}")

    lines.append("=" * 72)
    print("\n".join(lines))  # noqa: T201 - example CLI output


def render_summary(
    entity: dict[str, Any],
    events: list[dict[str, Any]],
    sanctions: list[dict[str, Any]],
    directors: list[dict[str, Any]],
    regulations: list[dict[str, Any]],
) -> None:
    """Render the full KYB summary; uses ``rich`` when available."""
    if _RICH_AVAILABLE:
        _render_rich(entity, events, sanctions, directors, regulations)
    else:
        _render_plain(entity, events, sanctions, directors, regulations)


# --------------------------------------------------------------------------- #
# Entry point                                                                 #
# --------------------------------------------------------------------------- #


def _format_error(exc: CerberusAPIError) -> str:
    """Format a ``CerberusAPIError`` for CLI output, with actionable hints."""
    if isinstance(exc, AuthError):
        return (
            f"authentication failed ({exc.status} {exc.title}); "
            "check the --api-key flag or the CERBERUS_API_KEY environment variable"
        )
    if isinstance(exc, RateLimitError):
        retry_after = exc.retry_after
        if retry_after is not None:
            return f"rate limited (429 {exc.title}); retry after {retry_after:.1f} seconds" + (
                f" [request_id={exc.request_id}]" if exc.request_id else ""
            )
        return f"rate limited (429 {exc.title}); no Retry-After header was returned" + (
            f" [request_id={exc.request_id}]" if exc.request_id else ""
        )
    message = f"API error: {exc}"
    if exc.request_id and f"request_id={exc.request_id}" not in message:
        message = f"{message} [request_id={exc.request_id}]"
    return message


def main(argv: Sequence[str] | None = None) -> int:
    """Run the KYB quickstart. Returns a POSIX-style exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    try:
        client = CerberusClient(api_key=args.api_key, base_url=args.base_url)
    except ValueError as exc:
        return _fail(f"configuration error: {exc}")

    try:
        with client:
            entity = resolve_entity(client, args.rut)
            if entity is None:
                return _fail(f"no entity found for rut={args.rut!r}")

            entity_id = _as_str(entity.get("id"))
            events = list_material_events(client, entity_id)
            sanctions = list_active_sanctions(client, entity_id)
            directors = list_directors(client, entity_id)
            regulations = fetch_regulations(client, entity_id)
    except CerberusAPIError as exc:
        return _fail(_format_error(exc))

    render_summary(entity, events, sanctions, directors, regulations)
    return 0


def _fail(message: str) -> int:
    """Print ``message`` to stderr and return exit code 1."""
    print(f"error: {message}", file=sys.stderr)  # noqa: T201 - example CLI output
    return 1


if __name__ == "__main__":
    sys.exit(main())
