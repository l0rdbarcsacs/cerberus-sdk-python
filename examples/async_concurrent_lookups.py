"""Concurrent KYB lookups across a 5-RUT portfolio with AsyncCerberusClient.

Runnable: ``CERBERUS_API_KEY=<your-key> python examples/async_concurrent_lookups.py``
Tier required: ``professional`` (scopes ``kyb:read``, ``entities:read``).
Expected runtime: ~600 ms (5 lookups in parallel vs. ~2 s sequentially).

``AsyncCerberusClient`` shares the same surface as ``CerberusClient`` with
``await`` in front. Fanning out to ``asyncio.gather`` over the async
client is the idiomatic way to resolve a portfolio of RUTs in parallel
while keeping a single connection pool.

The example picks five real production seed RUTs:

- ``96.505.760-9`` — Falabella SA (IPSA issuer)
- ``90.320.000-6`` — Enel Chile SA (has a historical CMF sanction)
- ``99.301.000-6`` — Consorcio Nacional de Seguros SA (insurance)
- ``76.086.428-5`` — Fintual Crowd SpA (fintech / crowdfunding)
- ``70.002.050-9`` — Coopeuch Cooperativa de Ahorro y Crédito

Each task uses ``return_exceptions=True`` so a single 404 or rate-limit
does not cancel sibling tasks — a common pitfall when new callers meet
``asyncio.gather``.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time
from typing import Any

from cerberus_compliance import (
    AsyncCerberusClient,
    CerberusAPIError,
    NotFoundError,
    RateLimitError,
)

logger = logging.getLogger("cerberus_compliance.examples.async_concurrent_lookups")

PORTFOLIO: tuple[str, ...] = (
    "96.505.760-9",
    "90.320.000-6",
    "99.301.000-6",
    "76.086.428-5",
    "70.002.050-9",
)


def _fmt(value: Any) -> str:
    """Render ``None`` as ``'-'`` and coerce anything else to ``str``."""
    return "-" if value is None else str(value)


async def _fetch_one(client: AsyncCerberusClient, rut: str) -> dict[str, Any]:
    """Fetch one KYB profile. Errors propagate to ``asyncio.gather``."""
    return await client.kyb.get(rut, include=["directors", "lei", "sanctions"])


async def amain() -> int:
    """Async entry point — return a POSIX-style exit code."""
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    try:
        client = AsyncCerberusClient()
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    started_at = time.monotonic()
    async with client:
        results = await asyncio.gather(
            *(_fetch_one(client, rut) for rut in PORTFOLIO),
            return_exceptions=True,
        )
    elapsed = time.monotonic() - started_at

    print(f"\nResolved {len(PORTFOLIO)} RUTs in {elapsed * 1000:.0f} ms\n")
    print(f"{'RUT':18s} | {'legal_name':40s} | risk | dirs | active_sanc")
    print("-" * 84)
    for rut, result in zip(PORTFOLIO, results, strict=True):
        if isinstance(result, NotFoundError):
            print(f"{rut:18s} | {'(not found)':40s} | -    | -    | -")
            continue
        if isinstance(result, RateLimitError):
            retry_after = result.retry_after or 0.0
            print(f"{rut:18s} | (rate limited, retry after {retry_after:.1f}s)")
            continue
        if isinstance(result, CerberusAPIError):
            print(f"{rut:18s} | (api error: {result.status} {result.title})")
            continue
        if isinstance(result, Exception):
            print(f"{rut:18s} | (unexpected error: {result!r})")
            continue

        directors = result.get("directors_current") or []
        sanctions_summary = result.get("sanctions") or {}
        active_sanc = (
            sanctions_summary.get("active_count") if isinstance(sanctions_summary, dict) else None
        )
        print(
            f"{rut:18s} | {_fmt(result.get('legal_name'))[:40]:40s} "
            f"| {_fmt(result.get('risk_score'))[:4]:4s} "
            f"| {len(directors):4d} "
            f"| {_fmt(active_sanc)}"
        )

    return 0


def main() -> int:
    """Sync entry point used by ``python examples/async_concurrent_lookups.py``."""
    try:
        return asyncio.run(amain())
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
