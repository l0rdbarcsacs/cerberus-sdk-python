---
title: "Pagination"
description: "Cursor pagination conventions and the SDK's iter_all helper."
---

# Pagination

All Cerberus list endpoints (`/entities`, `/material_events`, `/sanctions`, …) use
**cursor pagination** with a uniform envelope. The SDK exposes both a manual-loop
pattern and a lazy `iter_all` helper so you can pick the ergonomics that fit your
call site.

## Envelope format

Every list response looks like this:

```json
{
  "data": [
    { "id": "ent_01HW...", "legal_name": "ACME SpA", "rut": "76.086.428-5" },
    { "id": "ent_01HX...", "legal_name": "BETA SpA", "rut": "77.123.456-7" }
  ],
  "next": "eyJhZnRlciI6IjIwMjYtMDQtMjNUMTk6MDA6MDBaIn0"
}
```

- `data` — the page of results (always a JSON array; may be empty).
- `next` — an **opaque** cursor. Pass it back as `?cursor=<next>` on the follow-up
  request to retrieve the next page. When there are no more results, `next` is either
  `null`, omitted entirely, or an empty string.

Some endpoints also include a `page` object with metadata (page size, total hints).
Treat those fields as best-effort — production code should rely on `data` and `next`
only.

## Manual pagination

With only `_request`, the loop is short and explicit. This is the shape you use today
in v0.1.0-rc1:

```python
from typing import Any
from cerberus_compliance import CerberusClient

def fetch_all_material_events(client: CerberusClient, since: str) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    params: dict[str, Any] = {"limit": 50, "since": since}

    while True:
        response = client._request("GET", "/material_events", params=params)
        collected.extend(response.get("data", []))

        next_token = response.get("next")
        if not isinstance(next_token, str) or not next_token:
            break
        # Chase the cursor. Keep the original filters — some endpoints require them.
        params = {"cursor": next_token}

    return collected
```

Notes:

- Check `isinstance(next_token, str) and next_token` — the SDK treats `None`, missing
  keys, and empty strings identically, but your code should too.
- Keep page size modest (`limit=50` to `limit=200` are typical) to stay well within
  the response-size budget.

## With `iter_all`

Once resource namespaces ship in **v0.1.0 GA**, idiomatic iteration becomes a single
`for` loop:

```python
from cerberus_compliance import CerberusClient

with CerberusClient() as client:
    last_seen = "2026-04-23T00:00:00Z"
    for event in client.material_events.iter_all(since=last_seen):
        process(event)
```

Features:

- **Lazy** — one HTTP request per page. Memory usage is bounded by `limit`, not by
  the total result-set size. You can walk millions of events without OOMing.
- **Transparent cursor handling** — you never touch the `next` token yourself.
- **Filter forwarding** — keyword arguments (`since=`, `active=`, `category=`, etc.)
  are forwarded on every page request, exactly as the underlying endpoint expects.
- **Early exit** is fine. Break out of the loop whenever you have enough results; the
  SDK does not prefetch additional pages.

## Async iteration

The async client exposes the same helper as an **async iterator**:

```python
import asyncio
from cerberus_compliance import AsyncCerberusClient

async def tail_events(since: str) -> None:
    async with AsyncCerberusClient() as client:
        async for event in client.material_events.iter_all(since=since):
            await handle(event)

asyncio.run(tail_events("2026-04-23T00:00:00Z"))
```

Under the hood each page is a single `await` on `_request`, so back-pressure (via
`httpx`'s connection pool) works exactly as you would expect.

## Cursor stability

Cursors are **server-issued** and opaque. Two guarantees worth knowing:

1. A cursor is specific to the filter set that produced it. Do not reuse a cursor
   from one query with a different `since=` or `active=` filter — the server may
   reject it or return results that no longer match.
2. Cursors may **expire after roughly 24 hours**. Callers that pause pagination
   overnight and resume the next day should drop the cursor and re-issue the query
   with a `since=<timestamp>` filter instead. This is also the right pattern for
   incremental sync jobs: persist the last processed timestamp, not the last cursor.

## Gotchas

- **Do not construct cursors by hand.** They are opaque tokens (typically
  base64-encoded JSON, but the scheme may change). Always pass back the exact string
  the server returned.
- **Do not mix filters across pages.** Once you have a cursor, the only parameter you
  need is `cursor=<token>`; the server already remembers the filters.
- **Empty `data` with a non-null `next` is legal** (rare, but valid). The SDK's
  `iter_all` handles this correctly — your manual loop should too.
- **The SDK wraps non-object responses defensively.** If the server returns a bare
  JSON array at the top level, `_request` wraps it as `{"data": [...]}` with no
  `next`. Treat it the same as a single-page result.
