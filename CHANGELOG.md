# Changelog

All notable changes to `cerberus-compliance` are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [v0.5.1] — 2026-04-27

### Fixed

- **Documentation, examples and codegen URLs** corrected. `docs/auth.md`,
  `examples/notebooks/01-kyb-quickstart.ipynb`, and `scripts/codegen.sh`
  still referenced the obsolete `api.cerberus.cl` /
  `staging-api.cerberus.cl` hosts in code samples and the OpenAPI fetch
  URL. The runtime client (`cerberus_compliance.client`) was already
  correct since v0.3.0 — no behavioural change for consumers using the
  default `base_url`. Anyone who copy-pasted the sample `base_url=` in
  `docs/auth.md` would have hit an unresolvable host; this release
  removes those broken references.

## [v0.5.0] — 2026-04-27

P5.4.2 commercial extensions — five new resources, four extended
resources, an offline webhook signature verifier, and the BCentral
indicator series wired through the existing `indicadores` accessor.

### Added — five new resources

- **`client.admin_api_keys`** — typed accessor for
  `GET /v1/admin/api-keys/me`. Returns the calling key's metadata
  (prefix, env, tier, scopes, expiry, daily + monthly quota) without
  ever leaking the secret. Method: `me()`. Async mirror:
  `AsyncAdminApiKeysResource`.

- **`client.sasb_topics`** — `GET /v1/sasb-topics`. Wraps the SASB
  Standards 2018 reference taxonomy (~395 topics across 40 SICS
  industries). Methods: `list(industry=, limit=, offset=)`,
  `iter_all(industry=)` (offset-paginated). Async mirror.

- **`client.exports`** — bulk export lifecycle for enterprise tier.
  Methods: `create(resource, *, format='csv'|'parquet', filters=,
  fields=)`, `get(export_id)`, `delete(export_id)`, `list(limit=)`,
  `wait(export_id, *, poll_interval=, timeout=)`. CSV + Parquet,
  presigned MinIO URLs with 1h TTL. Async mirror.

- **`client.webhooks`** — full CRUD lifecycle plus offline signature
  verification. Methods: `create(callback_url, event_types,
  description=)`, `list()`, `get(id)`, `update(id, ...)`, `delete(id)`,
  `deliveries(id, limit=)`, `test(id)`. The plaintext secret is only
  returned on `create()` — subsequent reads omit it. The
  `WebhooksResource.verify_signature(payload, signature_header,
  secret)` static method (also re-exported as
  `cerberus_compliance.verify_webhook_signature`) implements the
  Stripe-compatible `t=,v1=hmac-sha256` scheme with replay protection
  (defaults to a 5-minute max signature age). Async mirror.

- **`client.equity`** — `GET /v1/equity/{ticker}/prices`. Daily OHLCV
  for the IPSA-25 sourced from Yahoo Finance, with `entity_id`
  resolution against `cmf_entities`. Method: `prices(ticker, *,
  from_=, to=)`. Async mirror.

### Added — extensions to existing resources

- **`client.persons.list(*, pep, cargo, entity_kind, cursor, limit)`**
  + `iter_all()` — paginated list of natural persons with their active
  cargos. The `pep=True` filter narrows to active cargos at bancos and
  IPSA-25 emisores (Cerberus's PEP-lite definition). New public Literal
  alias: `PersonEntityKind`.

- **`client.esg.rankings(*, indicator, year, top_n, direction='desc',
  industry=)`** — top-N emisores ranked by an NCG-461 ESG indicator for
  a fiscal year. New public Literal alias: `ESGRankingDirection`.

- **`client.entities.diff(entity_id, *, from_, to=)`** — SCD2 traversal
  of `cmf_entity_history` plus director appointments / removals from
  `cmf_persona_cargos` between two dates. Returns a chronological list
  of `{timestamp, field, old_value, new_value, source}` changes.

- **`client.entities.bancos_fichas(rut, year=, month=)`** and
  **`client.entities.bancos_fichas_latest_per_section(rut)`** — wraps
  the P5.4.1 endpoint that returns the most recent ficha per RAN
  section, useful when individual sections are frozen in different
  months (e.g. `adecuacion_capital` lags `composicion_directorio`).

- **`client.sanctions.cross_reference(*, rut=, name=, threshold=0.92,
  limit=50)`** — match a person or entity against OFAC SDN, UN
  Consolidated, and the internal CMF lists. Uses Jaro-Winkler matching
  on normalized names. Raises `ValueError` if neither `rut` nor `name`
  is supplied.

- **`client.indicadores`** — the existing `get(name, ...)` and
  `history(name, ...)` accessors now serve five additional series
  ingested from the Banco Central de Chile (`source='bcentral_api'`):
  TPM, IMACEC, IMACEC_MIN, IPC_BCH, PIB. New public Literal aliases:
  `SbifIndicatorName`, `BCentralIndicatorName`, `IndicatorName` (the
  union, unchanged in name from v0.4.0).

### Added — public re-exports

`__init__.py` now exports `verify_webhook_signature` as a
top-level convenience along with the new resource classes and the
three Literal type aliases (`PersonEntityKind`, `ESGRankingDirection`,
`SbifIndicatorName`, `BCentralIndicatorName`, `IndicatorName`).

### Notes for upgraders

- The previously-deprecated `PersonsResource.list()` and
  `iter_all()` shims that raised `NotImplementedError` are gone.
  Callers writing `client.persons.list(pep=True)` now hit the live
  endpoint instead of the shim — this is a fix, not a break, but
  worth flagging since the runtime behaviour has changed.
- `client.exports.wait()` raises `CerberusAPIError` (not a subclass)
  on `failed`, `expired`, or timeout. The original problem-detail
  body is forwarded into the exception's `.problem` attribute so
  callers can inspect `failure_reason` / `rows_exported`.

### Tests

698 passing (was 547 in v0.4.0 audit). 18 skipped (live-staging tests
gated on `CERBERUS_STAGING_KEY`). Mypy strict-clean, ruff clean.

## [v0.4.0] — 2026-04-26

Nine new resource modules covering the full CMF document corpus, plus
universal semantic search powered by Qdrant + Bedrock Titan Embeddings.
This release completes the P5.3 Wave E SDK surface.

### Added

- **`client.resoluciones`** — typed accessor for `GET /resoluciones` and
  `GET /resoluciones/{id}`. Wraps CMF formal resolutions (numbered
  administrative acts). Methods: `list(**params)`, `get(id_)`, `iter_all(**filters)`.
  Async mirror: `AsyncResolucionesResource`.

- **`client.opas`** — typed accessor for `GET /opas` and `GET /opas/{id}`.
  Wraps OPAs (Ofertas Públicas de Adquisición) regulated under Ley 18.045
  Title XXV. Methods: `list`, `get`, `iter_all`. Async mirror: `AsyncOPAsResource`.

- **`client.tdc`** — typed accessor for `GET /tdc` and `GET /tdc/{id}`.
  Wraps CMF-published Tasa de Descuento de Cartera series. Methods: `list`,
  `get`, `iter_all`. Async mirror: `AsyncTDCResource`.

- **`client.art12`** — typed accessor for `GET /art12` and `GET /art12/{id}`.
  Wraps Artículo 12 (Ley 18.045) controller / major-shareholder stake
  disclosures. Methods: `list`, `get`, `iter_all`. Async mirror:
  `AsyncArt12Resource`.

- **`client.art20`** — typed accessor for `GET /art20` and `GET /art20/{id}`.
  Wraps Artículo 20 (Ley 18.045) hechos esenciales filings. Methods:
  `list`, `get`, `iter_all`. Async mirror: `AsyncArt20Resource`.

- **`client.comunicaciones`** — typed accessor for `GET /comunicaciones` and
  `GET /comunicaciones/{id}`. Wraps official CMF communications (circulars,
  letters, notices). Methods: `list`, `get`, `iter_all`. Async mirror:
  `AsyncComunicacionesResource`.

- **`client.dictamenes`** — typed accessor for `GET /dictamenes` and
  `GET /dictamenes/{id}`. Wraps CMF legal opinions and formal rulings.
  Methods: `list`, `get`, `iter_all`. Async mirror: `AsyncDictamenesResource`.

- **`client.esg`** — typed accessor for `GET /esg/{rut}`. Wraps NCG 461
  (2023) ESG sustainability disclosures for publicly listed Chilean companies.
  The primary method is `get(rut)` returning the full ESG dossier; `list`
  enumerates all entities with ESG data. Async mirror: `AsyncESGResource`.

- **`client.normativa_historic`** — typed accessor for
  `GET /normativa/historic` and `GET /normativa/historic/{id}`. Exposes the
  point-in-time version history of CMF regulatory texts for retroactive
  compliance checks and change-log diffing. Methods: `list`, `get`,
  `iter_all`. Async mirror: `AsyncNormativaHistoricResource`.

- **`client.search`** — universal CMF semantic search client wrapping
  `POST /search`. Backed by Qdrant vector search + AWS Bedrock Titan
  Embeddings. The `search(query, filters, top_k)` method returns a
  `SearchResponse` with ranked `SearchHit` items across the full document
  corpus (resoluciones, OPAs, TDC, Art.12/20, comunicaciones, dictámenes,
  ESG, normativa, normativa-consulta). `SearchFilters` Pydantic model
  supports `doc_types`, `from_date`, `to_date`, `entity_rut` filtering.
  Async mirror: `AsyncSearchClient`.

- New Pydantic models exported from `cerberus_compliance.resources.search`:
  `SearchFilters`, `SearchHit`, `SearchResponse`.

- `scripts/check_sdk_drift.py`: `RESOURCE_COVERAGE` extended with 19 new
  entries covering all 9 new resource endpoints + `POST /search`.

### Breaking changes

None. All additions are net-new attributes on `CerberusClient` /
`AsyncCerberusClient`. No existing method signatures changed.

### Release flow

Release to TestPyPI + PyPI deferred to operator post-merge — credentials
required. Tag `v0.4.0` triggers the CI release workflow automatically.

[v0.4.0]: https://github.com/l0rdbarcsacs/cerberus-sdk-python/releases/tag/v0.4.0

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
