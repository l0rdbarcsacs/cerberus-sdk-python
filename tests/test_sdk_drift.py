"""Guard: every entry in ``RESOURCE_COVERAGE`` must point to a real callable.

``scripts/check_sdk_drift.py`` ships a hand-maintained mapping of
``(HTTP method, OpenAPI path) -> (resource_attr, SDK method name)`` used
to diff the live OpenAPI spec against the SDK. If someone renames
``entities.by_rut`` without updating the mapping the drift CLI will
silently report "coverage OK" while the documented SDK method has gone
missing at runtime.

This test reloads :data:`scripts.check_sdk_drift.RESOURCE_COVERAGE` and
verifies every entry lands on an attribute of :class:`CerberusClient`
and a callable method on that attribute. It catches SDK renames the
next time `pytest` runs, long before the drift CLI would.

Implementation note
-------------------
``scripts/`` is not an importable package, so we use
``importlib.util.spec_from_file_location`` to load the script module
directly. If the indirection becomes painful, the long-term fix in
the review note is to move the table into
``cerberus_compliance/internal/coverage.py`` and import it both from
this test and the CLI. We deliberately stay with the awkward form now
so the guard ships in this PR.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
from types import ModuleType

import pytest

from cerberus_compliance import CerberusClient

SCRIPT_PATH = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "check_sdk_drift.py"


def _load_drift_module() -> ModuleType:
    """Load ``scripts/check_sdk_drift.py`` as an importable module.

    The script lives outside the ``cerberus_compliance`` package, so a
    plain ``import`` statement won't reach it. ``spec_from_file_location``
    bypasses ``sys.path`` and lets pytest exercise the real file the
    CI runs, without symlinking or adjusting ``sys.path``.

    We register the loaded module in ``sys.modules`` before executing
    it so that ``@dataclass`` (which resolves forward-reference
    annotations via ``sys.modules[cls.__module__].__dict__``) works —
    without this, dataclass construction raises ``AttributeError:
    'NoneType' object has no attribute '__dict__'`` on Python 3.12+.
    """
    spec = importlib.util.spec_from_file_location("check_sdk_drift", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        pytest.fail(f"could not load {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_resource_coverage_entries_are_live() -> None:
    """Every ``RESOURCE_COVERAGE`` entry must resolve to a callable method."""
    drift = _load_drift_module()
    # Dummy key is fine — we never actually dispatch a request; we only
    # introspect the resource attribute tree wired up in ``__init__``.
    client = CerberusClient(
        api_key="ck_test_dummy_for_introspection",
        base_url="https://mock.test/v1",
    )
    try:
        for (http_method, openapi_path), (
            resource_attr,
            method_name,
        ) in drift.RESOURCE_COVERAGE.items():
            resource = getattr(client, resource_attr, None)
            assert resource is not None, (
                f"client has no attribute '{resource_attr}' "
                f"(needed for {http_method} {openapi_path})"
            )
            method = getattr(resource, method_name, None)
            assert method is not None, (
                f"client.{resource_attr} has no method '{method_name}' "
                f"(needed for {http_method} {openapi_path})"
            )
            assert callable(method), (
                f"client.{resource_attr}.{method_name} is not callable "
                f"(needed for {http_method} {openapi_path})"
            )
    finally:
        client.close()


def test_resource_coverage_is_nonempty() -> None:
    """Sanity: the coverage table itself must not be accidentally emptied."""
    drift = _load_drift_module()
    assert len(drift.RESOURCE_COVERAGE) > 0, (
        "RESOURCE_COVERAGE is empty — did someone nuke the table?"
    )


def test_deferred_coverage_disjoint_from_resource_coverage() -> None:
    """A key in both tables means a stale DEFERRED entry — remove it.

    ``DEFERRED_COVERAGE``'s contract is to shrink: once an endpoint gains
    an SDK wrapper (a ``RESOURCE_COVERAGE`` entry) its deferred marker
    must be deleted in the same PR, otherwise the report would count it
    as covered while the deferred table lies about the backlog.
    """
    drift = _load_drift_module()
    overlap = set(drift.RESOURCE_COVERAGE) & set(drift.DEFERRED_COVERAGE)
    assert not overlap, f"stale DEFERRED_COVERAGE entries (already covered): {sorted(overlap)}"


def test_compute_drift_classifies_deferred_without_tripping_drift() -> None:
    """Deferred endpoints are reported but never counted as drift.

    A live endpoint listed in ``DEFERRED_COVERAGE`` lands in the
    ``deferred`` bucket (``has_drift`` stays ``False``), while a novel
    endpoint absent from every table still trips ``has_drift`` — the
    weekly cron must keep paging on *unannounced* API growth.
    """
    drift = _load_drift_module()
    deferred_method, deferred_path = next(iter(sorted(drift.DEFERRED_COVERAGE)))

    known = [drift.Endpoint(method=deferred_method, path=deferred_path)]
    report = drift.compute_drift(known)
    assert [e.key() for e in report.deferred] == [(deferred_method, deferred_path)]
    assert not report.uncovered_api
    # Every RESOURCE_COVERAGE entry is rotten here (empty live spec), so
    # has_drift is True for that reason — check the uncovered axis alone
    # by re-running with the full coverage keys present as live endpoints.
    live = known + [drift.Endpoint(method=m, path=p) for (m, p) in drift.RESOURCE_COVERAGE]
    report = drift.compute_drift(live)
    assert not report.has_drift
    assert report.to_json()["deferred"] == [[deferred_method, deferred_path]]

    novel = [*live, drift.Endpoint(method="GET", path="/definitely-new-endpoint")]
    report = drift.compute_drift(novel)
    assert report.has_drift
    assert [e.path for e in report.uncovered_api] == ["/definitely-new-endpoint"]
