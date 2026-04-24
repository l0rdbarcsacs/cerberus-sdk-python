"""KYB (Know Your Business) quickstart for the Cerberus Compliance SDK.

Runnable: ``CERBERUS_API_KEY=<your-key> python examples/kyb_quickstart.py``
Tier required: ``professional`` (scope ``kyb:read``).
Expected runtime: ~300 ms.

Given a Chilean tax id (RUT), call the flagship aggregate endpoint
(``GET /v1/kyb/{rut}``) to retrieve a consolidated profile:

* Entity header (id, legal name, RUT, regulated sector).
* Risk score and cache freshness metadata.
* Optional dimensions requested via ``include=[...]``:
  ``directors``, ``lei``, ``sanctions``, ``regulations``, ``material_events``.

Usage::

    # Zero-args run — uses the seed demo RUT (96.505.760-9 = Falabella SA):
    export CERBERUS_API_KEY=ck_live_...
    python examples/kyb_quickstart.py

    # Or specify a RUT explicitly:
    python examples/kyb_quickstart.py --rut 96.505.760-9

    # Ask for a richer bundle:
    python examples/kyb_quickstart.py --rut 96.505.760-9 --include directors,lei,sanctions

    # Point-in-time view:
    python examples/kyb_quickstart.py --rut 96.505.760-9 --as-of 2024-01-01

Optional flags ``--base-url`` and ``--api-key`` override the defaults for
staging / local runs. Install ``rich`` (``pip install rich``) for prettier
output; plain text is used automatically when ``rich`` is unavailable.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from typing import TYPE_CHECKING, Any

from cerberus_compliance import (
    AuthError,
    CerberusAPIError,
    CerberusClient,
    NotFoundError,
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
        default="96.505.760-9",
        help=(
            "Chilean tax id (RUT) to resolve. Defaults to 96.505.760-9 (Falabella SA) "
            "so the example runs out of the box for design partners."
        ),
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
    parser.add_argument(
        "--as-of",
        default=None,
        help="Point-in-time snapshot date (YYYY-MM-DD). Defaults to live.",
    )
    parser.add_argument(
        "--include",
        default=None,
        help=(
            "Comma-separated dimensions to embed "
            "(directors,lei,sanctions,regulations,material_events)."
        ),
    )
    return parser


def _parse_as_of(value: str | None) -> date | None:
    """Parse a ``YYYY-MM-DD`` string into a :class:`date`, or ``None``."""
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise SystemExit(f"invalid --as-of value {value!r}: {exc}") from exc


def _parse_include(value: str | None) -> list[str] | None:
    """Parse a comma-separated string into a non-empty list, or ``None``."""
    if value is None:
        return None
    parts = [p.strip() for p in value.split(",") if p.strip()]
    return parts or None


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


def _as_list(value: Any) -> list[dict[str, Any]]:
    """Return ``value`` as a ``list[dict]``, or ``[]`` when malformed."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _render_rich(profile: dict[str, Any]) -> None:
    """Render the KYB profile using the optional ``rich`` library."""
    console = Console()

    header = Table(title="KYB profile", show_header=False, header_style="bold cyan")
    header.add_column("Field", style="bold")
    header.add_column("Value")
    header.add_row("rut", _as_str(profile.get("rut")))
    header.add_row("legal_name", _as_str(profile.get("legal_name") or profile.get("name")))
    header.add_row("sector", _as_str(profile.get("sector")))
    header.add_row("status", _as_str(profile.get("status")))
    header.add_row("risk_score", _as_str(profile.get("risk_score")))
    header.add_row("cache_status", _as_str(profile.get("cache_status")))
    header.add_row("lei", _as_str(profile.get("lei")))
    console.print(header)

    directors = _as_list(profile.get("directors"))
    if directors:
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
        console.print(directors_table)

    sanctions = _as_list(profile.get("sanctions"))
    if sanctions:
        sanctions_table = Table(title="Sanctions", header_style="bold red")
        sanctions_table.add_column("source")
        sanctions_table.add_column("active")
        sanctions_table.add_column("reason", overflow="fold")
        for sanction in sanctions:
            sanctions_table.add_row(
                _as_str(sanction.get("source")),
                _as_str(sanction.get("active")),
                _as_str(sanction.get("reason") or sanction.get("summary")),
            )
        console.print(sanctions_table)

    events = _as_list(profile.get("hechos_esenciales") or profile.get("material_events"))
    if events:
        events_table = Table(title="Recent material events", header_style="bold magenta")
        events_table.add_column("date")
        events_table.add_column("category")
        events_table.add_column("title", overflow="fold")
        for event in events[:5]:
            events_table.add_row(
                _as_str(event.get("event_date") or event.get("date")),
                _as_str(event.get("category")),
                _as_str(event.get("title") or event.get("summary")),
            )
        console.print(events_table)


def _render_plain(profile: dict[str, Any]) -> None:
    """Render the KYB profile as plain text (rich-less fallback)."""
    lines: list[str] = []
    lines.append("=" * 72)
    lines.append("KYB PROFILE")
    lines.append("-" * 72)
    lines.append(f"rut          : {_as_str(profile.get('rut'))}")
    lines.append(f"legal_name   : {_as_str(profile.get('legal_name') or profile.get('name'))}")
    lines.append(f"sector       : {_as_str(profile.get('sector'))}")
    lines.append(f"status       : {_as_str(profile.get('status'))}")
    lines.append(f"risk_score   : {_as_str(profile.get('risk_score'))}")
    lines.append(f"cache_status : {_as_str(profile.get('cache_status'))}")
    lines.append(f"lei          : {_as_str(profile.get('lei'))}")

    directors = _as_list(profile.get("directors"))
    if directors:
        lines.append("")
        lines.append("DIRECTORS")
        lines.append("-" * 72)
        for director in directors:
            name = _as_str(director.get("name") or director.get("full_name"))
            role = _as_str(director.get("role") or director.get("title"))
            rut = _as_str(director.get("rut"))
            lines.append(f"  {name} ({role}) - {rut}")

    sanctions = _as_list(profile.get("sanctions"))
    if sanctions:
        lines.append("")
        lines.append("SANCTIONS")
        lines.append("-" * 72)
        for sanction in sanctions:
            source = _as_str(sanction.get("source"))
            active = _as_str(sanction.get("active"))
            reason = _as_str(sanction.get("reason") or sanction.get("summary"))
            lines.append(f"  [{source}] active={active}: {reason}")

    events = _as_list(profile.get("hechos_esenciales") or profile.get("material_events"))
    if events:
        lines.append("")
        lines.append("RECENT MATERIAL EVENTS (max 5)")
        lines.append("-" * 72)
        for event in events[:5]:
            date_ = _as_str(event.get("event_date") or event.get("date"))
            category = _as_str(event.get("category"))
            title = _as_str(event.get("title") or event.get("summary"))
            lines.append(f"  [{date_}] ({category}) {title}")

    lines.append("=" * 72)
    print("\n".join(lines))


def render_summary(profile: dict[str, Any]) -> None:
    """Render the KYB profile; uses ``rich`` when available."""
    if _RICH_AVAILABLE:
        _render_rich(profile)
    else:
        _render_plain(profile)


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
    if isinstance(exc, NotFoundError):
        return f"no KYB record found ({exc.status} {exc.title})" + (
            f" [request_id={exc.request_id}]" if exc.request_id else ""
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

    as_of = _parse_as_of(args.as_of)
    include = _parse_include(args.include)

    try:
        client = CerberusClient(api_key=args.api_key, base_url=args.base_url)
    except ValueError as exc:
        return _fail(f"configuration error: {exc}")

    try:
        with client:
            profile = client.kyb.get(args.rut, as_of=as_of, include=include)
    except CerberusAPIError as exc:
        return _fail(_format_error(exc))

    render_summary(profile)
    return 0


def _fail(message: str) -> int:
    """Print ``message`` to stderr and return exit code 1."""
    print(f"error: {message}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
