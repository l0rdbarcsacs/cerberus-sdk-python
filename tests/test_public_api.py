"""Guard the public surface of the `cerberus_compliance` package.

Instances B/C/D wire sub-resources later; the top-level `__all__` must stay in
lockstep with the contract documented in the P4 plan so downstream imports
remain stable across releases.
"""

from __future__ import annotations

import cerberus_compliance

EXPECTED_ALL = {
    "AsyncCerberusClient",
    "AsyncEntitiesResource",
    "AsyncKYBResource",
    "AsyncMaterialEventsResource",
    "AsyncNormativaResource",
    "AsyncPersonsResource",
    "AsyncRegistriesResource",
    "AsyncRegulationsResource",
    "AsyncRPSFResource",
    "AsyncSanctionsResource",
    "AuthError",
    "CerberusAPIError",
    "CerberusClient",
    "EntitiesResource",
    "KYBResource",
    "MaterialEventsResource",
    "NormativaResource",
    "NotFoundError",
    "PersonsResource",
    "QuotaError",
    "RateLimitError",
    "RegistriesResource",
    "RegulationsResource",
    "RPSFResource",
    "SanctionsResource",
    "ServerError",
    "ValidationError",
}


def test_version_is_semver_0_2_0() -> None:
    assert cerberus_compliance.__version__ == "0.2.0"


def test_all_matches_expected_surface() -> None:
    assert set(cerberus_compliance.__all__) == EXPECTED_ALL


def test_all_entries_are_importable_from_top_level() -> None:
    for name in cerberus_compliance.__all__:
        assert hasattr(cerberus_compliance, name), f"missing top-level export: {name}"


def test_error_subclasses_inherit_from_base() -> None:
    from cerberus_compliance import (
        AuthError,
        CerberusAPIError,
        NotFoundError,
        QuotaError,
        RateLimitError,
        ServerError,
        ValidationError,
    )

    for sub in (AuthError, NotFoundError, ValidationError, QuotaError, RateLimitError, ServerError):
        assert issubclass(sub, CerberusAPIError)


def test_client_classes_exposed() -> None:
    from cerberus_compliance import AsyncCerberusClient, CerberusClient

    assert CerberusClient.__name__ == "CerberusClient"
    assert AsyncCerberusClient.__name__ == "AsyncCerberusClient"
