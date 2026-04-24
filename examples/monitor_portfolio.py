"""Async portfolio monitor for the Cerberus Compliance API.

Runnable: ``CERBERUS_API_KEY=<your-key> python examples/monitor_portfolio.py``
   (invoked with no flags: prints a single-tick demo against the built-in
   sample portfolio, then exits. Use ``--csv`` + ``--interval`` for a
   long-running poller.)
Tier required: ``professional`` (scope ``kyb:read``).
Expected runtime: ~600 ms for the zero-arg demo.

Reads a CSV file of Chilean tax ids (RUTs) and polls the Cerberus
``/v1/kyb/{rut}`` endpoint every ``--interval`` seconds, surfacing newly-
published ``recent_material_events`` (hechos esenciales) as log lines.

Usage::

    # Zero-arg demo — one tick against the 5-RUT sample portfolio, then exit:
    export CERBERUS_API_KEY=ck_live_...
    python examples/monitor_portfolio.py

    # Full polling mode (Ctrl+C to stop):
    python -m examples.monitor_portfolio --csv portfolio.csv --interval 60

The CSV must have a header row containing a ``rut`` column; extra columns
are ignored. The example calls ``kyb.get(rut)`` on every tick, diffs the
returned ``recent_material_events`` against an in-memory per-RUT seen-set,
and logs only the newly observed events.

v0.2.0 note: the pre-v0.2.0 version of this example hit
``/entities/{id}/material_events``, which turned out never to exist on
the prod API (audit gap G3). The flagship KYB endpoint is the correct
source of truth for ``recent_material_events`` going forward.
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
from typing import Any

from cerberus_compliance import (
    AsyncCerberusClient,
    AuthError,
    CerberusAPIError,
    NotFoundError,
    QuotaError,
    RateLimitError,
    ServerError,
    ValidationError,
)

__all__ = ["amain", "main"]

logger = logging.getLogger("cerberus.monitor")

DEFAULT_INTERVAL_SECONDS = 60.0
DEFAULT_MAX_ENTITIES = 50
EXIT_OK = 0
EXIT_AUTH = 2
EXIT_USAGE = 64

# Baked-in sample portfolio so the example is runnable without a CSV file
# (e.g. by the gate loop in the release workflow).
SAMPLE_PORTFOLIO: tuple[str, ...] = (
    "96.505.760-9",
    "90.320.000-6",
    "99.301.000-6",
    "76.086.428-5",
    "70.002.050-9",
)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse CLI flags into an :class:`argparse.Namespace`.

    ``--csv`` is intentionally optional: when omitted the example runs a
    single tick against :data:`SAMPLE_PORTFOLIO` and exits. That makes the
    script friendly to the release-gate loop ("run every example with no
    args against prod") while still supporting the production use case
    (``--csv portfolio.csv --interval 60``).
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
        default=None,
        help=(
            "Path to a CSV file with a header row containing a 'rut' column. "
            "Omit to run a single tick against the built-in sample portfolio."
        ),
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
    parser.add_argument(
        "--ticks",
        type=int,
        default=None,
        help=(
            "Run this many ticks and exit. Defaults to 1 when --csv is omitted "
            "(demo mode) and to an infinite loop when --csv is set."
        ),
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


async def _fetch_events(
    client: AsyncCerberusClient,
    rut: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Fetch the KYB profile for ``rut`` and return ``(profile, events)``.

    ``events`` is the ``recent_material_events`` list, filtered down to
    ``dict`` entries so the caller can blindly index into each row.
    """
    profile = await client.kyb.get(rut, include=["material_events"])
    raw = profile.get("recent_material_events")
    if not isinstance(raw, list):
        return profile, []
    return profile, [event for event in raw if isinstance(event, dict)]


async def _poll_rut(
    client: AsyncCerberusClient,
    rut: str,
    seen_event_ids: set[str],
) -> int:
    """Poll one RUT. Returns the number of *new* events observed this tick."""
    try:
        profile, events = await _fetch_events(client, rut)
    except NotFoundError:
        logger.warning("rut %s not found in Cerberus directory; skipping", rut)
        return 0
    except RateLimitError as exc:
        sleep_for = exc.retry_after if exc.retry_after is not None else DEFAULT_INTERVAL_SECONDS
        logger.warning("rate limited for rut %s, sleeping %.1fs", rut, sleep_for)
        await asyncio.sleep(sleep_for)
        return 0
    except AuthError:
        raise
    except ValidationError as exc:
        logger.error("validation error for rut %s: %s", rut, exc)
        return 0
    except (QuotaError, ServerError, CerberusAPIError) as exc:
        logger.warning("api error polling rut %s: %s", rut, exc)
        return 0
    except OSError as exc:
        logger.warning("network error polling rut %s: %s", rut, exc)
        return 0

    legal_name = profile.get("legal_name") or rut
    new_count = 0
    for event in events:
        event_id = event.get("id")
        if not isinstance(event_id, str) or event_id in seen_event_ids:
            continue
        seen_event_ids.add(event_id)
        new_count += 1
        logger.info(
            "new hecho esencial: entity=%s (rut=%s) published=%s asunto=%s",
            legal_name,
            rut,
            event.get("publicacion_at"),
            event.get("asunto"),
        )
    return new_count


async def _run_loop(
    client: AsyncCerberusClient,
    ruts: list[str],
    *,
    interval: float,
    max_ticks: int | None,
    stop_event: asyncio.Event,
) -> None:
    """Main polling loop. Exits cleanly on ``stop_event`` or ``max_ticks``.

    ``max_ticks=None`` means "run forever"; ``max_ticks=1`` is the demo
    mode used by the zero-arg entry point.
    """
    seen_events: dict[str, set[str]] = {rut: set() for rut in ruts}
    ticks_done = 0

    while not stop_event.is_set():
        tick_started = time.monotonic()
        new_total = 0

        for rut in ruts:
            new_total += await _poll_rut(client, rut, seen_events[rut])

        elapsed = time.monotonic() - tick_started
        ticks_done += 1
        logger.info(
            "tick: ruts=%d new_events=%d elapsed=%.2fs",
            len(ruts),
            new_total,
            elapsed,
        )

        if max_ticks is not None and ticks_done >= max_ticks:
            return

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
            continue


async def amain(argv: list[str]) -> int:
    """Async entry point.

    Returns a process exit code: ``0`` on clean shutdown, ``2`` on auth
    failure, ``64`` on usage errors.
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

    if args.csv is None:
        # Zero-arg demo path — single tick against the baked-in sample
        # portfolio so the example finishes in under 2 s for the release gate.
        logger.info(
            "no --csv provided; running single-tick demo against %d sample RUTs",
            len(SAMPLE_PORTFOLIO),
        )
        ruts = list(SAMPLE_PORTFOLIO)
        max_ticks = args.ticks if args.ticks is not None else 1
    else:
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
        max_ticks = args.ticks  # None = forever

    stop_event = asyncio.Event()
    _install_signal_handlers(stop_event)

    try:
        async with AsyncCerberusClient(api_key=api_key, base_url=args.base_url) as client:
            try:
                await _run_loop(
                    client,
                    ruts,
                    interval=args.interval,
                    max_ticks=max_ticks,
                    stop_event=stop_event,
                )
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
