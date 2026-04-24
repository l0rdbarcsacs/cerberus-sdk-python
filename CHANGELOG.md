# Changelog

All notable changes to `cerberus-compliance` are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [v0.2.0] — 2026-04-24

Track-to-prod overhaul. Closes the 10 gaps identified in the P5 endpoint
audit (G1/G2/G3/G4/G12/G13/G14/G15/G16/G17). The SDK now targets the real
production API at `https://compliance.cerberus.cl/v1`.

### Added

- **KYB resource (G1).** `client.kyb.get(rut, *, as_of, include)` and async
  mirror `AsyncKYBResource.get`. Flagship aggregate endpoint; `as_of` accepts
  `datetime.date` and is serialised as ISO 8601; `include` preserves
  caller order.
- **Entities enrichment (G12, G13).** `client.entities.by_rut(rut)` hits
  `/entities/by-rut/{rut}`; `client.entities.ownership(id_)` hits
  `/entities/{id}/ownership`. Both with async mirrors.
- **RPSF resource (G14).** New `client.rpsf` surface: `list`, `get`,
  `by_entity`, `by_servicio`, `iter_all` (plus async mirror). Wraps the
  CMF Registro Público de Servicios Financieros.
- **Normativa resource (G15).** New `client.normativa` surface: `list`,
  `get`, `mercado`, `iter_all` (plus async mirror). Wraps the regulatory-
  text catalogue and its per-norm market-segment mapping.
- **Regulations search (G16).** `client.regulations.search(q, **params)`
  hits `/regulations/search` (plus async mirror).
- **`NotFoundError` (404).** New subclass of `CerberusAPIError`; the
  transport now dispatches `404` to it instead of the bare base class, so
  callers can branch on `except NotFoundError`.
- **Drift-detection script (G17).** `scripts/check_sdk_drift.py` compares
  live OpenAPI paths against a hand-maintained SDK coverage table. Emits
  `covered` / `uncovered_api` / `rotten_sdk` buckets; supports
  `--fail-on-drift`, `--json`, `--verbose`.
- **Integration test suite.** `tests/integration/test_live_staging.py`
  hits `https://staging-compliance.cerberus.cl/v1` when
  `CERBERUS_STAGING_KEY` is set; skipped otherwise. Covers kyb.get,
  entities.list/get/by_rut/ownership, sanctions.list + entities.sanctions
  (G2), regulations.list + search, rpsf.list, normativa.list,
  persons.regulatory_profile.

### Changed

- **Default base URL (G4).** `DEFAULT_BASE_URL` is now
  `https://compliance.cerberus.cl/v1` (previously `https://api.cerberus.cl/v1`).
- **`client.entities.sanctions(id_)` (G2).** Now hits
  `/sanctions/by-entity/{id_}` instead of the fictional
  `/entities/{id_}/sanctions`. The method signature is unchanged; callers
  do not need to update.
- `examples/kyb_quickstart.py` rewritten to use `client.kyb.get(...)` as
  the single round-trip. All `_request` fallbacks removed.
- `README.md` primary example now uses `client.kyb.get(...)`.

### Deprecated

- **`client.registries` (G3).** The `/registries` endpoint family never
  shipped on the prod API. The resource is now a compatibility shim:
  - Constructor emits a `DeprecationWarning` once.
  - `list`, `get`, `iter_all` raise `NotImplementedError` with a migration
    message. Removed in v0.3.0.
  - `lookup_rut(rut)` still works — it emits a warning and internally
    calls `entities.by_rut(rut)`.
- **`client.material_events` (G3).** Material events are now embedded in
  the entity profile under the `hechos_esenciales` key returned by
  `entities.get(id)` and `kyb.get(rut)`. The standalone resource is a
  shim with the same deprecation semantics as `registries`: constructor
  warns, `list/get/iter_all` raise `NotImplementedError`. Removed in v0.3.0.
- **`PersonsResource.list()` and `PersonsResource.get()`.** The prod API
  never exposed `/v1/persons` (collection) or `/v1/persons/{id}` (detail);
  only `/v1/persons/{rut}/regulatory-profile` is real. Both methods are
  now partial-deprecation shims on `PersonsResource`: the constructor
  emits a single `DeprecationWarning`, and `list` / `get` / `iter_all`
  raise `NotImplementedError` with a migration message. Migrate to
  `client.persons.regulatory_profile(rut)` when you already know the
  RUT, or `client.entities.directors(id)` to enumerate personas tied to
  a legal entity. Removed in v0.3.0.

### Fixed

- `entities.sanctions(id_)` now hits a real endpoint (G2, see Changed).
- **`307 Temporary Redirect` on collection endpoints.** Both
  `CerberusClient` and `AsyncCerberusClient` now construct their
  underlying `httpx` client with `follow_redirects=True`. The prod API
  serves collection endpoints with a trailing slash
  (`GET /v1/entities/`, `GET /v1/sanctions/`), and FastAPI responds
  with a `307` when a caller omits it. `307` preserves the HTTP method
  and body, so following the redirect is safe for GET and POST alike.
  Before the fix, the default httpx client raised a `CerberusAPIError`
  on every `.list()` call against the real API.

### Security

- `NotFoundError` preserves the existing path-traversal hardening
  (percent-encoding in `_get` / `_list` / explicit `quote(..., safe="")`
  on all new URL segments).

[v0.2.0]: https://github.com/l0rdbarcsacs/cerberus-sdk-python/releases/tag/v0.2.0

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
