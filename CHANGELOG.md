# Changelog

All notable changes to `cerberus-compliance` are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [v0.1.0-rc1] — Unreleased

### Added
- Foundation client infrastructure: `CerberusClient`, `AsyncCerberusClient`, `BaseResource`, `AsyncBaseResource`.
- API-key auth via `httpx.Auth` (`Authorization: Bearer <key>`).
- Configurable retry with exponential backoff + jitter, honoring `Retry-After`.
- Typed error hierarchy parsing RFC 7807 problem documents.
- Pytest fixtures (`sync_client`, `async_client`, `responses_mock`, `problem_json`) for downstream resource modules.
- CI matrix (Python 3.10 / 3.11 / 3.12) with `pytest`, `ruff`, `mypy --strict`.
- Release workflow: TestPyPI for `*-rc*`/`*-beta*`/`*-alpha*` tags, PyPI for stable `v*` tags.

[v0.1.0-rc1]: https://github.com/l0rdbarcsacs/cerberus-sdk-python/releases/tag/v0.1.0-rc1
