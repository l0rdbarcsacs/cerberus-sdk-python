"""Guard the public surface of the `cerberus_compliance` package.

Instances B/C/D wire sub-resources later; the top-level `__all__` must stay in
lockstep with the contract documented in the P4 plan so downstream imports
remain stable across releases.
"""

from __future__ import annotations

import cerberus_compliance

EXPECTED_ALL = {
    # v0.6.0 — API contract realignment (search, indicadores, webhooks)
    "SearchDateRange",
    "WebhookEventType",
    # v0.5.0 — P5.4.2 commercial extensions
    "AdminApiKeysResource",
    "AsyncAdminApiKeysResource",
    "AsyncEquityResource",
    "AsyncExportsResource",
    "AsyncSasbTopicsResource",
    "AsyncWebhooksResource",
    "BCentralIndicatorName",
    "ESGRankingDirection",
    "EquityResource",
    "ExportsResource",
    "IndicatorName",
    "PersonEntityKind",
    "SasbTopicsResource",
    "SbifIndicatorName",
    "WebhooksResource",
    "verify_webhook_signature",
    # v0.4.0 — P5.3 corpus + universal search
    "Art12Resource",
    "Art20Resource",
    "AsyncArt12Resource",
    "AsyncArt20Resource",
    "AsyncCerberusClient",
    "AsyncComunicacionesResource",
    "AsyncDictamenesResource",
    "AsyncESGResource",
    "AsyncEntitiesResource",
    "AsyncIndicadoresResource",
    "AsyncKYBResource",
    "AsyncNormativaConsultaResource",
    "AsyncNormativaHistoricResource",
    "AsyncNormativaResource",
    "AsyncOPAsResource",
    "AsyncPersonsResource",
    "AsyncRegulationsResource",
    "AsyncRPSFResource",
    "AsyncResolucionesResource",
    "AsyncResolveResource",
    "AsyncSanctionsResource",
    "AsyncSearchClient",
    "AsyncTDCResource",
    "AuthError",
    "CerberusAPIError",
    "CerberusClient",
    "ComunicacionesResource",
    "DictamenesResource",
    "ESGResource",
    "EntitiesResource",
    "IndicadoresResource",
    "KYBResource",
    "NormativaConsultaEstado",
    "NormativaConsultaResource",
    "NormativaHistoricResource",
    "NormativaResource",
    "NotFoundError",
    "OPAsResource",
    "PersonsResource",
    "QuotaError",
    "RateLimitError",
    "RegulationsResource",
    "RPSFResource",
    "ResolucionesResource",
    "ResolveResource",
    "SanctionsResource",
    "SearchClient",
    "SearchFilters",
    "SearchHit",
    "SearchResponse",
    "ServerError",
    "TDCResource",
    "ValidationError",
}


def test_version_is_v0_6_0() -> None:
    assert cerberus_compliance.__version__ == "0.6.0"


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


def test_dead_shims_are_gone() -> None:
    """v0.3.0 breaking change: the registries + material_events shims are removed.

    If these ever come back, ``__all__`` should not re-export them and
    attribute lookup on the package should fail.
    """
    for removed in (
        "RegistriesResource",
        "AsyncRegistriesResource",
        "MaterialEventsResource",
        "AsyncMaterialEventsResource",
        "RegistryType",
    ):
        assert removed not in cerberus_compliance.__all__
        assert not hasattr(cerberus_compliance, removed)
