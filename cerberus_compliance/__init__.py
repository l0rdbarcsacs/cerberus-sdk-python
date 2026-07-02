"""Official Python SDK for the Cerberus Compliance API (Chile RegTech)."""

__version__ = "0.8.0rc1"

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.errors import (
    AuthError,
    CerberusAPIError,
    NotFoundError,
    QuotaError,
    RateLimitError,
    ServerError,
    ValidationError,
)

# v0.5.0 — P5.4.2 commercial extensions ----------------------------------
from cerberus_compliance.resources.admin_api_keys import (
    AdminApiKeysResource,
    AsyncAdminApiKeysResource,
)
from cerberus_compliance.resources.art12 import Art12Resource, AsyncArt12Resource
from cerberus_compliance.resources.art20 import Art20Resource, AsyncArt20Resource
from cerberus_compliance.resources.banking import (
    AsyncBankingResource,
    BankingResource,
)
from cerberus_compliance.resources.comunicaciones import (
    AsyncComunicacionesResource,
    ComunicacionesResource,
)
from cerberus_compliance.resources.copilot import (
    AsyncCopilotResource,
    CopilotResource,
    CopilotStreamEvent,
)
from cerberus_compliance.resources.diario import (
    AsyncDiarioResource,
    DiarioEventoTipo,
    DiarioResource,
)
from cerberus_compliance.resources.dictamenes import (
    AsyncDictamenesResource,
    DictamenesResource,
)
from cerberus_compliance.resources.entities import (
    AsyncEntitiesResource,
    EntitiesResource,
)
from cerberus_compliance.resources.equity import AsyncEquityResource, EquityResource
from cerberus_compliance.resources.esg import (
    AsyncESGResource,
    ESGRankingDirection,
    ESGResource,
)
from cerberus_compliance.resources.exports import AsyncExportsResource, ExportsResource
from cerberus_compliance.resources.financials import (
    AsyncFinancialsResource,
    FinancialsResource,
)
from cerberus_compliance.resources.fondos import (
    AsyncFondosResource,
    FondosPeriodicidad,
    FondosResource,
)
from cerberus_compliance.resources.graph import (
    AsyncGraphResource,
    GraphResource,
)
from cerberus_compliance.resources.grupos import (
    AsyncGruposResource,
    GruposResource,
)
from cerberus_compliance.resources.hechos import (
    AsyncHechosResource,
    HechoEventType,
    HechosResource,
)
from cerberus_compliance.resources.indicadores import (
    AsyncIndicadoresResource,
    IndicadoresResource,
)
from cerberus_compliance.resources.insider import (
    AsyncInsiderResource,
    InsiderResource,
    InsiderSubjectType,
)
from cerberus_compliance.resources.ipsa import (
    AsyncIPSAResource,
    IPSAResource,
)
from cerberus_compliance.resources.kyb import (
    AsyncKYBResource,
    KYBResource,
)
from cerberus_compliance.resources.normativa import (
    AsyncNormativaResource,
    NormativaResource,
)
from cerberus_compliance.resources.normativa_consulta import (
    AsyncNormativaConsultaResource,
    NormativaConsultaEstado,
    NormativaConsultaResource,
)
from cerberus_compliance.resources.normativa_historic import (
    AsyncNormativaHistoricResource,
    NormativaHistoricResource,
)
from cerberus_compliance.resources.norms import (
    AsyncNormsResource,
    NormsResource,
)
from cerberus_compliance.resources.opas import AsyncOPAsResource, OPAsResource
from cerberus_compliance.resources.persons import (
    AsyncPersonsResource,
    PersonEntityKind,
    PersonsResource,
)
from cerberus_compliance.resources.ran import (
    AsyncRANResource,
    RANResource,
)
from cerberus_compliance.resources.ratings import (
    AsyncRatingsResource,
    RatingsDistributionType,
    RatingsResource,
)
from cerberus_compliance.resources.regulations import (
    AsyncRegulationsResource,
    RegulationsResource,
    RegulationType,
)
from cerberus_compliance.resources.rentas import (
    AsyncRentasResource,
    RentasResource,
)
from cerberus_compliance.resources.resoluciones import (
    AsyncResolucionesResource,
    ResolucionesResource,
)
from cerberus_compliance.resources.resolve import AsyncResolveResource, ResolveResource
from cerberus_compliance.resources.rpsf import (
    AsyncRPSFResource,
    RPSFResource,
)
from cerberus_compliance.resources.sanctions import (
    AsyncSanctionsResource,
    SancionEstado,
    SanctionsResource,
)
from cerberus_compliance.resources.sasb_topics import (
    AsyncSasbTopicsResource,
    SasbTopicsResource,
)
from cerberus_compliance.resources.scomp import (
    AsyncSCOMPResource,
    SCOMPResource,
)
from cerberus_compliance.resources.screening import (
    AsyncScreeningResource,
    ScreeningResource,
)
from cerberus_compliance.resources.search import (
    AsyncSearchClient,
    SearchClient,
    SearchDateRange,
    SearchFilters,
    SearchHit,
    SearchResponse,
)
from cerberus_compliance.resources.sii import (
    AsyncSIIResource,
    SIIResource,
)
from cerberus_compliance.resources.tdc import AsyncTDCResource, TDCResource
from cerberus_compliance.resources.watchlist import (
    AsyncWatchlistResource,
    WatchlistResource,
)
from cerberus_compliance.resources.webhooks import (
    AsyncWebhooksResource,
    WebhookEventType,
    WebhooksResource,
)

#: Convenience alias — verify a webhook signature without instantiating a
#: client.  The same function lives at ``WebhooksResource.verify_signature``.
verify_webhook_signature = WebhooksResource.verify_signature

__all__ = [
    "AdminApiKeysResource",
    "Art12Resource",
    "Art20Resource",
    "AsyncAdminApiKeysResource",
    "AsyncArt12Resource",
    "AsyncArt20Resource",
    "AsyncBankingResource",
    "AsyncCerberusClient",
    "AsyncComunicacionesResource",
    "AsyncCopilotResource",
    "AsyncDiarioResource",
    "AsyncDictamenesResource",
    "AsyncESGResource",
    "AsyncEntitiesResource",
    "AsyncEquityResource",
    "AsyncExportsResource",
    "AsyncFinancialsResource",
    "AsyncFondosResource",
    "AsyncGraphResource",
    "AsyncGruposResource",
    "AsyncHechosResource",
    "AsyncIPSAResource",
    "AsyncIndicadoresResource",
    "AsyncInsiderResource",
    "AsyncKYBResource",
    "AsyncNormativaConsultaResource",
    "AsyncNormativaHistoricResource",
    "AsyncNormativaResource",
    "AsyncNormsResource",
    "AsyncOPAsResource",
    "AsyncPersonsResource",
    "AsyncRANResource",
    "AsyncRPSFResource",
    "AsyncRatingsResource",
    "AsyncRegulationsResource",
    "AsyncRentasResource",
    "AsyncResolucionesResource",
    "AsyncResolveResource",
    "AsyncSCOMPResource",
    "AsyncSIIResource",
    "AsyncSanctionsResource",
    "AsyncSasbTopicsResource",
    "AsyncScreeningResource",
    "AsyncSearchClient",
    "AsyncTDCResource",
    "AsyncWatchlistResource",
    "AsyncWebhooksResource",
    "AuthError",
    "BankingResource",
    "CerberusAPIError",
    "CerberusClient",
    "ComunicacionesResource",
    "CopilotResource",
    "CopilotStreamEvent",
    "DiarioEventoTipo",
    "DiarioResource",
    "DictamenesResource",
    "ESGRankingDirection",
    "ESGResource",
    "EntitiesResource",
    "EquityResource",
    "ExportsResource",
    "FinancialsResource",
    "FondosPeriodicidad",
    "FondosResource",
    "GraphResource",
    "GruposResource",
    "HechoEventType",
    "HechosResource",
    "IPSAResource",
    "IndicadoresResource",
    "InsiderResource",
    "InsiderSubjectType",
    "KYBResource",
    "NormativaConsultaEstado",
    "NormativaConsultaResource",
    "NormativaHistoricResource",
    "NormativaResource",
    "NormsResource",
    "NotFoundError",
    "OPAsResource",
    "PersonEntityKind",
    "PersonsResource",
    "QuotaError",
    "RANResource",
    "RPSFResource",
    "RateLimitError",
    "RatingsDistributionType",
    "RatingsResource",
    "RegulationType",
    "RegulationsResource",
    "RentasResource",
    "ResolucionesResource",
    "ResolveResource",
    "SCOMPResource",
    "SIIResource",
    "SancionEstado",
    "SanctionsResource",
    "SasbTopicsResource",
    "ScreeningResource",
    "SearchClient",
    "SearchDateRange",
    "SearchFilters",
    "SearchHit",
    "SearchResponse",
    "ServerError",
    "TDCResource",
    "ValidationError",
    "WatchlistResource",
    "WebhookEventType",
    "WebhooksResource",
    "verify_webhook_signature",
]
