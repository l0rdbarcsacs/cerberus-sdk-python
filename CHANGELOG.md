# Changelog

All notable changes to `cerberus-compliance` are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [v0.1.0-rc1] — 2026-04-24

### Added
- Foundation client infrastructure: `CerberusClient`, `AsyncCerberusClient`, `BaseResource`, `AsyncBaseResource`.
- API-key auth via `httpx.Auth` (`Authorization: Bearer <key>`).
- Configurable retry with exponential backoff + jitter, honoring `Retry-After`.
- Typed error hierarchy parsing RFC 7807 problem documents (`CerberusAPIError`, `AuthError`,
  `ValidationError`, `QuotaError`, `RateLimitError`, `ServerError`).
- Six typed sub-resources with sync + async mirrors:
  - `client.entities` (`list` / `get` / `material_events` / `sanctions` / `directors` /
    `regulations` / `iter_all`).
  - `client.persons` (`list` / `get` / `regulatory_profile` / `iter_all`).
  - `client.material_events` (`list` with `since` / `until` / `entity_id` / `limit`,
    `get`, `iter_all`; timezone-aware datetimes required).
  - `client.sanctions` (`list` / `get` / `iter_all` with `SanctionSource` literal:
    `OFAC`, `EU`, `UN` / `ONU`, `CMF`).
  - `client.registries` (`list` / `get` / `lookup_rut` / `iter_all` with `RegistryType`
    literal: `CMF`, `SII`, `DICOM`, `Conservador`).
  - `client.regulations` (`list` / `get` / `iter_all` with `RegulationFramework`
    literal: `Ley21521`, `Ley21719`, `NCG514`, `SOX`, `MiFID`).
- Developer-experience layer:
  - `examples/kyb_quickstart.py`, `examples/monitor_portfolio.py`,
    `examples/webhook_handler.py`, `examples/notebooks/01-kyb-quickstart.ipynb`.
  - `README.md` with install / quickstart / auth / retries / errors / async / pagination.
  - `docs/{quickstart,auth,errors,pagination}.md` — Mintlify-ready guides for the P7 dev portal.
- CI matrix (Python 3.10 / 3.11 / 3.12) with `pytest`, `ruff`, `mypy --strict`.
- Release workflow: TestPyPI for `*-rc*` / `*-beta*` / `*-alpha*` tags, PyPI for stable `v*`.

### Security
- Path-traversal hardening in `BaseResource._get` / `AsyncBaseResource._get`:
  identifiers are percent-encoded with `urllib.parse.quote(safe="")`, so raw
  strings like `"../admin"` can no longer escape the sub-resource prefix.

### Changed
- `material_events` now rejects naive `datetime` filters with a `ValueError`;
  every timestamp crossing the API boundary must be timezone-aware
  (`America/Santiago` or UTC), matching the Cerberus-wide standard.

[v0.1.0-rc1]: https://github.com/l0rdbarcsacs/cerberus-sdk-python/releases/tag/v0.1.0-rc1
