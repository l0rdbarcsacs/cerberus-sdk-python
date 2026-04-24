# cerberus-compliance

Official Python SDK for the **Cerberus Compliance API** — a Chile-specific RegTech
platform that consolidates KYB (Know Your Business), AML/sanctions screening,
CMF regulatory feeds, and ``Registro Público de Servicios Financieros`` (RPSF)
lookups into a single typed client.

[![PyPI version](https://img.shields.io/pypi/v/cerberus-compliance.svg)](https://pypi.org/project/cerberus-compliance)
[![Python versions](https://img.shields.io/pypi/pyversions/cerberus-compliance.svg)](https://pypi.org/project/cerberus-compliance)
[![CI](https://img.shields.io/github/actions/workflow/status/l0rdbarcsacs/cerberus-sdk-python/ci.yml?branch=main)](https://github.com/l0rdbarcsacs/cerberus-sdk-python/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)

---

## What problem does it solve?

Chilean compliance teams today glue together half a dozen data sources — CMF
sanctions publications, the RPSF registry, ``hechos esenciales`` filings,
Ley 21.521 / Ley 21.719 / NCG 380/461/514 normativa, LEI lookups, sanctions
watchlists (OFAC / UN / EU) — and build bespoke risk scores on top. The
Cerberus Compliance API unifies all of that behind one REST surface keyed
on the Chilean RUT; this SDK is the typed Python client for that surface:

- One flagship aggregate endpoint — ``GET /kyb/{rut}`` — that returns the
  consolidated entity dossier (directors, sanctions, RPSF inscriptions,
  recent material events, ownership chain, risk score).
- Narrow sub-resources for callers that want one signal at a time
  (``entities``, ``sanctions``, ``regulations``, ``rpsf``, ``normativa``,
  ``persons``).
- A single exception hierarchy carrying the RFC 7807 problem document and
  the ``X-Request-Id`` header, so support tickets are actionable.
- Cursor-pagination helpers (``iter_all``) that lazily chase the
  ``next_cursor`` token.
- Synchronous (``CerberusClient``) and asynchronous (``AsyncCerberusClient``)
  clients sharing an identical API, retry policy, and exception hierarchy.
- ``py.typed`` marker — strict ``mypy`` compatible.

## Install

```bash
pip install cerberus-compliance
# or
uv add cerberus-compliance
```

Requires **Python 3.10+**. Core dependencies: ``httpx>=0.27,<1.0``,
``pydantic>=2.6,<3.0``.

## Configure

```python
import os
from cerberus_compliance import CerberusClient

# Reads CERBERUS_API_KEY from the environment.
client = CerberusClient()

# Or pass the key explicitly (useful for dependency-injected test harnesses).
client = CerberusClient(api_key=os.environ["CERBERUS_API_KEY"])

# Staging / local dev: override the base URL.
client = CerberusClient(base_url="https://staging-compliance.cerberus.cl/v1")
```

The default base URL is `https://compliance.cerberus.cl/v1`. The API-key
resolution order is: `api_key=` argument → `CERBERUS_API_KEY` env var →
`ValueError` at construction time. See [`docs/auth.md`](./docs/auth.md) for
rotation and secret-hygiene guidance.

## Resources at a glance

Every resource has a sync (`client.<resource>`) and async
(`async_client.<resource>`) mirror; only the `await` differs.

| Resource              | Endpoint(s)                                                          | Key methods                                                                   |
|-----------------------|----------------------------------------------------------------------|-------------------------------------------------------------------------------|
| `client.kyb`          | `GET /kyb/{rut}`                                                     | `get(rut, *, as_of=None, include=[...])`                                      |
| `client.entities`     | `/entities`, `/entities/{id}`, `/entities/by-rut/{rut}`              | `list`, `get`, `by_rut`, `ownership`, `directors`, `sanctions`, `regulations`, `iter_all` |
| `client.sanctions`    | `/sanctions`, `/sanctions/{id}`                                      | `list(*, target_id, source, active, limit)`, `get`, `iter_all`                |
| `client.regulations`  | `/regulations`, `/regulations/search`                                | `list(*, entity_id, framework, limit)`, `get`, `search(q, **params)`, `iter_all` |
| `client.rpsf`         | `/rpsf`, `/rpsf/by-entity/{id}`, `/rpsf/by-servicio/{s}`             | `list(**filters)`, `get`, `by_entity`, `by_servicio`, `iter_all`              |
| `client.normativa`    | `/normativa`, `/normativa/{id}/mercado`                              | `list(**filters)`, `get`, `mercado`, `iter_all`                               |
| `client.persons`      | `/persons/{rut}/regulatory-profile`                                  | `regulatory_profile(rut)`                                                     |

Two quick examples (drop in an API key and run):

```python
# Sync.
from cerberus_compliance import CerberusClient

with CerberusClient() as client:
    profile = client.kyb.get("96.505.760-9", include=["directors", "lei", "sanctions"])
    print(profile["legal_name"], "| risk", profile["risk_score"])
```

```python
# Async.
import asyncio
from cerberus_compliance import AsyncCerberusClient

async def main() -> None:
    async with AsyncCerberusClient() as client:
        profile = await client.kyb.get("96.505.760-9", include=["directors"])
        print(profile["legal_name"], "| risk", profile["risk_score"])

asyncio.run(main())
```

## Flagship: KYB Express

`client.kyb.get(rut, *, as_of=..., include=[...])` is a single round-trip
against `GET /v1/kyb/{rut}` that returns a consolidated entity dossier —
the right default for dashboards, analyst views, and KYB gating flows.

```python
from datetime import date
from cerberus_compliance import CerberusClient

with CerberusClient() as client:
    profile = client.kyb.get(
        "96.505.760-9",                  # Falabella SA
        as_of=date(2026, 4, 1),          # point-in-time snapshot
        include=["directors", "lei", "sanctions"],
    )
```

A real response against prod (trimmed):

```jsonc
{
  "rut": "96.505.760-9",
  "rut_canonical": "96505760-9",
  "legal_name": "Falabella SA",
  "fantasy_name": "Falabella",
  "entity_kind": "sociedad_anonima_abierta",
  "status": "activo",
  "inscription_date": "1937-06-04",
  "lei": "5493002Q8WJ1QCQ5V912",
  "risk_score": 0,
  "risk_factors": [],
  "directors_current": [
    {
      "persona_rut": "11.111.111-1",
      "nombre": "Carlos Heller Solari",
      "cargo": "presidente",
      "fecha_inicio": "2020-01-01"
    }
    // ... 2 more
  ],
  "sanctions": {
    "active_count": 0,
    "historical_count": 0,
    "last_sanction_at": null,
    "last_sanction_summary": null
  },
  "rpsf_inscriptions": [],
  "recent_material_events": [
    {
      "id": "ba0bf3fe-f2e8-4e48-b2b6-56038dfaa193",
      "publicacion_at": "2026-04-04T00:00:00Z",
      "asunto": "Hecho esencial — cambio gerente general rutinario"
    }
  ],
  "ownership_chain": { /* ... */ },
  "as_of": "2026-04-24",
  "request_id": "req_...",
  "cache_status": "live"
}
```

Notes:

- `as_of` is serialised as an ISO-8601 date (`YYYY-MM-DD`). `None` asks the
  server for the live view.
- `include` preserves caller order on the wire; requested fields are
  guaranteed to be present (even when empty).
- `sanctions` in the KYB response is a *summary* object. To retrieve the
  full sanction records, use `client.entities.sanctions(entity_id)` (which
  hits `/v1/sanctions/by-entity/{id}`), or iterate `client.sanctions`.
- See [`examples/kyb_quickstart.py`](./examples/kyb_quickstart.py) for a
  full CLI that renders this payload with `rich`.

## Authentication, tiers, scopes, rate limits

- **Bearer token.** Every request carries `Authorization: Bearer <api_key>`
  plus `User-Agent: cerberus-compliance/<version>`.
- **Tiers.** `starter`, `professional`, `enterprise`. KYB, RPSF, normativa,
  and regulations search require at least `professional`. Webhooks require
  `enterprise`. Tier and scopes are surfaced by `GET /v1/keys/me` (also
  visible on the developer portal).
- **Scopes.** Key-level ACLs: `kyb:read`, `entities:read`, `sanctions:read`,
  `rpsf:read`, `regulations:read`, `normativa:read`, `persons:read`.
  Missing-scope calls return `403 Forbidden` as `AuthError`.
- **Rate limits.** Default `120 req/min` per key; bursts up to `240`.
  `429 Too Many Requests` responses carry a `Retry-After` header the SDK
  parses automatically into `RateLimitError.retry_after` (seconds).

See [`docs/auth.md`](./docs/auth.md) for key rotation, staging keys, and
client-side rate-limiting patterns.

## Error handling

Every non-2xx response raises a subclass of `CerberusAPIError`. Each
exception carries:

- `.status` — HTTP status code.
- `.problem` — the parsed RFC 7807 body as a `dict`.
- `.request_id` — the `X-Request-Id` header (include it in support tickets).
- `.title`, `.detail`, `.type`, `.instance` — RFC 7807 convenience
  properties, with safe fallbacks when the server omits a field.

```python
from cerberus_compliance import (
    CerberusClient,
    AuthError,         # 401 / 403 — bad key, missing scope
    NotFoundError,     # 404 — unknown entity / sanction / normativa id
    ValidationError,   # 422 — bad RUT, bad query params, has .errors list
    QuotaError,        # 402 — tier quota exhausted
    RateLimitError,    # 429 — carries .retry_after (seconds)
    ServerError,       # 5xx — retried automatically by default
    CerberusAPIError,  # parent; catch-all
)

client = CerberusClient()
try:
    profile = client.kyb.get("00.000.000-0")
except NotFoundError as exc:
    print(f"no entity: {exc.detail} [request_id={exc.request_id}]")
except ValidationError as exc:
    for field_err in exc.errors:
        print(f"bad field: {field_err}")
except RateLimitError as exc:
    print(f"slow down: retry after {exc.retry_after:.1f}s")
except AuthError:
    raise  # bad key — no point retrying
except CerberusAPIError as exc:
    print(f"api error: {exc.status} {exc.title}")
```

Transient failures (`429`, `500`, `502`, `503`, `504`, and transport errors)
are retried automatically with exponential backoff + jitter. Tune the
policy per client:

```python
from cerberus_compliance import CerberusClient
from cerberus_compliance.retry import RetryConfig

client = CerberusClient(retry=RetryConfig(max_attempts=5, base_delay_ms=500))
```

See [`examples/error_handling.py`](./examples/error_handling.py) for a
runnable walk-through of every exception, and
[`docs/errors.md`](./docs/errors.md) for the full RFC 7807 recipe sheet.

## Cursor pagination

All list endpoints return a cursor envelope:

```jsonc
{ "items": [ /* ... */ ], "next_cursor": "<opaque-token>" | null, "limit": 50 }
```

Every listable resource exposes an `iter_all(**filters)` helper that chases
`next_cursor` lazily — a plain Python generator (sync) or async generator
(async), so you never hold a full result set in memory:

```python
from itertools import islice
from cerberus_compliance import CerberusClient

with CerberusClient() as client:
    # First 20 sanctions matching a source filter.
    first_20 = list(islice(client.sanctions.iter_all(source="CMF"), 20))
```

Async usage:

```python
import asyncio
from cerberus_compliance import AsyncCerberusClient

async def main() -> None:
    async with AsyncCerberusClient() as client:
        count = 0
        async for record in client.rpsf.iter_all(is_active=True):
            count += 1
            if count >= 50:
                break

asyncio.run(main())
```

See [`examples/cursor_pagination.py`](./examples/cursor_pagination.py) for
three idioms (list, `islice`, streaming) and
[`docs/pagination.md`](./docs/pagination.md) for the manual-loop pattern.

## Examples

Every example below is runnable against prod with
`CERBERUS_API_KEY=<your-key> python examples/<name>.py`.

| File                                                                       | What it shows                                                            |
|----------------------------------------------------------------------------|--------------------------------------------------------------------------|
| [`kyb_quickstart.py`](./examples/kyb_quickstart.py)                        | Flagship: `client.kyb.get(...)` with `as_of` + `include`; `rich` render. |
| [`entities_lookup.py`](./examples/entities_lookup.py)                      | `entities.by_rut` → `get` → `directors` / `ownership` / `sanctions`.     |
| [`sanctions_browse.py`](./examples/sanctions_browse.py)                    | `sanctions.list` + detail + per-entity via `entities.sanctions`.         |
| [`regulations_search.py`](./examples/regulations_search.py)                | `regulations.list`, `get`, `search(q="sanciones")`.                      |
| [`rpsf_explore.py`](./examples/rpsf_explore.py)                            | `rpsf.list`, `by_entity`, `by_servicio("plataforma_financiamiento_colectivo")`. |
| [`normativa_explore.py`](./examples/normativa_explore.py)                  | `normativa.list`, `get`, `mercado(id)`.                                  |
| [`persons_profile.py`](./examples/persons_profile.py)                      | `persons.regulatory_profile("11.111.111-1")` (Carlos Heller — PEP-lite).|
| [`async_concurrent_lookups.py`](./examples/async_concurrent_lookups.py)    | `asyncio.gather` over a 5-RUT portfolio with `AsyncCerberusClient`.      |
| [`error_handling.py`](./examples/error_handling.py)                        | Each exception in the hierarchy with a real trigger.                     |
| [`cursor_pagination.py`](./examples/cursor_pagination.py)                  | `iter_all` — list, `islice(..., N)`, streaming loop.                     |
| [`monitor_portfolio.py`](./examples/monitor_portfolio.py)                  | Async polling CSV → `kyb.get` diff of new `recent_material_events`.      |
| [`webhook_handler.py`](./examples/webhook_handler.py)                      | FastAPI receiver with HMAC-SHA256 signature + replay protection.         |
| [`notebooks/01-kyb-quickstart.ipynb`](./examples/notebooks/01-kyb-quickstart.ipynb) | Narrated Jupyter quickstart for analysts.                        |

## Deprecations (v0.2.0)

Three surfaces shipped before the v0.2.0 audit and turned out to target
fictional endpoints. They remain as compatibility shims that **emit a
`DeprecationWarning` on first call** and raise `NotImplementedError` with
a pointer to the replacement. All three are **scheduled for removal in
v0.3.0**.

| Deprecated                                                    | Migrate to                                                                 |
|---------------------------------------------------------------|----------------------------------------------------------------------------|
| `client.persons.list()` / `client.persons.get()`              | `client.persons.regulatory_profile(rut)` or `client.entities.directors(entity_id)` |
| `client.registries.list()` / `.get()` / `.iter_all()`         | `client.entities.by_rut(rut)` (and `client.rpsf` for CMF registry records) |
| `client.material_events.list()` / `.get()` / `.iter_all()`    | `client.kyb.get(rut)["recent_material_events"]` or `entities.get(id)`      |

`client.registries.lookup_rut(rut)` still works (it emits a warning and
forwards to `entities.by_rut`) — it is the single shim we kept live so
in-flight integrations do not break.

## Status / roadmap

`v0.2.0` tracks the real production API at `https://compliance.cerberus.cl/v1`.
Typed resource coverage:

| Surface                                                                  | Status              |
|--------------------------------------------------------------------------|---------------------|
| `CerberusClient` / `AsyncCerberusClient`                                 | Shipped in v0.2.0   |
| `CerberusAPIError` hierarchy (incl. `NotFoundError`)                     | Shipped in v0.2.0   |
| `RetryConfig`, `ApiKeyAuth`                                              | Shipped in v0.2.0   |
| `client.kyb.get(rut, *, as_of, include)`                                 | Shipped in v0.2.0   |
| `client.entities` (`list` / `get` / `by_rut` / `ownership` / `sanctions` / `directors` / `regulations` / `iter_all`) | Shipped in v0.2.0 |
| `client.persons.regulatory_profile(rut)`                                 | Shipped in v0.2.0   |
| `client.sanctions`, `client.regulations` (+ `search`)                    | Shipped in v0.2.0   |
| `client.rpsf` (CMF Registro Público de Servicios Financieros)            | Shipped in v0.2.0   |
| `client.normativa` (regulatory-text catalogue + `mercado` mapping)       | Shipped in v0.2.0   |
| `client.registries`, `client.material_events`, `persons.list/get`        | **Deprecated** in v0.2.0; removed in v0.3.0 |
| Webhook signature helper (SDK-side)                                      | Planned v0.3.0      |

For endpoints not yet wrapped by a typed resource, the low-level
`client._request(method, path, *, params=..., json=...)` transport is
available and returns the parsed JSON body as a `dict`.

## Contributing

```bash
git clone https://github.com/l0rdbarcsacs/cerberus-sdk-python.git
cd cerberus-sdk-python
pip install -e ".[dev]"
pytest -q
mypy --strict cerberus_compliance/
ruff check .
ruff format --check .
```

Changelog: [`CHANGELOG.md`](./CHANGELOG.md).
Issues: <https://github.com/l0rdbarcsacs/cerberus-sdk-python/issues>.

## Links

- PyPI: <https://pypi.org/project/cerberus-compliance>
- Repository: <https://github.com/l0rdbarcsacs/cerberus-sdk-python>
- Developer portal: <https://developers.cerberus.cl>
- Changelog: [`CHANGELOG.md`](./CHANGELOG.md)

## License

MIT — see [LICENSE](./LICENSE).
