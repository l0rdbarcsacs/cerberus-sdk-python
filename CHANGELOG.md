# Changelog

All notable changes to `cerberus-compliance` are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [v0.3.0rc1] — 2026-04-24

Release candidate for v0.3.0. Adds the two new P5.2 "deep-data" resources
(`indicadores`, `normativa_consulta`) and **drops the pre-v0.2.0 deprecated
shims** that were scheduled for removal in v0.3.0.

### Added

- **`client.indicadores` (G8).** Typed accessor for `/indicadores/{name}`
  covering the six CMF Indicadores API v3 series: `UF`, `UTM`, `USD`, `EUR`,
  `IPC`, `TMC`. Methods:
  - `indicadores.get(name, date=None)` — single-date (or latest) value.
  - `indicadores.history(name, from_, to)` — historical range transformed
    internally from `YYYY-MM-DD` start/end into the CMF `periodo=Y/M/Y/M`
    form; returns the `values` array unwrapped for ergonomics.
  Async mirror: `AsyncIndicadoresResource`. Values are returned as **strings**
  (CMF-published precision, no float rounding) so `Decimal` consumers stay
  exact.
- **`client.normativa_consulta` (G9).** Typed accessor for
  `/normativa-consulta?estado=abierta|cerrada` — open and recently-closed
  CMF rulemaking consultations scraped from `normativa_tramite.php` +
  `normativa_tramite_cerrada.php` every 2h. Method:
  - `normativa_consulta.list(estado="abierta", limit=100, offset=0)`
  Async mirror: `AsyncNormativaConsultaResource`. Exposes the
  `NormativaConsultaEstado = Literal["abierta", "cerrada"]` type at the
  package top level for strict-mypy callers.
- `examples/indicadores_basic.py` and `examples/normativa_consulta_basic.py`
  — runnable walkthroughs for the two new resources.
- `tests/resources/test_indicadores.py` and
  `tests/resources/test_normativa_consulta.py` — respx-backed unit coverage
  for happy paths, envelope compatibility, path-traversal hardening, and
  error mapping. Integration cases added to
  `tests/integration/test_live_staging.py`.

### Changed

- `scripts/check_sdk_drift.py`: `RESOURCE_COVERAGE` now lists
  `/indicadores/{name}` and `/normativa-consulta` so the drift gate recognises
  the two new resources.
- `docs/api/endpoints.md` (backend repo) now documents both endpoints; this
  SDK's `README.md` surface table mirrors the addition.

### Removed — **breaking**

- **`client.registries` and its sync/async classes, plus `RegistryType`.**
  The resource was a deprecated shim flagged in v0.2.0; all five call paths
  were already raising `NotImplementedError` or emitting a
  `DeprecationWarning`. Callers have been migrating to `client.entities.by_rut`
  for six months. Removed per the v0.2.0 roadmap (D.4 audit finding).
- **`client.material_events` and its sync/async classes.** Same history as
  `registries` — deprecated in v0.2.0, all methods were no-ops modulo the
  warning. Material events are available on `client.kyb.get(rut)` under
  `recent_material_events` and on `client.entities.material_events(id)`.

  Migration recipe for anyone still on the shim::

      # Before (v0.2.x)
      events = client.material_events.list(entity_id=eid)  # raised

      # After (v0.3.0)
      events = client.kyb.get(rut)["recent_material_events"]
      # or
      events = client.entities.material_events(eid)

### Chore

- `pyproject.toml` version bumped to `0.3.0rc1`; the stable `0.3.0` tag
  follows the TestPyPI canary verification.
- `tests/test_public_api.py::test_dead_shims_are_gone` guards the removal —
  imports and `__all__` must not re-introduce the shims.

[v0.3.0rc1]: https://github.com/l0rdbarcsacs/cerberus-sdk-python/releases/tag/v0.3.0-rc1

## [Unreleased]

### Documentation

- **README rewrite.** Added a "What problem does it solve?" intro,
  a resource-at-a-glance table covering every v0.2.0 endpoint, a flagship
  "KYB Express" section with a real (trimmed) prod response shape,
  tier / scope / rate-limit guidance, per-exception handling recipes,
  cursor-pagination idioms, an examples index table, and an explicit
  deprecation migration table for `persons.list/get`, `registries.*`,
  and `material_events.*`.
- **New runnable examples (9).** `entities_lookup.py`,
  `sanctions_browse.py`, `regulations_search.py`, `rpsf_explore.py`,
  `normativa_explore.py`, `persons_profile.py`,
  `async_concurrent_lookups.py`, `error_handling.py`, and
  `cursor_pagination.py`. Each is verified against prod with a
  `professional`-tier key; each ships the standard
  `Runnable:` / `Tier required:` / `Expected runtime:` docstring block
  and can be invoked with zero arguments.
- **Existing examples modernised.**
  - `kyb_quickstart.py` now defaults `--rut` to `96.505.760-9` so it runs
    out of the box (ergonomics + release-gate friendliness).
  - `monitor_portfolio.py` rewritten to use `client.kyb.get(rut,
    include=["material_events"])` + diff `recent_material_events` instead
    of the fictional `/entities/{id}/material_events`; `--csv` is now
    optional and the script runs a one-tick demo against a built-in
    5-RUT sample portfolio when omitted.
  - `webhook_handler.py` exits cleanly (0) with a setup hint when
    `CERBERUS_WEBHOOK_SECRET` / `fastapi` / `uvicorn` are missing,
    instead of hanging uvicorn under a missing secret.

### Chore

- `pyproject.toml`: `tool.ruff.lint.per-file-ignores` now exempts
  `examples/**/*.py` from `T201`/`T203` — example CLIs print to stdout
  by design.

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
