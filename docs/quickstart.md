---
title: "Quickstart"
description: "Install the SDK, authenticate, and make your first call in under 60 seconds."
---

# Quickstart

This page takes you from a blank shell to a successful API call in about a minute. It
targets **Python 3.10+** and the official `cerberus-compliance` package on PyPI.

## Install

Pick one of the install flows below. All three install the same wheel.

```bash
pip install cerberus-compliance
```

```bash
uv add cerberus-compliance
```

For local development (tests, linters, mock-server libraries):

```bash
pip install "cerberus-compliance[dev]"
```

The `[dev]` extra pulls in `pytest`, `pytest-asyncio`, `pytest-cov`, `respx`,
`responses`, `ruff`, `mypy`, and the OpenAPI client generator.

## Get an API key

API keys are scoped to a single tenant and are created from the **Cerberus admin
dashboard** (available from phase P3 onward). Each key has a public 8-character prefix
(safe to log — useful for audit trails) and a secret remainder that must be treated as
a credential.

Export the key as `CERBERUS_API_KEY` before running any snippet on this page:

```bash
export CERBERUS_API_KEY="ck_live_..."
```

Never commit an API key. Keep it in a secret manager (AWS Secrets Manager, HashiCorp
Vault, 1Password, Doppler, etc.) and inject it at runtime. See
[`docs/auth.md`](./auth.md) for the full guidance.

## First call — sync

```python
import os
from cerberus_compliance import CerberusClient, CerberusAPIError

with CerberusClient(api_key=os.environ["CERBERUS_API_KEY"]) as client:
    try:
        # Once v0.1.0 GA ships resources will be at client.entities.get(rut=...)
        response = client._request(
            "GET",
            "/entities",
            params={"rut": "76.086.428-5", "limit": 1},
        )
    except CerberusAPIError as exc:
        print(f"API error {exc.status}: {exc.title} (request_id={exc.request_id})")
        raise

    entities = response.get("data") or []
    if not entities:
        raise SystemExit("no entity matched that RUT")
    print(entities[0]["legal_name"])
```

What to notice:

- The client is used as a context manager so the underlying `httpx.Client` is released
  when the block exits.
- `_request` returns the parsed JSON body as a `dict`. List endpoints use the
  `{"data": [...], "next": "<cursor>"}` envelope.
- Wrapping the call in `try/except CerberusAPIError` is the minimum shape for
  production code. From day one you get a typed exception with `.status`, `.title`, and
  `.request_id` attached.

## First call — async

```python
import asyncio
import os
from cerberus_compliance import AsyncCerberusClient, CerberusAPIError

async def main() -> None:
    async with AsyncCerberusClient(api_key=os.environ["CERBERUS_API_KEY"]) as client:
        try:
            response = await client._request(
                "GET",
                "/entities",
                params={"rut": "76.086.428-5", "limit": 1},
            )
        except CerberusAPIError as exc:
            print(f"API error {exc.status}: {exc.title}")
            raise

        entities = response.get("data") or []
        if not entities:
            raise SystemExit("no entity matched that RUT")
        print(entities[0]["legal_name"])

asyncio.run(main())
```

The async client is a strict mirror of the sync one — same constructor keyword
arguments, same retry policy, same error hierarchy. You can run many requests
concurrently with `asyncio.gather` once you have the client open.

## Next steps

- [Authentication](./auth.md) — key rotation, staging base URLs, custom `httpx`
  clients, and secret hygiene.
- [Errors](./errors.md) — the `CerberusAPIError` hierarchy and handler recipes.
- [Pagination](./pagination.md) — cursor conventions and the `iter_all` helper.
- Examples: [`examples/kyb_quickstart.py`](../examples/kyb_quickstart.py),
  [`examples/monitor_portfolio.py`](../examples/monitor_portfolio.py),
  [`examples/webhook_handler.py`](../examples/webhook_handler.py),
  [`examples/notebooks/01-kyb-quickstart.ipynb`](../examples/notebooks/01-kyb-quickstart.ipynb).
