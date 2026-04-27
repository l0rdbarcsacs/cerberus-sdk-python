"""Official Python SDK for the Cerberus Compliance API (Chile RegTech)."""

__version__ = "0.5.1"

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
from cerberus_compliance.resources.comunicaciones import (
    AsyncComunicacionesResource,
    ComunicacionesResource,
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
from cerberus_compliance.resources.indicadores import (
    AsyncIndicadoresResource,
    BCentralIndicatorName,
    IndicadoresResource,
    IndicatorName,
    SbifIndicatorName,
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
from cerberus_compliance.resources.opas import AsyncOPAsResource, OPAsResource
from cerberus_compliance.resources.persons import (
    AsyncPersonsResource,
    PersonEntityKind,
    PersonsResource,
)
from cerberus_compliance.resources.regulations import (
    AsyncRegulationsResource,
    RegulationsResource,
)
from cerberus_compliance.resources.resoluciones import (
    AsyncResolucionesResource,
    ResolucionesResource,
)
from cerberus_compliance.resources.rpsf import (
    AsyncRPSFResource,
    RPSFResource,
)
from cerberus_compliance.resources.sanctions import (
    AsyncSanctionsResource,
    SanctionsResource,
)
from cerberus_compliance.resources.sasb_topics import (
    AsyncSasbTopicsResource,
    SasbTopicsResource,
)
from cerberus_compliance.resources.search import (
    AsyncSearchClient,
    SearchClient,
    SearchFilters,
    SearchHit,
    SearchResponse,
)
from cerberus_compliance.resources.tdc import AsyncTDCResource, TDCResource
from cerberus_compliance.resources.webhooks import (
    AsyncWebhooksResource,
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
    "AsyncCerberusClient",
    "AsyncComunicacionesResource",
    "AsyncDictamenesResource",
    "AsyncESGResource",
    "AsyncEntitiesResource",
    "AsyncEquityResource",
    "AsyncExportsResource",
    "AsyncIndicadoresResource",
    "AsyncKYBResource",
    "AsyncNormativaConsultaResource",
    "AsyncNormativaHistoricResource",
    "AsyncNormativaResource",
    "AsyncOPAsResource",
    "AsyncPersonsResource",
    "AsyncRPSFResource",
    "AsyncRegulationsResource",
    "AsyncResolucionesResource",
    "AsyncSanctionsResource",
    "AsyncSasbTopicsResource",
    "AsyncSearchClient",
    "AsyncTDCResource",
    "AsyncWebhooksResource",
    "AuthError",
    "BCentralIndicatorName",
    "CerberusAPIError",
    "CerberusClient",
    "ComunicacionesResource",
    "DictamenesResource",
    "ESGRankingDirection",
    "ESGResource",
    "EntitiesResource",
    "EquityResource",
    "ExportsResource",
    "IndicadoresResource",
    "IndicatorName",
    "KYBResource",
    "NormativaConsultaEstado",
    "NormativaConsultaResource",
    "NormativaHistoricResource",
    "NormativaResource",
    "NotFoundError",
    "OPAsResource",
    "PersonEntityKind",
    "PersonsResource",
    "QuotaError",
    "RPSFResource",
    "RateLimitError",
    "RegulationsResource",
    "ResolucionesResource",
    "SanctionsResource",
    "SasbTopicsResource",
    "SbifIndicatorName",
    "SearchClient",
    "SearchFilters",
    "SearchHit",
    "SearchResponse",
    "ServerError",
    "TDCResource",
    "ValidationError",
    "WebhooksResource",
    "verify_webhook_signature",
]
