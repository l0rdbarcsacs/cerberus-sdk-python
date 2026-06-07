# Cerberus Compliance — SDK de Python

SDK oficial de Python para la API de Cerberus Compliance — inteligencia de cumplimiento y datos regulatorios (RegTech) sobre entidades fiscalizadas por la Comisión para el Mercado Financiero (CMF) de Chile.

[![PyPI](https://img.shields.io/pypi/v/cerberus-compliance.svg)](https://pypi.org/project/cerberus-compliance/)
[![Python](https://img.shields.io/pypi/pyversions/cerberus-compliance.svg)](https://pypi.org/project/cerberus-compliance/)
[![CI](https://github.com/l0rdbarcsacs/cerberus-sdk-python/actions/workflows/ci.yml/badge.svg)](https://github.com/l0rdbarcsacs/cerberus-sdk-python/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

---

## Qué es y qué resuelve

Cerberus Compliance consolida fuentes oficiales públicas de la CMF en una sola API de producción, de modo que usted obtenga, en una llamada, lo que de otro modo exigiría reunir y conciliar múltiples registros dispersos.

Este paquete (`cerberus-compliance`) es el cliente de Python tipado sobre esa API: le entrega clientes síncrono y asíncrono, modelos validados con Pydantic v2, paginación por cursor y una jerarquía de errores conforme a RFC 7807, con autocompletado y seguridad de tipos en su entorno de desarrollo.

Los dominios de datos que puede consumir, en lenguaje de cliente, incluyen:

- **KYB Express**: perfil consolidado de una empresa chilena (identidad, directorio, sanciones, identificador LEI, cadena de propiedad, autorización para operar y un puntaje de riesgo determinista) en una sola llamada.
- **Entidades y personas**: fichas de personas jurídicas y naturales identificadas por RUT, con directorio, cadena de propiedad, perfil regulatorio y cambios históricos.
- **Sanciones**: listas nacionales (CMF) e internacionales (OFAC, ONU, Unión Europea y Reino Unido), con referencia cruzada difusa por RUT o por nombre.
- **Normativa y regulaciones**: cuerpo normativo de la CMF (leyes, NCG, circulares, oficios), su aplicabilidad por entidad, versiones históricas y consultas públicas en trámite.
- **Registros regulatorios**: hechos esenciales (Art. 12 y Art. 20 de la Ley 18.045), OPAs, TDC, comunicaciones, dictámenes y resoluciones de la CMF.
- **Registro Público de Servicios Financieros (RPSF, Ley 21.521)**: prestadores autorizados, sus servicios y estado de inscripción.
- **ESG (NCG 461) y temas SASB**, **indicadores macro y financieros** (UF, UTM, USD, EUR, IPC, TMC, entre otros) y **precios bursátiles** de instrumentos chilenos e internacionales.
- **Búsqueda semántica universal** en lenguaje natural sobre todo el corpus documental de la CMF, **copiloto regulatorio** con respuestas fundamentadas y citas verificadas a la fuente, y un **grafo de conocimiento** de entidades (co-direcciones, propiedad y grupos económicos).

La plataforma está construida para Chile bajo la Ley 21.719 de protección de datos personales, con cifrado de datos personales en reposo y flujo de solicitudes ARSCO+.

---

## Modelo de acceso: plataforma, API y SDK

Los mismos datos están disponibles por tres canales sobre **una sola API de producción**. Usted elige el canal según su perfil; no son productos distintos, sino tres formas de acceder a la misma inteligencia.

| Canal | Punto de acceso | Credencial | Para quién |
|---|---|---|---|
| **Plataforma web (Explorer)** | `https://compliance.cerberus.cl/explorer` | Cuenta de usuario (inicio de sesión único con Google o GitHub en `/login`). Sin clave API; el acceso se asocia a su cuenta. | Equipos de cumplimiento, riesgo y negocio que desean explorar los datos de forma visual, sin escribir código. |
| **API REST** | `https://compliance.cerberus.cl/v1` | Clave API por cabecera Bearer: `Authorization: Bearer ck_live_<su-clave>` (entorno live o test). | Equipos de ingeniería que integran la inteligencia de cumplimiento en sistemas propios desde cualquier lenguaje, mediante HTTP estándar y la especificación OpenAPI publicada. |
| **SDK de Python (`cerberus-compliance`)** | Paquete PyPI `cerberus-compliance` (repositorio en GitHub: `https://github.com/l0rdbarcsacs/cerberus-sdk-python`); apunta a `https://compliance.cerberus.cl/v1`. | La misma clave API Bearer `ck_live_...` que la API REST; configúrela mediante la variable de entorno `CERBERUS_API_KEY` o al instanciar el cliente. | Equipos de desarrollo en Python que prefieren un cliente tipado (con `py.typed` y modelos Pydantic v2) sobre la misma API REST. |

**Este SDK es el cliente de Python sobre esa misma API REST.** Lo que obtenga por el SDK es exactamente lo que obtendría por HTTP directo o lo que vería en el Explorer.

### Cómo solicitar una clave API productiva

Inicie sesión en la Plataforma en `https://compliance.cerberus.cl/login` con su cuenta de Google o GitHub. Para acceso productivo, escriba a `contacto@cerberus.cl` —el mismo enlace «Acceso a producción» que ofrece la Plataforma— indicando el correo de su cuenta, su organización y el volumen estimado de consultas; le responderemos con las opciones de plan y le emitiremos una clave `ck_live_...` con el plan correspondiente.

La Plataforma permite un cupo diario de consultas gratuitas para evaluación —el cupo vigente se indica en la propia Plataforma—; para límites superiores, escríbanos a `contacto@cerberus.cl` (casilla organizacional).

---

## Instalación

```bash
pip install cerberus-compliance
```

Con `uv`:

```bash
uv add cerberus-compliance
```

Requiere Python 3.10 o superior. Las únicas dependencias en tiempo de ejecución del paquete cliente son `httpx` (`>=0.27,<1.0`) y `pydantic` (`>=2.6,<3.0`).

---

## Configuración

El cliente resuelve la clave API en este orden:

1. El argumento explícito `api_key=` cuando es una cadena no vacía.
2. La variable de entorno `CERBERUS_API_KEY` cuando es una cadena no vacía.
3. En caso contrario, lanza `ValueError` (`Cerberus API key not provided. Pass api_key= or set CERBERUS_API_KEY.`).

```bash
export CERBERUS_API_KEY="ck_live_<su-clave>"
```

```python
from cerberus_compliance import CerberusClient

# Resuelve la clave desde CERBERUS_API_KEY.
client = CerberusClient()

# O bien, de forma explícita y con parámetros de transporte:
client = CerberusClient(
    api_key="ck_live_<su-clave>",
    base_url="https://compliance.cerberus.cl/v1",  # valor por defecto
    timeout=30.0,                                   # segundos; valor por defecto
)
```

Parámetros del constructor (todos los de transporte son por palabra clave):

- `api_key: str | None = None` — se resuelve según el orden anterior.
- `base_url: str | None = None` — por defecto `https://compliance.cerberus.cl/v1`; se elimina la barra final.
- `timeout: float = 30.0` — segundos.
- `retry: RetryConfig | None = None` — por defecto `RetryConfig()` (véase «Manejo de errores»).
- `logger: logging.Logger | None = None` — por defecto el logger `cerberus_compliance`.
- `http_client` — cliente HTTP del paquete cliente, inyectable (la variante asíncrona acepta su contraparte asíncrona); cuando es `None`, el SDK construye el suyo.

### Cliente asíncrono

```python
import asyncio
from cerberus_compliance import AsyncCerberusClient

async def main() -> None:
    async with AsyncCerberusClient() as client:
        perfil = await client.kyb.get("76.123.456-7")
        print(perfil)

asyncio.run(main())
```

---

## Inicio rápido

Síncrono:

```python
from cerberus_compliance import CerberusClient

with CerberusClient() as client:
    perfil = client.kyb.get("76.123.456-7")
    print(perfil)
```

Asíncrono:

```python
import asyncio
from cerberus_compliance import AsyncCerberusClient

async def main() -> None:
    async with AsyncCerberusClient() as client:
        perfil = await client.kyb.get("76.123.456-7")
        print(perfil)

asyncio.run(main())
```

---

## KYB Express (endpoint estrella)

`client.kyb.get(rut, *, as_of=None, include=None)` devuelve el perfil consolidado de una empresa chilena —identidad, directorio vigente, sanciones, identificador LEI, cadena de propiedad, eventos materiales recientes y un puntaje de riesgo determinista de 0 a 100— en una sola llamada.

```python
from datetime import date
from cerberus_compliance import CerberusClient

with CerberusClient() as client:
    perfil = client.kyb.get(
        "76.123.456-7",
        as_of=date(2025, 12, 31),           # datetime.date; estado del perfil a una fecha dada (opcional)
        include=["directors", "lei", "sanctions"], # secciones a incluir (opcional)
    )
```

- `as_of` reconstruye el perfil tal como se conocía a la fecha indicada; acepta un `datetime.date` (se serializa en el protocolo como ISO-8601 `YYYY-MM-DD`), no una cadena. Si se omite, devuelve el estado más reciente.
- `include` permite acotar las secciones del documento que desea recibir.

Respuesta ilustrativa (los valores son **ilustrativos**; el RUT y la razón social corresponden a una empresa de ejemplo, no a una entidad real):

```jsonc
{
  "rut": "76.123.456-7",
  "rut_canonical": "76123456-7",
  "legal_name": "Empresa de Ejemplo S.A.",     // razón social ilustrativa
  "fantasy_name": "Ejemplo",
  "entity_kind": "sociedad_anonima_abierta",
  "status": "activo",
  "inscription_date": "1990-01-01",
  "lei": "5493000IBP32UQZ0KL24",               // identificador LEI ilustrativo
  "risk_score": 0,                             // puntaje determinista 0–100 (ilustrativo)
  "risk_factors": [],
  "directors_current": [
    { "persona_rut": "12.345.678-9", "nombre": "Persona de Ejemplo", "cargo": "presidente", "fecha_inicio": "2020-01-01" }
    // ...
  ],
  "sanctions": {                               // resumen; el detalle se obtiene con client.sanctions
    "active_count": 0,
    "historical_count": 0,
    "last_sanction_at": null,
    "last_sanction_summary": null
  },
  "rpsf_inscriptions": [],
  "recent_material_events": [
    { "id": "00000000-0000-0000-0000-000000000000", "publicacion_at": "2025-11-20T00:00:00Z", "asunto": "Hecho esencial de ejemplo" }
  ],
  "ownership_chain": { /* ... */ },
  "as_of": "2025-12-31",
  "request_id": "req_...",
  "cache_status": "live"
}
```

> Nota: en KYB Express, la sección `sanctions` es un **resumen** (conteo de sanciones activas e históricas). Para el detalle completo de sanciones de una entidad, utilice `client.sanctions` o `client.entities.sanctions(id_)`.

---

## Recursos tipados

Cada recurso se expone como un atributo del cliente (`client.<attr>`). Los recursos que listan colecciones ofrecen además `iter_all(**filters)` para recorrer todas las páginas automáticamente (véase «Paginación por cursor»).

### Entidades y personas

| Recurso | Endpoints | Métodos clave | Propósito |
|---|---|---|---|
| `client.entities` | `GET /entities`, `/entities/{id}`, `/entities/by-rut/{rut}`, `/entities/{id}/ownership`, `/entities/{id}/material-events`, `/entities/{id}/directors`, `/entities/{id}/regulations`, `/entities/{id}/diff`, `/sanctions/by-entity/{id}`, `/bancos/{rut}/fichas*` | `list(*, rut=None, limit=None)`, `get(id_)`, `by_rut(rut)`, `ownership(id_)`, `material_events(id_)`, `sanctions(id_)`, `directors(id_)`, `regulations(id_)`, `diff(entity_id, *, from_, to=None)`, `bancos_fichas(rut, *, year=None, month=None)`, `bancos_fichas_latest_per_section(rut)`, `bancos_fichas_latest(rut)`, `bancos_fichas_period(rut, fiscal_year, fiscal_month)` | Empresas y personas jurídicas chilenas (sociedades, fundaciones, bancos) por RUT, con propiedad, directorio, hechos esenciales y fichas bancarias. |
| `client.kyb` | `GET /kyb/{rut}` | `get(rut, *, as_of=None, include=None)` | Perfil KYB agregado de una empresa en un solo documento. |
| `client.persons` | `GET /persons`, `/persons/{rut}/regulatory-profile` | `list(*, pep=None, cargo=None, entity_kind=None, cursor=None, limit=None)`, `regulatory_profile(id_)` | Personas naturales con estado PEP, cargos y perfil de riesgo de cumplimiento. |
| `client.resolve` | `GET /resolve` | `resolve(*, query=None, rut=None, name=None)` | Resuelve texto libre, RUT o nombre a la entidad o persona canónica, con score de confianza. |

> `client.persons.get(id_)` está obsoleto: emite `DeprecationWarning` y lanza `NotImplementedError` (el endpoint nunca existió).

### Sanciones y normativa

| Recurso | Endpoints | Métodos clave | Propósito |
|---|---|---|---|
| `client.sanctions` | `GET /sanctions`, `/sanctions/{id}`, `/sanctions/cross-reference` | `list(*, target_id=None, source=None, active=None, limit=None)`, `get(id_)`, `cross_reference(*, rut=None, name=None, threshold=0.92, limit=50)` | Sanciones de OFAC, ONU, UE y CMF, con cruce difuso por RUT o nombre. |
| `client.regulations` | `GET /regulations`, `/regulations/{id}`, `/regulations/search` | `list(*, entity_id=None, framework=None, limit=None)`, `get(id_)`, `search(q, **params)` | Aplicabilidad regulatoria: qué marco normativo aplica a cada entidad y con qué estado. |
| `client.normativa` | `GET /normativa`, `/normativa/{id}`, `/normativa/{id}/mercado` | `list(**params)`, `get(id_)`, `mercado(id_)` | Textos regulatorios autoritativos con cita, resumen y mercado de aplicación. |
| `client.normativa_historic` | `GET /normativa/historic` | `list(**params)` | Historial de versiones punto-en-el-tiempo de los textos regulatorios de la CMF. |
| `client.normativa_consulta` | `GET /normativa-consulta` | `list(estado='abierta', limit=100, offset=0)` | Consultas públicas de normativa de la CMF (proyectos en trámite) como señal anticipada de obligaciones futuras. |

### Registros regulatorios de la CMF

| Recurso | Endpoints | Métodos clave | Propósito |
|---|---|---|---|
| `client.resoluciones` | `GET /resoluciones` | `list(**params)` | Resoluciones formales de la CMF (actos administrativos numerados). |
| `client.opas` | `GET /opas` | `list(**params)` | Ofertas Públicas de Adquisición (OPAs) reguladas por la CMF. |
| `client.tdc` | `GET /tdc` | `list(**params)` | Tasas de Descuento de Cartera (TDC) para valorización de carteras. |
| `client.art12` | `GET /art12` | `list(**params)` | Declaraciones del Art. 12 de la Ley 18.045 (participaciones significativas, 5%+). |
| `client.art20` | `GET /art20` | `list(**params)` | Hechos esenciales del Art. 20 de la Ley 18.045 (eventos corporativos materiales). |
| `client.comunicaciones` | `GET /comunicaciones` | `list(**params)` | Comunicaciones oficiales de la CMF (circulares, oficios y avisos numerados). |
| `client.dictamenes` | `GET /dictamenes` | `list(**params)` | Dictámenes (pronunciamientos legales formales) emitidos por la CMF. |

> En los recursos `resoluciones`, `opas`, `tdc`, `art12`, `art20`, `comunicaciones`, `dictamenes` y `normativa_historic`, el método `get(id_)` está obsoleto y lanza `NotImplementedError`: utilice `list(...)` con paginación.

### RPSF, ESG, indicadores y mercado

| Recurso | Endpoints | Métodos clave | Propósito |
|---|---|---|---|
| `client.rpsf` | `GET /rpsf`, `/rpsf/{id}`, `/rpsf/by-entity/{entity_id}`, `/rpsf/by-servicio/{servicio}` | `list(**params)`, `get(id_)`, `by_entity(id_)`, `by_servicio(servicio)` | Registro Público de Servicios Financieros (Ley 21.521): prestadores autorizados, servicios y estado de inscripción. |
| `client.esg` | `GET /esg/{rut}`, `/esg`, `/esg/rankings` | `get(rut)`, `list(**params)`, `rankings(*, indicator, year, top_n=20, direction='desc', industry=None)` | Perfil ambiental, social y de gobernanza (ESG) según la NCG 461, con rankings por indicador. |
| `client.sasb_topics` | `GET /sasb-topics` | `list(*, industry=None, limit=None, offset=None)`, `iter_all(*, industry=None)` | Catálogo de referencia de temas de divulgación SASB por industria. |
| `client.indicadores` | `GET /indicadores/{name}`, `/indicadores/{name}?from=&to=` | `get(name, date=None)`, `history(name, from_, to)` | Indicadores monetarios, de inflación y macroeconómicos (UF, UTM, USD, EUR, IPC, TMC, TPM, IMACEC, PIB...) como valores exactos en string. |
| `client.equity` | `GET /equity/{ticker}/prices` | `prices(ticker, *, from_=None, to=None)` | Series de precios bursátiles OHLCV de tickers chilenos e internacionales. |

### Operación y plataforma

| Recurso | Endpoints | Métodos clave | Propósito |
|---|---|---|---|
| `client.search` | `POST /search` | `search(*, query, filters=None, top_k=10)` | Búsqueda semántica universal sobre todo el corpus documental de la CMF (véase «Búsqueda semántica»). |
| `client.exports` | `POST /exports/{resource}`, `GET /exports/{export_id}`, `DELETE /exports/{export_id}`, `GET /exports` | `create(resource, *, format='csv', filters=None, fields=None)`, `get(export_id)`, `delete(export_id)`, `list(*, limit=50)`, `wait(export_id, *, poll_interval=2.0, timeout=120.0)` | Exportación masiva de cualquier familia de recursos a CSV o Parquet mediante una cola de trabajos con URL de descarga firmada. |
| `client.webhooks` | `POST /webhooks`, `GET /webhooks`, `GET /webhooks/{id}`, `PATCH /webhooks/{id}`, `DELETE /webhooks/{id}`, `GET /webhooks/{id}/deliveries`, `POST /webhooks/{id}/test` | `create(*, callback_url, event_types, description=None)`, `list()`, `get(webhook_id)`, `update(...)`, `delete(webhook_id)`, `deliveries(webhook_id, *, limit=50)`, `test(webhook_id)`, `verify_signature(...)` | Suscripciones a eventos de la plataforma con ciclo de vida completo y verificación de firma sin conexión (véase «Webhooks»). |
| `client.admin_api_keys` | `GET /admin/api-keys/me` | `me()` | Metadatos no secretos de la API key en uso: prefijo, entorno, tier, scopes, expiración y cuota mensual/diaria. |

---

## Búsqueda semántica

`client.search.search(...)` realiza una **búsqueda semántica sobre el corpus documental de la CMF** (resoluciones, OPAs, TDC, Art. 12 y Art. 20, comunicaciones, dictámenes, ESG, normativa y hechos esenciales) a partir de una consulta en lenguaje natural, y devuelve un `SearchResponse` con resultados rankeados.

```python
from cerberus_compliance import CerberusClient
from cerberus_compliance.resources.search import SearchFilters, SearchDateRange
# (también importables desde el top-level: from cerberus_compliance import SearchFilters, SearchDateRange)

with CerberusClient() as client:
    respuesta = client.search.search(
        query="cambios de control en bancos durante 2025",
        filters=SearchFilters(
            tipo_documento=["hecho_esencial"],
            marco_regulatorio=["Ley 18.045"],
            tipo_entidad_target=["banco"],
            materias=["cambio de control"],
            entity_rut="76.123.456-7",
            date_range=SearchDateRange(from_="2025-01-01", to="2025-12-31"),
        ),
        top_k=10,
    )

    print(respuesta.total_searched)        # número de documentos evaluados para esta consulta
    for hit in respuesta.hits:
        print(hit.score, hit.tipo_documento, hit.entity_rut)
        print(hit.payload)                 # contenido del documento coincidente
```

Modelos (`cerberus_compliance.resources.search`, también importables desde `cerberus_compliance`):

- **`SearchFilters`** — todos los campos son opcionales: `tipo_documento`, `marco_regulatorio`, `tipo_entidad_target`, `materias` (listas de cadenas), `entity_rut` (cadena) y `date_range`.
- **`SearchDateRange`** — `from_` (se serializa al campo de protocolo `from`) y `to`; aceptan `str` o `date`.
- **`SearchHit`** — `score`, `source_table` (colección de origen del documento), `source_row_id` (identificador único del documento de origen, UUID), `tipo_documento`, `marco_regulatorio`, `tipo_entidad_target`, `materias`, `entity_rut`, `publicacion_at` y `payload` (contenido del documento coincidente).
- **`SearchResponse`** — `query`, `hits` (lista de `SearchHit`) y `total_searched` (número de documentos evaluados para esta consulta).

El rango recomendado de `top_k` es de 1 a 40.

---

## Cobertura total de la API (v0.7.0)

Desde la versión **0.7.0**, el SDK envuelve la **totalidad de la superficie pública** de la API con recursos tipados (cobertura verificada contra el OpenAPI de producción: 0 endpoints sin envolver). Las capacidades que en versiones previas exigían el transporte de bajo nivel ahora se exponen como `client.<recurso>`:

| Recurso | Métodos clave | Propósito |
|---|---|---|
| `client.graph` | `ego_network(rut)`, `shortest_path(*, from_rut, to_rut)`, `node_centrality(rut)`, `centrality_distribution()`, `centrality_batch(ruts)`, `edge_detail(edge_id)`, `edge_transactions(edge_id, ...)`, `nodes_attrs(ruts)` | Grafo de conocimiento de entidades: co-direcciones, propiedad y grupos económicos (scope `graph:read`; la distribución agregada es pública, `entities:read`). |
| `client.copilot` | `ask(...)`, `ask_public(...)`, `ask_stream(...)`, `ask_public_stream(...)`, `upload_document(...)`, `get_document(id)` | Copiloto regulatorio con respuestas fundamentadas y citas («cite-or-refuse»), en JSON o por streaming (SSE), con documentos adjuntos opcionales. |
| `client.financials` | `get_summary(rut)`, `get_ratios(rut)`, `get_distress(rut)`, `get_benchmark(rut)`, `get_timeseries(rut)`, `get_distress_histogram()`, `get_sector_stats()` | Estados financieros IFRS, razones, indicadores de distress y comparación sectorial. |
| `client.ratings` | `get_entity_ratings(rut)`, `get_entity_ratings_timeline(rut)`, `get_ratings_distribution()`, `get_ratings_migration()` | Clasificaciones de riesgo oficiales, su evolución por agencia y su migración. |
| `client.screening` | `get_exposure(rut)`, `get_exposure_distribution()` | Exposición frente a listas de sanciones, incluida la exposición por contagio en la red. |
| `client.hechos` | `list_hechos(...)`, `list_hechos_bancos(...)`, `list_hechos_otros(...)`, `hechos_event_type_distribution()` | Hechos esenciales (emisores, bancos, otros) y su distribución por tipo. |
| `client.fondos` | `list(...)`, `get(run)` | Fondos mutuos y sus métricas. |
| `client.grupos` | `get_by_rut(rut)` | Grupos empresariales por RUT. |
| `client.insider` | `get_profile(rut_or_persona)` | Red de personas con información privilegiada (Art. 12). |
| `client.ipsa` | `risk_panel()`, `ticker_risk(ticker)`, `event_study(ticker_or_rut)` | Panel de riesgo del IPSA y estudios de evento de mercado. |
| `client.banking` | `list_indicadores(...)` | Indicadores prudenciales bancarios. |
| `client.norms` | `top_cited(...)`, `citations(regulation_id)` | Normas más citadas y red de citaciones normativas. |
| `client.diario` · `client.ran` · `client.rentas` · `client.scomp` · `client.sii` | `list(...)` / `list_*(...)` (+ `iter_all` donde aplica) | Diario Oficial, RAN, rentas vitalicias, estadísticas SCOMP y nóminas SII. |
| `client.watchlist` | `list()`, `create(...)`, `get(entry_id)`, `delete(entry_id)` | Listas de seguimiento (CRUD). |

Además, recursos existentes ganaron métodos: `client.indicadores.forecast(name)` (proyección), `client.regulations.lineage(id)`, `client.persons.co_directors(rut)` y `client.sanctions.top_entities()`.

### Copiloto: respuesta directa o por streaming

```python
from cerberus_compliance import CerberusClient

with CerberusClient() as client:
    # Respuesta completa (JSON), con política cite-or-refuse:
    res = client.copilot.ask("¿Qué exige la NCG 461 en materia de gobernanza?")
    print(res["kind"], res["answer"])      # 'grounded' | 'refusal' | 'conversational'
    for cita in res["citations"]:
        print(cita["source_table"], cita["title"])

    # Streaming incremental (Server-Sent-Events) → CopilotStreamEvent:
    for evento in client.copilot.ask_stream("Resuma la NCG 461"):
        if evento.event == "delta":
            print(evento.data["text"], end="")
        elif evento.event == "answer":
            final = evento.data            # objeto de respuesta canónico
```

> El copiloto se invoca con su clave `ck_live_...`. `ask` / `ask_stream` (scope `copilot:read`) operan sobre todo el corpus indexado; `ask_public` / `ask_public_stream` (scope `regulations:read`) responden únicamente sobre normativa pública.

> Para cualquier endpoint aún no presente en su versión del SDK, el transporte de bajo nivel `client._request(method, path, *, params=..., json=...)` sigue disponible y aplica la misma autenticación, reintentos y manejo de errores.

---

## Autenticación, planes, límites y cuotas

La autenticación es por cabecera Bearer, inyectada en cada petición:

```
Authorization: Bearer ck_live_<su-clave>
```

La clave es una cadena opaca, no vacía; existen entornos `live` y `test`. El SDK la envía tal cual, sin modificarla.

Los planes son cualitativos y se asignan al emitir su clave:

| Plan | Orientación |
|---|---|
| `free` | Plan de evaluación con límites de tasa conservadores y cuota diaria/mensual reducida, para pruebas iniciales. |
| `starter` | Plan de entrada con mayor tasa por segundo y cuotas adecuadas para integraciones pequeñas en producción. |
| `professional` | Plan de uso intensivo con tasa por segundo elevada y cuotas amplias para cargas de producción sostenidas. |
| `enterprise` | Plan corporativo con la tasa por segundo más alta y volumen sin tope práctico, para integraciones a gran escala. |

Cada plan combina un **límite de tasa** (peticiones por segundo) con una **cuota** (consumo diario y mensual). Los límites vigentes de su clave se consultan en línea, sin exponer la clave secreta:

```python
with CerberusClient() as client:
    meta = client.admin_api_keys.me()   # GET /v1/admin/api-keys/me
    print(meta)  # prefijo, entorno, tier, scopes, expiración y cuota restante
```

Los mismos límites y su consumo están visibles en el portal autenticado. Para una cuota superior, escríbanos por la vía descrita en «Modelo de acceso».

---

## Manejo de errores

Toda respuesta no exitosa se traduce a una excepción de la jerarquía `CerberusAPIError`. La clase base es una `dataclass` que transporta:

- `.status: int` — código HTTP.
- `.problem: dict` — cuerpo RFC 7807 (`application/problem+json`) ya deserializado.
- `.request_id: str | None` — del encabezado `X-Request-Id`.
- Propiedades `.title`, `.detail`, `.type`, `.instance` derivadas de `problem` (con respaldo en la frase de estado HTTP cuando faltan).

| Excepción | Estado | Cuándo |
|---|---|---|
| `CerberusAPIError` | cualquier no-2xx | Clase base; también el respaldo para estados no mapeados que no sean 5xx. |
| `AuthError` | 401, 403 | No autorizado o prohibido. |
| `QuotaError` | 402 | Cuota agotada. |
| `NotFoundError` | 404 | Recurso inexistente (lo distingue de fallos de autenticación o transitorios). |
| `ValidationError` | 422 | Entidad no procesable. Propiedad extra `.errors` (lista de detalles de validación). |
| `RateLimitError` | 429 | Demasiadas peticiones. Campo extra `.retry_after: float | None` (segundos), tomado del encabezado `Retry-After`. |
| `ServerError` | 5xx (500–599) | Cualquier error de servidor. |

```python
from cerberus_compliance import CerberusClient
from cerberus_compliance.errors import (
    CerberusAPIError,
    AuthError,
    QuotaError,
    NotFoundError,
    ValidationError,
    RateLimitError,
    ServerError,
)

with CerberusClient() as client:
    try:
        perfil = client.kyb.get("76.123.456-7")
    except NotFoundError:
        perfil = None
    except RateLimitError as exc:
        print(f"Reintente en {exc.retry_after} s")
        raise
    except AuthError as exc:
        print(f"Credencial inválida: {exc.title} (request_id={exc.request_id})")
        raise
    except CerberusAPIError as exc:
        print(f"Error {exc.status}: {exc.detail}")
        raise
```

### Reintentos automáticos

El cliente reintenta de forma automática los fallos transitorios. La política se controla con `RetryConfig`, una `dataclass` inmutable que valida sus campos en construcción:

```python
from cerberus_compliance import CerberusClient
from cerberus_compliance.retry import RetryConfig

client = CerberusClient(
    retry=RetryConfig(
        max_attempts=3,                          # presupuesto total de intentos (>=1; 1 = sin reintentos)
        base_delay_ms=200,                       # retardo del primer reintento, en ms
        max_delay_ms=10_000,                     # techo por espera individual, en ms
        retry_on=(429, 500, 502, 503, 504),      # estados que se reintentan
        jitter=True,                             # jitter aleatorio sobre el backoff exponencial
    )
)
```

Se reintentan los estados `429`, `500`, `502`, `503` y `504`, así como los errores de transporte de red (tratados como un `503` sintético para la decisión de reintento). El backoff es exponencial con jitter; cuando hay un encabezado `Retry-After` numérico, este tiene prioridad sobre el cálculo exponencial. Agotados los reintentos, propaga la excepción correspondiente.

---

## Paginación por cursor

Los recursos de colección exponen `iter_all(**filters)`, que recorre todas las páginas hacia adelante y entrega las filas una a una. En la variante síncrona es un generador (`Iterator[dict]`); en la asíncrona, un generador asíncrono (`AsyncIterator[dict]`).

El SDK normaliza de forma transparente la estructura de respuesta, leyendo tanto la forma `{ "items": [...], "next_cursor": "...", "limit": N }` como la forma `{ "data": [...], "next": "..." }`. La iteración se detiene cuando no hay cursor siguiente.

```python
from cerberus_compliance import CerberusClient

with CerberusClient() as client:
    for empresa in client.entities.iter_all(rut="76.123.456-7"):
        print(empresa["id"])
```

```python
import asyncio
from cerberus_compliance import AsyncCerberusClient

async def main() -> None:
    async with AsyncCerberusClient() as client:
        async for sancion in client.sanctions.iter_all(active=True):
            print(sancion["id"])

asyncio.run(main())
```

---

## Webhooks

Suscríbase a eventos de la plataforma y verifique cada entrega **sin conexión**. El secreto de firma se entrega en texto plano una sola vez, al crear el webhook.

```python
from cerberus_compliance import CerberusClient

with CerberusClient() as client:
    wh = client.webhooks.create(
        callback_url="https://su-sistema.example.cl/cerberus/webhook",
        event_types=["hecho_esencial.new", "sancion.new"],
        description="Alertas de hechos esenciales y sanciones",
    )
    secreto = wh["secret"]  # guárdelo de forma segura: se muestra una sola vez
```

Verificación sin conexión de una entrega entrante (HMAC-SHA256 sobre el encabezado `X-Cerberus-Signature`, con formato `t=<unix_ts>,v1=<hex_hmac>`):

```python
from cerberus_compliance import verify_webhook_signature

es_valida = verify_webhook_signature(
    payload=cuerpo_crudo,                 # bytes
    signature_header=cabecera_firma,      # str: 't=<unix_ts>,v1=<hex_hmac>'
    secret=secreto,                       # str
    max_age_seconds=300,                  # tolerancia de frescura, en segundos
)
```

Devuelve `True` solo si la firma es válida y reciente; nunca lanza excepción ante un encabezado malformado.

Tipos de evento (`WebhookEventType`):

`hecho_esencial.new`, `sancion.new`, `resolucion.new`, `tdc.new`, `dictamen.new`, `comunicacion.new`, `opa.new`, `art12.new`, `art20.new`, `entity.changed`, `ping`.

El estado de un webhook (`WebhookStatus`) es `active` o `disabled`.

---

## Ejemplos

El repositorio incluye ejemplos ejecutables en `examples/`:

| Archivo | Qué muestra |
|---|---|
| `kyb_quickstart.py` | Inicio rápido de KYB con el SDK. |
| `entities_lookup.py` | Resuelve una entidad chilena de extremo a extremo por la superficie `client.entities`. |
| `persons_profile.py` | Obtiene el perfil regulatorio de una persona natural. |
| `sanctions_browse.py` | Navega sanciones CMF mediante el recurso `client.sanctions`. |
| `sanctions_cross_reference.py` | Cruza una persona contra OFAC SDN, ONU Consolidada y listas CMF. |
| `regulations_search.py` | Navega y busca por texto completo el catálogo de regulaciones de la CMF. |
| `normativa_explore.py` | Explora el catálogo de textos regulatorios mediante `client.normativa`. |
| `normativa_consulta_basic.py` | Navega las consultas de normativa de la CMF (proyectos abiertos y cerrados). |
| `rpsf_explore.py` | Explora el Registro Público de Servicios Financieros (RPSF). |
| `indicadores_basic.py` | Obtiene indicadores de la CMF (UF, UTM, USD, EUR, IPC, TMC). |
| `equity_prices.py` | Descarga el OHLCV diario del IPSA-25 mediante el endpoint de equity. |
| `sasb_topics_browse.py` | Navega la taxonomía de temas SASB Standards 2018. |
| `cursor_pagination.py` | Tres idiomas de paginación por cursor sobre `iter_all`. |
| `exports_bulk_csv.py` | Dispara una exportación masiva CSV y descarga el resultado. |
| `error_handling.py` | Recorre cada excepción de la jerarquía `CerberusAPIError`. |
| `admin_api_keys_introspect.py` | Inspecciona los metadatos (tier/cuota) de la API key en uso mediante `client.admin_api_keys.me`. |
| `async_concurrent_lookups.py` | Consultas KYB concurrentes sobre una cartera de 5 RUT con `AsyncCerberusClient`. |
| `monitor_portfolio.py` | Monitor asíncrono de una cartera contra la API. |
| `webhooks_subscribe_and_verify.py` | Suscribe un webhook y verifica sin conexión una firma entrante. |
| `webhook_handler.py` | Ejemplo de endpoint receptor de webhooks (servidor HTTP, cualquier framework ASGI) para eventos salientes de Cerberus. |

---

## Compatibilidad y tipado

- Versión actual del SDK: **0.7.0**.
- Python **3.10 o superior** (clasificadores para 3.10, 3.11 y 3.12).
- El paquete distribuye `py.typed`: los modelos y firmas están completamente anotados y se verifican con `mypy` en modo estricto.
- Dependencias en tiempo de ejecución del paquete cliente: `httpx` (`>=0.27,<1.0`) y `pydantic` (`>=2.6,<3.0`).
- El control de deriva entre el SDK y la API se verifica con `scripts/check_sdk_drift.py`, de modo que la superficie tipada se mantenga alineada con la especificación publicada.

---

## Contribuir

```bash
git clone https://github.com/l0rdbarcsacs/cerberus-sdk-python.git
cd cerberus-sdk-python
pip install -e ".[dev]"

pytest          # pruebas
mypy .          # verificación estática de tipos
ruff check .    # estilo y linting
```

---

## Enlaces

- **PyPI**: https://pypi.org/project/cerberus-compliance/
- **Repositorio**: https://github.com/l0rdbarcsacs/cerberus-sdk-python
- **Plataforma (Explorer)**: https://compliance.cerberus.cl/explorer
- **Documentación OpenAPI**: https://compliance.cerberus.cl/docs
- **Portal de desarrolladores**: https://developers.cerberus.cl
- **CHANGELOG**: https://github.com/l0rdbarcsacs/cerberus-sdk-python/blob/main/CHANGELOG.md

---

## Licencia

El código de este SDK se distribuye bajo licencia **MIT**: es un cliente de código abierto que usted puede usar, modificar y redistribuir libremente. El acceso a los datos y al servicio de Cerberus Compliance es **comercial** y se rige por las condiciones del plan asociado a su clave API; el carácter abierto del cliente no confiere acceso a los datos.
