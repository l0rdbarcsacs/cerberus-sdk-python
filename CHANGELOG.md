# Changelog

All notable changes to `cerberus-compliance` are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [v0.1.0-rc1] — Unreleased

### Added
- Foundation client infrastructure: `CerberusClient`, `AsyncCerberusClient`, `BaseResource`, `AsyncBaseResource`.
- API-key auth via `httpx.Auth` (`Authorization: Bearer <key>`).
- Configurable retry with exponential backoff + jitter, honoring `Retry-After`.
- Typed error hierarchy parsing RFC 7807 problem documents (`CerberusAPIError`, `AuthError`,
  `ValidationError`, `QuotaError`, `RateLimitError`, `ServerError`).
- Pytest fixtures (`sync_client`, `async_client`, `responses_mock`, `problem_json`) for downstream resource modules.
- CI matrix (Python 3.10 / 3.11 / 3.12) with `pytest`, `ruff`, `mypy --strict`.
- Release workflow: TestPyPI for `*-rc*`/`*-beta*`/`*-alpha*` tags, PyPI for stable `v*` tags.
- Developer-experience layer:
  - `examples/kyb_quickstart.py` — CLI KYB walkthrough (entity + material events + sanctions
    + directors + regulations) with optional `rich` rendering.
  - `examples/monitor_portfolio.py` — async polling monitor for a CSV of RUTs, logging new
    material-event deltas; handles `RateLimitError`, graceful SIGINT/SIGTERM shutdown.
  - `examples/webhook_handler.py` — FastAPI receiver with HMAC-SHA256 signature verification,
    replay-window defense, and a routing table for `material_event.published` / `sanction.added`.
  - `examples/notebooks/01-kyb-quickstart.ipynb` — narrated Jupyter version of the quickstart.
  - `README.md` with install/quickstart/auth/retries/errors/async/pagination overview.
  - `docs/quickstart.md`, `docs/auth.md`, `docs/errors.md`, `docs/pagination.md` — Mintlify-ready
    guides consumed by the P7 dev portal.

### Known gaps (rc1 → GA)
- Resource namespaces (`client.entities`, `client.persons`, `client.material_events`,
  `client.sanctions`, `client.registries`, `client.regulations`) land in feat/resources-1
  and feat/resources-2 before the `v0.1.0` GA tag. Until then, examples and notebooks use the
  low-level `client._request(method, path, *, params=..., json=...)` surface; every such call
  is tagged `TODO(#P4-B-merge)` for surgical replacement once the resources PRs land.

[v0.1.0-rc1]: https://github.com/l0rdbarcsacs/cerberus-sdk-python/releases/tag/v0.1.0-rc1
