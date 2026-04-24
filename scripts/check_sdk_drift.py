#!/usr/bin/env python3
"""Compare live Cerberus Compliance OpenAPI paths vs SDK resource coverage.

Running this script tells you, at a glance:

* **covered** — paths the prod API publishes that the SDK has a typed
  wrapper for. Good.
* **uncovered_api** — paths the prod API publishes that the SDK does
  not yet wrap. Warning; callers will have to fall back to
  ``client._request(...)``.
* **rotten_sdk** — SDK methods pointing at paths that no longer exist
  in the prod spec. Hard failure under ``--fail-on-drift`` because it
  means shipped code is broken.

Usage::

    python scripts/check_sdk_drift.py
    python scripts/check_sdk_drift.py --base-url https://staging-compliance.cerberus.cl/v1
    python scripts/check_sdk_drift.py --fail-on-drift --json

Design
------
The SDK surface is hand-mapped below in :data:`RESOURCE_COVERAGE` rather
than introspected at runtime. Rationale:

* SDK methods accept Python-native args (``date``, ``Sequence[str]``)
  that don't round-trip trivially to OpenAPI path templates.
* Introspection would pick up private ``_path_prefix`` + synthesise
  paths, but the synthesis table is exactly what a maintainer would
  want to audit by eye when the API changes. So we surface it here as
  data rather than hide it behind ``inspect.getmembers``.
* The table doubles as documentation of what the SDK *intends* to
  cover, which is useful in its own right.

Keep :data:`RESOURCE_COVERAGE` in sync with
:mod:`cerberus_compliance.resources` whenever you add or rename a
method. The drift checker will call you on it the next time it runs.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger("cerberus_compliance.scripts.check_sdk_drift")


# --------------------------------------------------------------------------- #
# Hand-maintained SDK coverage table                                          #
# --------------------------------------------------------------------------- #

# Each entry maps ``(method, openapi_path_template)`` to
# ``(resource_attr, sdk_method_name)``. Path templates use ``{var}`` placeholders
# matching the OpenAPI spec convention.
# Path-template variable names match the live prod OpenAPI spec
# (``{entity_id}``, ``{regulation_id}``, ``{sancion_id}``, etc.). Do not
# generalise them to ``{id}`` — the drift checker compares raw template
# strings, so a mismatch here produces spurious rotten_sdk entries.
RESOURCE_COVERAGE: dict[tuple[str, str], tuple[str, str]] = {
    # /kyb (G1)
    ("GET", "/kyb/{rut}"): ("kyb", "get"),
    # /entities — the live API exposes the collection with a trailing slash.
    ("GET", "/entities/"): ("entities", "list"),
    ("GET", "/entities/{entity_id}"): ("entities", "get"),
    ("GET", "/entities/by-rut/{rut}"): ("entities", "by_rut"),  # G12
    ("GET", "/entities/{entity_id}/ownership"): ("entities", "ownership"),  # G13
    ("GET", "/entities/{entity_id}/directors"): ("entities", "directors"),
    # /sanctions (G2 — sanctions by entity moved here, away from /entities/{id}/sanctions)
    ("GET", "/sanctions"): ("sanctions", "list"),
    ("GET", "/sanctions/{sancion_id}"): ("sanctions", "get"),
    ("GET", "/sanctions/by-entity/{entity_id}"): ("entities", "sanctions"),  # G2
    # /persons — only the regulatory-profile endpoint is real in prod.
    # ``PersonsResource.list`` and ``PersonsResource.get`` are SDK methods
    # deprecated in v0.2.0 (they raise ``NotImplementedError`` at runtime and
    # will be removed in v0.3.0); they are intentionally absent from this
    # coverage table so the drift report stays 0-rotten.
    ("GET", "/persons/{rut}/regulatory-profile"): ("persons", "regulatory_profile"),
    # /regulations (+ G16 search)
    ("GET", "/regulations"): ("regulations", "list"),
    ("GET", "/regulations/{regulation_id}"): ("regulations", "get"),
    ("GET", "/regulations/search"): ("regulations", "search"),
    # /rpsf (G14)
    ("GET", "/rpsf"): ("rpsf", "list"),
    ("GET", "/rpsf/{inscripcion_id}"): ("rpsf", "get"),
    ("GET", "/rpsf/by-entity/{entity_id}"): ("rpsf", "by_entity"),
    ("GET", "/rpsf/by-servicio/{servicio}"): ("rpsf", "by_servicio"),
    # /normativa (G15)
    ("GET", "/normativa"): ("normativa", "list"),
    ("GET", "/normativa/{regulation_id}"): ("normativa", "get"),
    ("GET", "/normativa/{regulation_id}/mercado"): ("normativa", "mercado"),
}
"""Keep in sync with :mod:`cerberus_compliance.resources` — one entry per
endpoint + SDK method pair the SDK intends to wrap. Path-template variable
names MUST match the prod OpenAPI spec literally."""

# Endpoints the SDK deliberately does NOT wrap (operational/health). Kept out
# of "uncovered_api" so the drift report stays focused on user-facing gaps.
IGNORED_PATHS: frozenset[str] = frozenset(
    {
        "/healthz",
        "/readyz",
        "/v1/healthz",
        "/v1/readyz",
        "/health",
        "/v1/health",
        "/openapi.json",
        "/v1/openapi.json",
        "/docs",
        "/redoc",
    }
)

# Path prefixes (not exact matches) the SDK deliberately does NOT wrap. The
# Cerberus Compliance prod service exposes two distinct API surfaces in the
# same OpenAPI document:
#
#   * The **SDK-facing read API** under ``/`` (``/kyb``, ``/entities``, …).
#   * The **tenant/admin app API** under ``/api/v1/*`` and ``/auth/*`` —
#     these drive the internal dashboard and are intentionally not exposed
#     through this SDK. Including them in "uncovered_api" would bury the
#     actionable gaps under ~50 false-positive lines.
IGNORED_PREFIXES: tuple[str, ...] = (
    "/api/v1/",
    "/auth/",
)


# --------------------------------------------------------------------------- #
# Data model                                                                  #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Endpoint:
    """One ``(method, path)`` endpoint extracted from an OpenAPI spec."""

    method: str
    path: str

    def key(self) -> tuple[str, str]:
        return (self.method.upper(), self.path)


@dataclass
class DriftReport:
    """Summary of the SDK vs OpenAPI comparison."""

    covered: list[Endpoint] = field(default_factory=list)
    uncovered_api: list[Endpoint] = field(default_factory=list)
    rotten_sdk: list[tuple[str, str, str, str]] = field(default_factory=list)
    """(method, path, resource_attr, sdk_method_name) tuples for SDK
    methods that point at paths not in the live spec."""

    ignored: list[Endpoint] = field(default_factory=list)

    @property
    def has_drift(self) -> bool:
        """True when anything actionable (uncovered or rotten) was found."""
        return bool(self.uncovered_api) or bool(self.rotten_sdk)

    def to_json(self) -> dict[str, Any]:
        return {
            "covered": [[e.method, e.path] for e in self.covered],
            "uncovered_api": [[e.method, e.path] for e in self.uncovered_api],
            "rotten_sdk": [list(t) for t in self.rotten_sdk],
            "ignored": [[e.method, e.path] for e in self.ignored],
        }


# --------------------------------------------------------------------------- #
# OpenAPI fetch + parse                                                       #
# --------------------------------------------------------------------------- #


def fetch_openapi(base_url: str, *, timeout: float = 10.0) -> dict[str, Any]:
    """Fetch the OpenAPI document for ``base_url``.

    Tries ``<base_url>/openapi.json`` first (e.g. prod exposes it under
    the ``/v1`` prefix), then falls back to the root-relative
    ``<scheme+host>/openapi.json``.
    """
    base_url = base_url.rstrip("/")
    candidates = [f"{base_url}/openapi.json"]

    # Root-level fallback: strip any suffix path (e.g. ``/v1``) and try there.
    match = re.match(r"^(https?://[^/]+)(/.*)?$", base_url)
    if match:
        root = match.group(1)
        root_candidate = f"{root}/openapi.json"
        if root_candidate not in candidates:
            candidates.append(root_candidate)

    last_exc: Exception | None = None
    for url in candidates:
        try:
            logger.info("fetching openapi from %s", url)
            response = httpx.get(url, timeout=timeout, follow_redirects=True)
        except httpx.HTTPError as exc:
            last_exc = exc
            continue
        if response.status_code == 200:
            parsed: Any = response.json()
            if isinstance(parsed, dict):
                return parsed
        last_exc = RuntimeError(f"status {response.status_code} from {url}")

    raise RuntimeError(f"could not fetch OpenAPI spec from {candidates}: {last_exc}")


def extract_endpoints(spec: dict[str, Any]) -> list[Endpoint]:
    """Return every ``(method, path)`` pair from an OpenAPI ``paths`` map.

    Strips a leading ``/v1`` prefix if present so the spec keys line up with
    :data:`RESOURCE_COVERAGE` (which is written without the version prefix).
    """
    paths = spec.get("paths")
    if not isinstance(paths, dict):
        return []

    endpoints: list[Endpoint] = []
    http_verbs = {"get", "post", "put", "patch", "delete", "head", "options"}
    for raw_path, path_item in paths.items():
        if not isinstance(raw_path, str) or not isinstance(path_item, dict):
            continue
        normalized = raw_path
        if normalized.startswith("/v1/"):
            normalized = normalized[3:]
        elif normalized == "/v1":
            normalized = "/"
        for verb, _ in path_item.items():
            if verb.lower() in http_verbs:
                endpoints.append(Endpoint(method=verb.upper(), path=normalized))
    return endpoints


# --------------------------------------------------------------------------- #
# Diff                                                                        #
# --------------------------------------------------------------------------- #


def _is_ignored(path: str) -> bool:
    if path in IGNORED_PATHS or path.replace("/v1", "") in IGNORED_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in IGNORED_PREFIXES)


def compute_drift(
    api_endpoints: Iterable[Endpoint],
    coverage: dict[tuple[str, str], tuple[str, str]] = RESOURCE_COVERAGE,
) -> DriftReport:
    """Compare API endpoints against the SDK coverage table.

    Returns a :class:`DriftReport`. Every API endpoint is classified as
    exactly one of ``covered`` / ``uncovered_api`` / ``ignored``. Every
    SDK entry with no matching API endpoint becomes ``rotten_sdk``.
    """
    report = DriftReport()
    api_keys = {e.key() for e in api_endpoints}

    for endpoint in api_endpoints:
        if _is_ignored(endpoint.path):
            report.ignored.append(endpoint)
            continue
        if endpoint.key() in coverage:
            report.covered.append(endpoint)
        else:
            report.uncovered_api.append(endpoint)

    for key, (resource_attr, method_name) in coverage.items():
        if key not in api_keys:
            report.rotten_sdk.append((key[0], key[1], resource_attr, method_name))

    return report


# --------------------------------------------------------------------------- #
# CLI                                                                         #
# --------------------------------------------------------------------------- #


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="check_sdk_drift",
        description="Compare live OpenAPI paths vs SDK resource coverage.",
    )
    parser.add_argument(
        "--base-url",
        default="https://compliance.cerberus.cl/v1",
        help="Base URL of the prod/staging Cerberus Compliance API.",
    )
    parser.add_argument(
        "--fail-on-drift",
        action="store_true",
        help="Exit 1 when any uncovered_api or rotten_sdk entries are found.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the report as a machine-readable JSON blob on stdout.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging.",
    )
    return parser


def _render_human(report: DriftReport) -> str:
    """Render a human-readable drift report for stdout."""
    lines: list[str] = []
    lines.append(f"Covered       : {len(report.covered)}")
    lines.append(f"Uncovered API : {len(report.uncovered_api)}")
    lines.append(f"Rotten SDK    : {len(report.rotten_sdk)}")
    lines.append(f"Ignored       : {len(report.ignored)}")
    lines.append("")

    if report.rotten_sdk:
        lines.append("ROTTEN SDK (SDK methods pointing at paths not in the live spec)")
        lines.append("-" * 72)
        for method, path, resource_attr, method_name in report.rotten_sdk:
            lines.append(f"  {method:6s} {path:50s} client.{resource_attr}.{method_name}")
        lines.append("")

    if report.uncovered_api:
        lines.append("UNCOVERED API (live paths with no SDK wrapper)")
        lines.append("-" * 72)
        for endpoint in report.uncovered_api:
            lines.append(f"  {endpoint.method:6s} {endpoint.path}")
        lines.append("")

    if report.covered:
        lines.append("COVERED")
        lines.append("-" * 72)
        for endpoint in report.covered:
            attr, method_name = RESOURCE_COVERAGE[endpoint.key()]
            lines.append(f"  {endpoint.method:6s} {endpoint.path:50s} client.{attr}.{method_name}")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns a POSIX-style exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    try:
        spec = fetch_openapi(args.base_url)
    except (httpx.HTTPError, RuntimeError) as exc:
        sys.stderr.write(f"error: could not fetch OpenAPI spec: {exc}\n")
        return 2

    endpoints = extract_endpoints(spec)
    report = compute_drift(endpoints)

    if args.json:
        sys.stdout.write(json.dumps(report.to_json(), indent=2, sort_keys=True))
        sys.stdout.write("\n")
    else:
        sys.stdout.write(_render_human(report))
        sys.stdout.write("\n")

    if args.fail_on_drift and report.has_drift:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
