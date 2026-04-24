# Handoff A → B / C / D

**Foundation SHA:** `e4fedb46a734e8fc0dcccb1c449eb81d3cb06189`
**Date:** 2026-04-23
**Status:** ✅ Ready for parallel tracks B / C / D

## Verification gates (all green on the foundation SHA)

- [x] `pytest -q` — **171 passed** in 0.32 s
- [x] Coverage — **99.78 %** on `cerberus_compliance/` (pyproject enforces ≥ 90 %)
- [x] `ruff check .` — clean
- [x] `ruff format --check .` — 16 files already formatted
- [x] `mypy --strict cerberus_compliance/` — Success, no issues found in 7 source files
- [x] Public surface matches the P4 plan contract
- [x] `# INSERT RESOURCES HERE` marker present exactly twice in `cerberus_compliance/client.py` (once per `__init__` — sync + async)

## What you can import now

```python
from cerberus_compliance import (
    CerberusClient, AsyncCerberusClient,
    CerberusAPIError, AuthError, ValidationError,
    QuotaError, RateLimitError, ServerError,
)
from cerberus_compliance.retry import RetryConfig, backoff_seconds, should_retry
from cerberus_compliance.auth import ApiKeyAuth, resolve_api_key, API_KEY_ENV_VAR
from cerberus_compliance.resources._base import BaseResource, AsyncBaseResource
```

`CerberusClient._request` / `AsyncCerberusClient._request` handle:
- retry on `RetryConfig.retry_on` statuses (default 429, 500, 502, 503, 504)
- `Retry-After` header (numeric or HTTP-date) honored on 429
- transport errors retried the same way
- error dispatch to the right `CerberusAPIError` subclass via `from_response`
- `X-Request-Id` response header plumbed into raised exceptions

## Scope boundaries — DO NOT cross

| Instance | Owns (create or edit)                                                                                                                            | Forbidden                                                       |
|----------|---------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------|
| **B** (`feat/resources-1`) | `cerberus_compliance/resources/{entities,persons,material_events}.py` + matching `tests/resources/test_*.py` + **append-only** edits to `client.py` and `resources/__init__.py` | anything under `cerberus_compliance/{errors,retry,auth,client}.py` body or `_base.py`; `examples/`; other resources |
| **C** (`feat/resources-2`) | `cerberus_compliance/resources/{sanctions,registries,regulations}.py` + matching `tests/resources/test_*.py` + **append-only** edits to `client.py` and `resources/__init__.py` | anything under core modules; `examples/`; B's resources |
| **D** (`feat/dx-examples`) | `examples/`, `examples/notebooks/`, real `README.md`, extended `CHANGELOG.md`, `docs/{quickstart,auth,errors,pagination}.md`; cross-track X1/X2/X3 in `cerberus_compliance` repo | nothing under `cerberus_compliance/` package source |

## Append-only merge points

Both B and C must touch `cerberus_compliance/client.py` and `cerberus_compliance/resources/__init__.py`. Keep edits append-only to guarantee a trivial rebase for the second PR to merge:

### `cerberus_compliance/client.py`

Two lines look exactly like this today (once in `CerberusClient.__init__`, once in `AsyncCerberusClient.__init__`):

```python
        # Sub-resources are wired below by Instances B/C — keep this exact marker:
        # INSERT RESOURCES HERE
```

**Do not remove the `# INSERT RESOURCES HERE` line.** Insert your wiring *above* it (still inside the `__init__` body):

```python
        self.entities = EntitiesResource(self)
        self.persons = PersonsResource(self)
        self.material_events = MaterialEventsResource(self)
        # Sub-resources are wired below by Instances B/C — keep this exact marker:
        # INSERT RESOURCES HERE
```

### `cerberus_compliance/resources/__init__.py`

Currently empty. Add append-only imports + update `__all__`:

```python
from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource
from cerberus_compliance.resources.entities import EntitiesResource
# ... etc.

__all__ = ["AsyncBaseResource", "BaseResource", "EntitiesResource", ...]
```

## How each instance starts

```bash
# Instance B
cd /home/l0rd/workspace/cerberus-sdk-python-B
git pull origin main --rebase        # fast-forward, foundation already present
cat docs/HANDOFF_A.md                 # confirm contract
source /home/l0rd/workspace/cerberus-sdk-python/.venv/bin/activate  # or recreate locally
pytest -q                             # sanity: 171 passed

# Instance C — identical, use cerberus-sdk-python-C
# Instance D — identical, use cerberus-sdk-python-D
```

If the shared venv is inconvenient across worktrees, each instance can spin up its own:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Sibling-module behavior notes (from subagent reports)

1. **respx query-string gotcha** — `respx_mock.get(path, params={})` matches *any* query string. In pagination tests, register the cursor-specific mock **before** the no-cursor mock, otherwise the latter swallows both.
2. **User-Agent** — `ApiKeyAuth` overrides httpx's auto-injected `python-httpx/*` User-Agent with `cerberus-compliance/<version>`; a caller-set UA is preserved.
3. **Network-error exhaustion** — after all retries the raw `httpx.TransportError` is re-raised (not wrapped). If you need a typed wrapper in a resource, do it at the resource level.
4. **Top-level list responses** — `_request` defensively wraps bare top-level JSON arrays as `{"data": [...]}`, so callers always get a dict.
5. **`Retry-After` plumbing** — passed through to `CerberusAPIError.from_response(retry_after=...)` as a string (full parser: numeric seconds or HTTP-date), and converted to float for the in-loop sleep decision.

## Branch protection

All three feature branches push to `origin/{feat/resources-1, feat/resources-2, feat/dx-examples}`. No direct pushes to `main`. The instance A controller merges PRs with `gh pr merge --squash` after a `cerberus-auditor` pass.

— Instance A, out.
