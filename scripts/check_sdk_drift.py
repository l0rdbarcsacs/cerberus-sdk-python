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
    python scripts/check_sdk_drift.py --base-url https://compliance.cerberus.cl/v1
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
    ("GET", "/entities"): ("entities", "list"),
    ("GET", "/entities/{entity_id}"): ("entities", "get"),
    ("GET", "/entities/by-rut/{rut}"): ("entities", "by_rut"),  # G12
    ("GET", "/entities/{entity_id}/ownership"): ("entities", "ownership"),  # G13
    ("GET", "/entities/{entity_id}/directors"): ("entities", "directors"),
    ("GET", "/entities/{entity_id}/diff"): ("entities", "diff"),
    # /bancos — bank fichas live under EntitiesResource because they're keyed
    # by entity RUT. /fichas/latest and /fichas/{fy}/{fm} are not yet wrapped.
    ("GET", "/bancos/{rut}/fichas"): ("entities", "bancos_fichas"),
    ("GET", "/bancos/{rut}/fichas/latest"): ("entities", "bancos_fichas_latest"),
    ("GET", "/bancos/{rut}/fichas/latest-per-section"): (
        "entities",
        "bancos_fichas_latest_per_section",
    ),
    ("GET", "/bancos/{rut}/fichas/{fiscal_year}/{fiscal_month}"): (
        "entities",
        "bancos_fichas_period",
    ),
    # /sanctions (G2 — sanctions by entity moved here, away from /entities/{id}/sanctions)
    ("GET", "/sanctions"): ("sanctions", "list"),
    ("GET", "/sanctions/{sancion_id}"): ("sanctions", "get"),
    ("GET", "/sanctions/by-entity/{entity_id}"): ("entities", "sanctions"),  # G2
    ("GET", "/sanctions/cross-reference"): ("sanctions", "cross_reference"),
    # /persons — list endpoint is real in prod (added v0.6.x). regulatory-profile
    # is the per-person enrichment endpoint. PersonsResource.get is deprecated
    # at runtime (raises NotImplementedError) and intentionally absent.
    ("GET", "/persons"): ("persons", "list"),
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
    # /normativa-consulta (P5.2 G9 — early-warning regulatory consultations)
    ("GET", "/normativa-consulta"): ("normativa_consulta", "list"),
    # /indicadores (P5.2 G8 → series_id-canonical since 0.8.0 — BCCh ~25k
    # series proxy). The canonical handle is the BCCh ``series_id`` (e.g.
    # ``F073.UFF.PRE.Z.D``); friendly names (``UF``, ``IPC``, …) are retired
    # and 404 in prod. The server exposes a single ``{series_id}`` path
    # template for both the single-date lookup (``?date=``) and the
    # historical range (``?from=&to=``); the SDK splits that into ``get()``
    # + ``history()`` but both land on the same OpenAPI entry. Discovery is
    # ``GET /indicadores/buscar``.
    ("GET", "/indicadores/{series_id}"): ("indicadores", "get"),
    ("GET", "/indicadores/buscar"): ("indicadores", "buscar"),
    # 0.8.0 — featured-catalog listing + multi-series comparison (both are
    # series_id-canonical surfaces added server-side with the Phase 2.x
    # indicadores uplift).
    ("GET", "/indicadores"): ("indicadores", "list"),
    ("GET", "/indicadores/compare"): ("indicadores", "compare"),
    # v0.4.0 — P5.3 nine new resources + universal semantic search.
    # Per-id ``GET /{resource}/{id}`` endpoints are NOT exposed in prod; the
    # corresponding ``ResourcesResource.get`` SDK methods raise
    # NotImplementedError at runtime and are intentionally absent from this
    # coverage table so the drift report stays 0-rotten.
    ("GET", "/resoluciones"): ("resoluciones", "list"),
    ("GET", "/opas"): ("opas", "list"),
    # SDK-01 — GLEIF LEI registry (cmf_lei_records); offset-paginated.
    ("GET", "/lei"): ("lei", "list"),
    ("GET", "/lei/{lei}"): ("lei", "get"),
    ("GET", "/tdc"): ("tdc", "list"),
    ("GET", "/art12"): ("art12", "list"),
    ("GET", "/art20"): ("art20", "list"),
    ("GET", "/comunicaciones"): ("comunicaciones", "list"),
    ("GET", "/dictamenes"): ("dictamenes", "list"),
    ("GET", "/esg/{rut}"): ("esg", "get"),
    ("GET", "/esg/rankings"): ("esg", "rankings"),
    ("GET", "/normativa/historic"): ("normativa_historic", "list"),
    ("POST", "/search"): ("search", "search"),
    # v0.6.0 — webhooks, exports, equity, sasb-topics, admin, sanctions x-ref
    ("GET", "/webhooks"): ("webhooks", "list"),
    ("POST", "/webhooks"): ("webhooks", "create"),
    ("GET", "/webhooks/{webhook_id}"): ("webhooks", "get"),
    ("PATCH", "/webhooks/{webhook_id}"): ("webhooks", "update"),
    ("DELETE", "/webhooks/{webhook_id}"): ("webhooks", "delete"),
    ("GET", "/webhooks/{webhook_id}/deliveries"): ("webhooks", "deliveries"),
    ("POST", "/webhooks/{webhook_id}/test"): ("webhooks", "test"),
    ("POST", "/exports/{resource}"): ("exports", "create"),
    ("GET", "/exports"): ("exports", "list"),
    ("GET", "/exports/{export_id}"): ("exports", "get"),
    ("DELETE", "/exports/{export_id}"): ("exports", "delete"),
    ("GET", "/equity/{ticker}/prices"): ("equity", "prices"),
    ("GET", "/sasb-topics"): ("sasb_topics", "list"),
    ("GET", "/admin/api-keys/me"): ("admin_api_keys", "me"),
    ("GET", "/resolve"): ("resolve", "resolve"),
    # v0.7.0 — 18 new resources + 4 extensions (54 endpoints)
    ("GET", "/banking/indicadores"): ("banking", "list_indicadores"),
    ("POST", "/copilot/ask"): ("copilot", "ask"),
    ("POST", "/copilot/ask-public"): ("copilot", "ask_public"),
    ("POST", "/copilot/ask/stream"): ("copilot", "ask_stream"),
    ("POST", "/copilot/ask-public/stream"): ("copilot", "ask_public_stream"),
    ("POST", "/copilot/uploads"): ("copilot", "upload_document"),
    ("GET", "/copilot/uploads/{document_id}"): ("copilot", "get_document"),
    ("GET", "/diario"): ("diario", "list_eventos"),
    ("GET", "/entities/{rut}/financials"): ("financials", "get_summary"),
    ("GET", "/entities/{rut}/financials/ratios"): ("financials", "get_ratios"),
    ("GET", "/entities/{rut}/financials/distress"): ("financials", "get_distress"),
    ("GET", "/entities/{rut}/financials/benchmark"): ("financials", "get_benchmark"),
    ("GET", "/entities/{rut}/financials/timeseries"): ("financials", "get_timeseries"),
    ("GET", "/entities/financials/distress/histogram"): ("financials", "get_distress_histogram"),
    ("GET", "/entities/financials/sector-stats"): ("financials", "get_sector_stats"),
    ("GET", "/fondos"): ("fondos", "list"),
    ("GET", "/fondos/{run}"): ("fondos", "get"),
    ("GET", "/graph/{rut}"): ("graph", "ego_network"),
    ("GET", "/graph/path"): ("graph", "shortest_path"),
    ("GET", "/graph/{rut}/centrality"): ("graph", "node_centrality"),
    ("GET", "/graph/centrality/distribution"): ("graph", "centrality_distribution"),
    ("POST", "/graph/centrality/batch"): ("graph", "centrality_batch"),
    ("GET", "/graph/edge/{edge_id}/detail"): ("graph", "edge_detail"),
    ("GET", "/graph/edge/{edge_id}/transactions"): ("graph", "edge_transactions"),
    ("POST", "/graph/nodes/attrs"): ("graph", "nodes_attrs"),
    ("GET", "/grupos/{rut}"): ("grupos", "get_by_rut"),
    ("GET", "/hechos"): ("hechos", "list_hechos"),
    ("GET", "/hechos/event-types"): ("hechos", "hechos_event_type_distribution"),
    ("GET", "/hechos/bancos"): ("hechos", "list_hechos_bancos"),
    ("GET", "/hechos/otros"): ("hechos", "list_hechos_otros"),
    ("GET", "/indicadores/{series_id}/forecast"): ("indicadores", "forecast"),
    ("GET", "/insider/{rut_or_persona}/profile"): ("insider", "get_profile"),
    ("GET", "/ipsa/risk-panel"): ("ipsa", "risk_panel"),
    ("GET", "/ipsa/{ticker}/risk"): ("ipsa", "ticker_risk"),
    ("GET", "/event-study/{ticker_or_rut}"): ("ipsa", "event_study"),
    ("GET", "/norms/top-cited"): ("norms", "top_cited"),
    ("GET", "/norms/{regulation_id}/citations"): ("norms", "citations"),
    ("GET", "/persons/{rut}/co-directors"): ("persons", "co_directors"),
    ("GET", "/sanctions/top-entities"): ("sanctions", "top_entities"),
    ("GET", "/ran"): ("ran", "list"),
    ("GET", "/entities/{rut}/ratings"): ("ratings", "get_entity_ratings"),
    ("GET", "/entities/{rut}/ratings-timeline"): ("ratings", "get_entity_ratings_timeline"),
    ("GET", "/ratings/distribution"): ("ratings", "get_ratings_distribution"),
    ("GET", "/ratings/migration"): ("ratings", "get_ratings_migration"),
    ("GET", "/regulations/{regulation_id}/lineage"): ("regulations", "lineage"),
    ("GET", "/rentas"): ("rentas", "list"),
    ("GET", "/scomp"): ("scomp", "list_estadisticas"),
    ("GET", "/screening/{rut}/exposure"): ("screening", "get_exposure"),
    ("GET", "/screening/exposure/distribution"): ("screening", "get_exposure_distribution"),
    ("GET", "/sii"): ("sii", "list"),
    ("POST", "/watchlist"): ("watchlist", "create"),
    ("GET", "/watchlist"): ("watchlist", "list"),
    ("GET", "/watchlist/{entry_id}"): ("watchlist", "get"),
    ("DELETE", "/watchlist/{entry_id}"): ("watchlist", "delete"),
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

# Endpoints acknowledged as live-but-unwrapped. Unlike IGNORED_PATHS these
# ARE user-facing ``/v1`` surfaces; they are listed here explicitly (with a
# reason) so the weekly drift cron does not page on a *known* backlog while
# still failing hard on any *new* endpoint that shows up unannounced.
#
#   * ``/copilot/conversations*`` (6 endpoints) — the Telar multi-device
#     conversation-sync surface. Payloads are client-side-encrypted blobs
#     produced by the web frontend; wrapping them in the SDK has no
#     standalone value (an SDK consumer cannot produce or read the
#     ciphertext). Deliberately not wrapped.
#   * ``/legal/search``, ``/regulatory-impact/{impact_id}``,
#     ``/regulatory-subscriptions`` (GET+PUT) — new regulatory surfaces
#     shipped server-side after 0.7.0; SDK wrappers are a follow-on
#     release (out of scope for the 0.8.0 series_id retype).
#
# Contract: keep this table SHRINKING. Every entry removed here must land
# as a RESOURCE_COVERAGE entry + SDK method in the same PR.
DEFERRED_COVERAGE: frozenset[tuple[str, str]] = frozenset(
    {
        ("GET", "/copilot/conversations"),
        ("POST", "/copilot/conversations"),
        ("POST", "/copilot/conversations/import"),
        ("GET", "/copilot/conversations/{conversation_id}"),
        ("PATCH", "/copilot/conversations/{conversation_id}"),
        ("DELETE", "/copilot/conversations/{conversation_id}"),
        ("GET", "/legal/search"),
        ("GET", "/regulatory-impact/{impact_id}"),
        ("GET", "/regulatory-subscriptions"),
        ("PUT", "/regulatory-subscriptions"),
    }
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

    deferred: list[Endpoint] = field(default_factory=list)
    """Live endpoints acknowledged in :data:`DEFERRED_COVERAGE` — reported
    for visibility but not counted as drift (see the table's docstring)."""

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
            "deferred": [[e.method, e.path] for e in self.deferred],
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
    exactly one of ``covered`` / ``uncovered_api`` / ``ignored`` /
    ``deferred``. Every SDK entry with no matching API endpoint becomes
    ``rotten_sdk``.
    """
    report = DriftReport()
    api_keys = {e.key() for e in api_endpoints}

    for endpoint in api_endpoints:
        if _is_ignored(endpoint.path):
            report.ignored.append(endpoint)
            continue
        if endpoint.key() in coverage:
            report.covered.append(endpoint)
        elif endpoint.key() in DEFERRED_COVERAGE:
            report.deferred.append(endpoint)
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
        help="Base URL of the Cerberus Compliance API (prod by default).",
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
    lines.append(f"Deferred      : {len(report.deferred)}")
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

    if report.deferred:
        lines.append("DEFERRED (live, acknowledged in DEFERRED_COVERAGE — not drift)")
        lines.append("-" * 72)
        for endpoint in report.deferred:
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
