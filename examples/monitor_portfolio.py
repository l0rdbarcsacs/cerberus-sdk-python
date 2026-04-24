"""Async portfolio monitor for the Cerberus Compliance API.

Reads a CSV file of Chilean tax ids (RUTs) and polls the Cerberus
``/entities/{id}/material_events`` endpoint every ``--interval`` seconds,
surfacing newly-published essential facts as log lines.

Usage::

    export CERBERUS_API_KEY=ck_live_...
    python -m examples.monitor_portfolio --csv portfolio.csv --interval 60

The CSV must have a header row containing a ``rut`` column; extra columns
are ignored. The example resolves each RUT to an entity id via
``GET /entities?rut=<rut>&limit=1`` on start-up, then enters a polling
loop that diffs new ``event_id``s against an in-memory per-entity set.

The file is intentionally self-contained so a first-time user can read
it top-to-bottom. It uses only the public SDK surface currently shipped
(``AsyncCerberusClient`` and the error hierarchy); once the B/C resource
sub-accessors land it should migrate to ``client.entities.iter_all(...)``.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone
from typing import Any

from cerberus_compliance import (
    AsyncCerberusClient,
    AuthError,
    CerberusAPIError,
    QuotaError,
    RateLimitError,
    ServerError,
    ValidationError,
)

__all__ = ["amain", "main"]

logger = logging.getLogger("cerberus.monitor")

DEFAULT_INTERVAL_SECONDS = 60.0
DEFAULT_MAX_ENTITIES = 50
DEFAULT_PAGE_LIMIT = 50
MAX_FOLLOWUP_PAGES = 5
EXIT_OK = 0
EXIT_AUTH = 2
EXIT_USAGE = 64


def _parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse CLI flags into an :class:`argparse.Namespace`.

    Kept separate from :func:`amain` so the CLI surface is trivial to
    unit-test. ``argparse`` writes to stderr and raises ``SystemExit`` on
    bad input, which is the behaviour we want for a script entry point.
    """
    parser = argparse.ArgumentParser(
        prog="monitor_portfolio",
        description=(
            "Poll the Cerberus Compliance API for new material events "
            "across a portfolio of Chilean RUTs."
        ),
    )
    parser.add_argument(
        "--csv",
        required=True,
        help="Path to a CSV file with a header row containing a 'rut' column.",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=DEFAULT_INTERVAL_SECONDS,
        help="Seconds between polling ticks (default: 60).",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="Override the SDK base URL (defaults to the production Cerberus endpoint).",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="Cerberus API key. Falls back to the CERBERUS_API_KEY env var.",
    )
    parser.add_argument(
        "--max-entities",
        type=int,
        default=DEFAULT_MAX_ENTITIES,
        help="Sanity cap on how many unique RUTs to poll (default: 50).",
    )
    return parser.parse_args(argv)


def _read_ruts(csv_path: str, max_entities: int) -> list[str]:
    """Read unique, non-empty ``rut`` values from a CSV header file.

    Order is preserved (first occurrence wins) so logs stay stable across
    runs. Raises :class:`ValueError` when the file has no ``rut`` column.
    """
    ruts: list[str] = []
    seen: set[str] = set()

    with open(csv_path, encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or "rut" not in reader.fieldnames:
            raise ValueError(f"CSV {csv_path!r} is missing a 'rut' header column")

        for row in reader:
            raw = (row.get("rut") or "").strip()
            if not raw or raw in seen:
                continue
            seen.add(raw)
            ruts.append(raw)
            if len(ruts) >= max_entities:
                logger.warning(
                    "truncating portfolio to first %d RUTs (max-entities cap)",
                    max_entities,
                )
                break

    return ruts


def _now_utc_iso() -> str:
    """Return the current UTC instant as an ISO 8601 string with ``Z`` suffix."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


async def _resolve_entity(
    client: AsyncCerberusClient,
    rut: str,
) -> dict[str, Any] | None:
    """Resolve a single RUT to an entity summary via ``GET /entities``.

    Returns ``None`` when the RUT is unknown, malformed, or the server
    returns a transient error. The caller logs and moves on — start-up
    should never abort because one RUT is bad.
    """
    try:
        # TODO(#P4-B-merge): switch to client.entities.iter_all(...) once feat/resources-1 lands.
        response = await client._request(
            "GET",
            "/entities",
            params={"rut": rut, "limit": 1},
        )
    except AuthError:
        raise
    except ValidationError as exc:
        logger.error("invalid rut %s: %s", rut, exc)
        return None
    except (QuotaError, RateLimitError, ServerError, CerberusAPIError) as exc:
        logger.warning("could not resolve rut %s: %s", rut, exc)
        return None

    data = response.get("data")
    if not isinstance(data, list) or not data:
        logger.warning("rut %s not found in Cerberus directory, skipping", rut)
        return None

    first = data[0]
    if not isinstance(first, dict):
        logger.warning("unexpected payload shape for rut %s, skipping", rut)
        return None

    return first


async def _fetch_events(
    client: AsyncCerberusClient,
    entity_id: str,
    since: str | None,
) -> list[dict[str, Any]]:
    """Fetch material events for ``entity_id`` published after ``since``.

    Pages manually using the ``{"data": [...], "next": "..."}`` envelope
    emitted by the API. Follow-up pages are capped at
    :data:`MAX_FOLLOWUP_PAGES` to bound each tick's work.
    """
    params: dict[str, Any] = {"limit": DEFAULT_PAGE_LIMIT}
    if since is not None:
        params["since"] = since

    response = await client._request(
        "GET",
        f"/entities/{entity_id}/material_events",
        params=params,
    )

    collected: list[dict[str, Any]] = []
    data = response.get("data")
    if isinstance(data, list):
        collected.extend(item for item in data if isinstance(item, dict))

    next_token = response.get("next")
    pages = 0
    while isinstance(next_token, str) and next_token and pages < MAX_FOLLOWUP_PAGES:
        pages += 1
        follow = await client._request(
            "GET",
            f"/entities/{entity_id}/material_events",
            params={"cursor": next_token},
        )
        follow_data = follow.get("data")
        if isinstance(follow_data, list):
            collected.extend(item for item in follow_data if isinstance(item, dict))
        next_token = follow.get("next")

    if pages >= MAX_FOLLOWUP_PAGES and isinstance(next_token, str) and next_token:
        logger.warning(
            "entity %s still has more pages after %d follow-ups; deferring to next tick",
            entity_id,
            MAX_FOLLOWUP_PAGES,
        )

    return collected


async def _poll_entity(
    client: AsyncCerberusClient,
    rut: str,
    entity: dict[str, Any],
    since: str | None,
    seen_event_ids: set[str],
) -> tuple[int, str | None]:
    """Poll a single entity once.

    Returns a tuple ``(new_events_count, new_since_iso)``. ``new_since_iso``
    is ``None`` when the request failed for a recoverable reason — the
    caller then preserves the previous ``since`` value so the next tick
    re-asks for the same window.
    """
    entity_id = entity.get("id")
    if not isinstance(entity_id, str) or not entity_id:
        logger.warning("entity for rut %s has no id, skipping", rut)
        return 0, since

    tick_started_at = _now_utc_iso()

    try:
        events = await _fetch_events(client, entity_id, since)
    except RateLimitError as exc:
        sleep_for = exc.retry_after if exc.retry_after is not None else DEFAULT_INTERVAL_SECONDS
        logger.warning("rate limited, sleeping %s s", sleep_for)
        await asyncio.sleep(sleep_for)
        return 0, None
    except AuthError:
        raise
    except ValidationError as exc:
        logger.error("validation error polling entity %s (rut=%s): %s", entity_id, rut, exc)
        return 0, None
    except (QuotaError, ServerError, CerberusAPIError) as exc:
        logger.warning("api error polling entity %s (rut=%s): %s", entity_id, rut, exc)
        return 0, None
    except OSError as exc:
        # httpx re-raises low-level network issues as OSError subclasses once
        # the retry budget is exhausted. Skip this entity for this tick.
        logger.warning("network error polling entity %s (rut=%s): %s", entity_id, rut, exc)
        return 0, None

    new_count = 0
    for event in events:
        event_id = event.get("event_id") or event.get("id")
        if not isinstance(event_id, str) or event_id in seen_event_ids:
            continue
        seen_event_ids.add(event_id)
        new_count += 1
        logger.info(
            "new event: entity=%s type=%s published=%s",
            rut,
            event.get("type"),
            event.get("published_at"),
        )

    return new_count, tick_started_at


async def _resolve_portfolio(
    client: AsyncCerberusClient,
    ruts: list[str],
) -> dict[str, dict[str, Any]]:
    """Resolve each RUT to its entity summary, skipping unknown ones."""
    resolved: dict[str, dict[str, Any]] = {}
    for rut in ruts:
        entity = await _resolve_entity(client, rut)
        if entity is not None:
            resolved[rut] = entity
    return resolved


async def _run_loop(
    client: AsyncCerberusClient,
    portfolio: dict[str, dict[str, Any]],
    interval: float,
    stop_event: asyncio.Event,
) -> None:
    """Main polling loop. Exits cleanly when ``stop_event`` is set."""
    seen_events: dict[str, set[str]] = {rut: set() for rut in portfolio}
    last_poll: dict[str, str | None] = dict.fromkeys(portfolio, None)

    while not stop_event.is_set():
        tick_started = time.monotonic()
        new_total = 0

        for rut, entity in portfolio.items():
            new_count, new_since = await _poll_entity(
                client,
                rut,
                entity,
                last_poll[rut],
                seen_events[rut],
            )
            new_total += new_count
            if new_since is not None:
                last_poll[rut] = new_since

        elapsed = time.monotonic() - tick_started
        logger.info(
            "tick: entities=%d new_events=%d elapsed=%.1fs",
            len(portfolio),
            new_total,
            elapsed,
        )

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            continue


def _install_signal_handlers(stop_event: asyncio.Event) -> None:
    """Wire SIGINT/SIGTERM to set the loop's stop event.

    Falls back silently on platforms that don't support
    ``loop.add_signal_handler`` (notably Windows for SIGTERM).
    """
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except (NotImplementedError, RuntimeError):
            # Best-effort: KeyboardInterrupt in amain() is the fallback.
            continue


async def amain(argv: list[str]) -> int:
    """Async entry point.

    Returns a process exit code: ``0`` on clean shutdown, ``2`` on auth
    failure (bad API key — no point retrying), ``64`` on usage errors.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    args = _parse_args(argv)

    api_key = args.api_key or os.environ.get("CERBERUS_API_KEY")
    if not api_key:
        logger.error(
            "no API key provided: pass --api-key or set CERBERUS_API_KEY",
        )
        return EXIT_USAGE

    try:
        ruts = _read_ruts(args.csv, args.max_entities)
    except FileNotFoundError:
        logger.error("csv file not found: %s", args.csv)
        return EXIT_USAGE
    except ValueError as exc:
        logger.error("%s", exc)
        return EXIT_USAGE

    if not ruts:
        logger.error("csv %s contained no RUTs", args.csv)
        return EXIT_USAGE

    logger.info("loaded %d RUTs from %s", len(ruts), args.csv)

    stop_event = asyncio.Event()
    _install_signal_handlers(stop_event)

    try:
        async with AsyncCerberusClient(api_key=api_key, base_url=args.base_url) as client:
            try:
                portfolio = await _resolve_portfolio(client, ruts)
            except AuthError as exc:
                logger.error("authentication failed while resolving portfolio: %s", exc)
                return EXIT_AUTH

            if not portfolio:
                logger.error("no RUTs could be resolved to entities; nothing to poll")
                return EXIT_USAGE

            logger.info(
                "resolved %d/%d entities; starting poll loop (interval=%.1fs)",
                len(portfolio),
                len(ruts),
                args.interval,
            )

            try:
                await _run_loop(client, portfolio, args.interval, stop_event)
            except AuthError as exc:
                logger.error("authentication failed during polling: %s", exc)
                return EXIT_AUTH
    except (asyncio.CancelledError, KeyboardInterrupt):
        logger.info("shutdown")
        return EXIT_OK

    logger.info("shutdown")
    return EXIT_OK


def main() -> int:
    """Synchronous entry point used by ``python -m examples.monitor_portfolio``."""
    try:
        return asyncio.run(amain(sys.argv[1:]))
    except KeyboardInterrupt:
        logger.info("shutdown")
        return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
