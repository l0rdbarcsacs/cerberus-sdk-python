# cerberus-compliance

Official Python SDK for the **Cerberus Compliance API** — a Chile RegTech platform for
KYB (Know Your Business), AML/sanctions screening, CMF material-event feeds, and
regulatory-registry lookups.

[![PyPI version](https://img.shields.io/pypi/v/cerberus-compliance.svg)](https://pypi.org/project/cerberus-compliance)
[![Python versions](https://img.shields.io/pypi/pyversions/cerberus-compliance.svg)](https://pypi.org/project/cerberus-compliance)
[![CI](https://img.shields.io/github/actions/workflow/status/l0rdbarcsacs/cerberus-sdk-python/ci.yml?branch=main)](https://github.com/l0rdbarcsacs/cerberus-sdk-python/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)

The SDK wraps the Cerberus REST API with a small, typed, production-shaped surface:

- Synchronous (`CerberusClient`) and asynchronous (`AsyncCerberusClient`) clients sharing
  the same API and keyword arguments.
- Typed, granular exception hierarchy (`AuthError`, `ValidationError`, `QuotaError`,
  `RateLimitError`, `ServerError`) carrying the RFC 7807 problem document and the
  `X-Request-Id` header.
- Configurable retries with exponential backoff, jitter, and `Retry-After` honoring.
- Cursor-pagination helpers (`iter_all`) that transparently chase the `next` token.
- Bearer API-key auth via the `CERBERUS_API_KEY` environment variable by default.
- `py.typed` marker — strict `mypy` compatible.

## Install

```bash
pip install cerberus-compliance
```

```bash
uv add cerberus-compliance
```

Requires **Python 3.10+**. Core dependencies: `httpx>=0.27,<1.0`, `pydantic>=2.6,<3.0`.

## 30-second quickstart

```python
import os
from datetime import date
from cerberus_compliance import CerberusClient

with CerberusClient(api_key=os.environ["CERBERUS_API_KEY"]) as client:
    profile = client.kyb.get(
        "96.505.760-9",
        as_of=date(2024, 1, 1),
        include=["directors", "lei", "sanctions"],
    )
    print(profile["legal_name"], profile["risk_score"])
```

`client.kyb.get(rut, *, as_of=..., include=[...])` is the flagship aggregate endpoint —
one round-trip returns a consolidated entity profile with optional dimensions embedded.

The constructor reads `CERBERUS_API_KEY` from the environment when `api_key=` is omitted,
so in typical deployments you can write `CerberusClient()` with no arguments. The default
base URL is `https://compliance.cerberus.cl/v1`.

## Authentication

The SDK authenticates with a bearer API key. Resolution order:

1. `api_key=` constructor argument.
2. `CERBERUS_API_KEY` environment variable.
3. Otherwise raise `ValueError`.

```python
from cerberus_compliance import CerberusClient

client = CerberusClient()                       # reads CERBERUS_API_KEY
client = CerberusClient(api_key="ck_live_...")  # explicit override
```

See [`docs/auth.md`](./docs/auth.md) for key rotation, custom base URLs, and secret
hygiene.

## Retries

Every transient failure (HTTP 429, 500, 502, 503, 504 and transport errors) is retried
with exponential backoff + jitter. Defaults:

```python
RetryConfig(max_attempts=3, base_delay_ms=200, max_delay_ms=10_000,
            retry_on=(429, 500, 502, 503, 504), jitter=True)
```

Customize per client:

```python
from cerberus_compliance import CerberusClient
from cerberus_compliance.retry import RetryConfig

client = CerberusClient(retry=RetryConfig(max_attempts=5, base_delay_ms=500))
```

When the retry budget is exhausted the original `CerberusAPIError` (or transport error)
is raised to the caller.

## Errors

All non-2xx responses raise a subclass of `CerberusAPIError`. Each exception carries
`.status`, `.problem` (the RFC 7807 body as a `dict`), `.request_id`, and convenience
`.title` / `.detail` / `.type` / `.instance` properties. The hierarchy is:
`AuthError` (401/403), `QuotaError` (402), `NotFoundError` (404),
`ValidationError` (422, with `.errors`), `RateLimitError` (429, with `.retry_after`),
`ServerError` (5xx).

See [`docs/errors.md`](./docs/errors.md) for recipes and support-ticket guidance.

## Async

```python
import asyncio
from cerberus_compliance import AsyncCerberusClient

async def main() -> None:
    async with AsyncCerberusClient() as client:
        profile = await client.kyb.get("96.505.760-9", include=["directors"])
        print(profile["legal_name"], profile["risk_score"])

asyncio.run(main())
```

`AsyncCerberusClient` mirrors the sync client 1:1 — same constructor arguments, same
retry policy, same exception hierarchy.

## Pagination

All list endpoints return a `{"data": [...], "next": "<cursor>" | null}` envelope.
The SDK ships an `iter_all` helper on every list resource that chases cursors lazily,
so you never have to hold a full result set in memory. See
[`docs/pagination.md`](./docs/pagination.md) for the manual-loop pattern and the
`iter_all` API.

## Examples

- [`examples/kyb_quickstart.py`](./examples/kyb_quickstart.py) — CLI: resolve an entity
  by RUT, then print its recent facts, sanctions, directors, and regulatory profile.
- [`examples/monitor_portfolio.py`](./examples/monitor_portfolio.py) — async polling
  over a CSV of RUTs, logs new material events on each tick with graceful shutdown.
- [`examples/webhook_handler.py`](./examples/webhook_handler.py) — FastAPI receiver
  with HMAC-SHA256 signature verification and replay protection.
- [`examples/notebooks/01-kyb-quickstart.ipynb`](./examples/notebooks/01-kyb-quickstart.ipynb)
  — narrated Jupyter version of the quickstart, ideal for analyst workflows.

## Status / roadmap

`v0.2.0` tracks the real prod API at `https://compliance.cerberus.cl/v1`. Typed
resource coverage:

| Surface                                                                  | Status             |
|--------------------------------------------------------------------------|--------------------|
| `CerberusClient` / `AsyncCerberusClient`                                 | Shipped in v0.2.0  |
| `CerberusAPIError` hierarchy (incl. `NotFoundError`)                     | Shipped in v0.2.0  |
| `RetryConfig`, `ApiKeyAuth`                                              | Shipped in v0.2.0  |
| `client.kyb.get(rut, *, as_of, include)` — flagship aggregate            | Shipped in v0.2.0  |
| `client.entities` (`list` / `get` / `by_rut` / `ownership` / `sanctions` / `material_events` / `directors` / `regulations` / `iter_all`) | Shipped in v0.2.0  |
| `client.persons` (`list` / `get` / `regulatory_profile` / `iter_all`)    | Shipped in v0.2.0  |
| `client.sanctions`, `client.regulations` (+ `search`)                    | Shipped in v0.2.0  |
| `client.rpsf` (CMF Registro Público de Servicios Financieros)            | Shipped in v0.2.0  |
| `client.normativa` (regulatory-text catalogue + `mercado` mapping)       | Shipped in v0.2.0  |
| `client.registries`, `client.material_events`                            | **Deprecated** in v0.2.0; removed in v0.3.0 |
| Webhook signature helper (SDK-side)                                      | Planned v0.3.0     |

For endpoints not yet wrapped by a typed resource you can still call the low-level
`client._request(method, path, *, params=..., json=...)` transport, which returns
the parsed JSON body as a `dict`.

## Contributing

```bash
git clone https://github.com/l0rdbarcsacs/cerberus-sdk-python.git
cd cerberus-sdk-python
pip install -e ".[dev]"
pytest -q
```

Changelog: [`CHANGELOG.md`](./CHANGELOG.md).
Report issues at <https://github.com/l0rdbarcsacs/cerberus-sdk-python/issues>.

## Links

- PyPI: <https://pypi.org/project/cerberus-compliance>
- Repository: <https://github.com/l0rdbarcsacs/cerberus-sdk-python>
- Developer portal: <https://developers.cerberus.cl>
- Changelog: [`CHANGELOG.md`](./CHANGELOG.md)

## License

MIT — see [LICENSE](./LICENSE).
