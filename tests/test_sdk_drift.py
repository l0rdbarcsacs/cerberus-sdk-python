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
