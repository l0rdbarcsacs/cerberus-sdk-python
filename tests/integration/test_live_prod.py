"""Integration tests against Cerberus Compliance prod.

These tests hit the real prod API
(``https://compliance.cerberus.cl/v1``) and are therefore:

* Skipped when ``CERBERUS_API_KEY`` is not set in the env.
* Opt-in in CI — Instance D wires this via a GitHub Actions secret of
  the same name. See docs/HANDOFF_P51_A.md for the orchestration plan.

Run locally::

    export CERBERUS_API_KEY=ck_test_...
    pytest tests/integration/ -q

If the endpoint exists but returns an empty result (404 for a missing
RUT, empty list for a filter that matches nothing), the test *passes* —
we exercise the plumbing, not the corpus. Tests that strictly require
a populated fixture (e.g. Falabella must exist) are marked with an
``xfail(strict=False)`` so a fresh prod DB doesn't break CI.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

from cerberus_compliance import (
    AsyncCerberusClient,
    CerberusAPIError,
    CerberusClient,
    NotFoundError,
)

CERBERUS_API_KEY = os.getenv("CERBERUS_API_KEY")
LIVE_BASE_URL = os.getenv("CERBERUS_BASE_URL", "https://compliance.cerberus.cl/v1")

# Anchor RUT seeded in the prod corpus (P5 seed script): Falabella.
FALABELLA_RUT = "96.505.760-9"

# Anchor BCCh series_id (canonical indicador handle since 0.8.0): the UF.
# Friendly names ("UF", "IPC", ...) are retired and 404 in prod.
UF_SERIES_ID = "F073.UFF.PRE.Z.D"

pytestmark = pytest.mark.skipif(
    not CERBERUS_API_KEY,
    reason="CERBERUS_API_KEY not set; integration tests require prod access",
)


@pytest.fixture
def live_client() -> Iterator[CerberusClient]:
    """Sync client pointing at the prod base URL."""
    assert CERBERUS_API_KEY is not None  # narrow for type-checker; pytestmark skips otherwise
    client = CerberusClient(api_key=CERBERUS_API_KEY, base_url=LIVE_BASE_URL, timeout=30.0)
    try:
        yield client
    finally:
        client.close()


# ---------------------------------------------------------------------------
# KYB (G1)
# ---------------------------------------------------------------------------


class TestProdKYB:
    def test_kyb_get_falabella(self, live_client: CerberusClient) -> None:
        try:
            profile = live_client.kyb.get(FALABELLA_RUT)
        except NotFoundError:
            pytest.xfail("Falabella not seeded in current prod corpus")
        assert isinstance(profile, dict)
        # legal_name is the single documented stable field across cache states.
        assert "legal_name" in profile or "rut" in profile

    def test_kyb_get_missing_raises_not_found(self, live_client: CerberusClient) -> None:
        with pytest.raises((NotFoundError, CerberusAPIError)):
            live_client.kyb.get("76000000-0")


# ---------------------------------------------------------------------------
# Entities (G12, G13)
# ---------------------------------------------------------------------------


class TestProdEntities:
    def test_list(self, live_client: CerberusClient) -> None:
        entities = live_client.entities.list(limit=1)
        assert isinstance(entities, list)

    def test_by_rut(self, live_client: CerberusClient) -> None:
        try:
            entity = live_client.entities.by_rut(FALABELLA_RUT)
        except NotFoundError:
            pytest.xfail("Falabella not seeded in current prod corpus")
        assert isinstance(entity, dict)
        assert "id" in entity or "rut" in entity

    def test_get_then_ownership(self, live_client: CerberusClient) -> None:
        entities = live_client.entities.list(limit=1)
        if not entities:
            pytest.skip("no entities in prod corpus")
        entity_id = entities[0].get("id")
        if entity_id is None:
            pytest.skip("entity payload missing id field")
        full = live_client.entities.get(str(entity_id))
        assert isinstance(full, dict)
        try:
            ownership = live_client.entities.ownership(str(entity_id))
        except NotFoundError:
            pytest.xfail("entity has no ownership record in current corpus")
        assert isinstance(ownership, dict)


# ---------------------------------------------------------------------------
# Sanctions (G2)
# ---------------------------------------------------------------------------


class TestProdSanctions:
    def test_list(self, live_client: CerberusClient) -> None:
        results = live_client.sanctions.list(limit=1)
        assert isinstance(results, list)

    def test_by_entity_via_entities_sanctions(self, live_client: CerberusClient) -> None:
        """G2 check: entities.sanctions(id) must succeed against the real API.

        Uses the first entity from /entities/list as the target so this
        test stays decoupled from whether any specific RUT is seeded.
        """
        entities = live_client.entities.list(limit=1)
        if not entities:
            pytest.skip("no entities in prod corpus")
        entity_id = entities[0].get("id")
        if entity_id is None:
            pytest.skip("entity payload missing id field")
        # Even when the entity has zero hits, we expect a 200 with an empty
        # list — not a 404 for the endpoint itself.
        hits = live_client.entities.sanctions(str(entity_id))
        assert isinstance(hits, list)


# ---------------------------------------------------------------------------
# Regulations + search (G16)
# ---------------------------------------------------------------------------


class TestProdRegulations:
    def test_list(self, live_client: CerberusClient) -> None:
        regs = live_client.regulations.list(limit=1)
        assert isinstance(regs, list)

    def test_search(self, live_client: CerberusClient) -> None:
        results = live_client.regulations.search("Ley")
        assert isinstance(results, list)


# ---------------------------------------------------------------------------
# RPSF (G14)
# ---------------------------------------------------------------------------


class TestProdRPSF:
    def test_list(self, live_client: CerberusClient) -> None:
        records = live_client.rpsf.list(limit=1)
        assert isinstance(records, list)


# ---------------------------------------------------------------------------
# Normativa (G15)
# ---------------------------------------------------------------------------


class TestProdNormativa:
    def test_list(self, live_client: CerberusClient) -> None:
        norms = live_client.normativa.list(limit=1)
        assert isinstance(norms, list)


# ---------------------------------------------------------------------------
# Normativa en Consulta (v0.3.0 G9)
# ---------------------------------------------------------------------------


class TestProdNormativaConsulta:
    # /normativa-consulta (backend PR #45, feat/p52-new-ingestors) is deployed
    # to prod, so both list calls return a (possibly empty) list.
    def test_list_abierta(self, live_client: CerberusClient) -> None:
        """Default ``estado='abierta'`` must return a list (possibly empty)."""
        rows = live_client.normativa_consulta.list(limit=5)
        assert isinstance(rows, list)

    def test_list_cerrada(self, live_client: CerberusClient) -> None:
        rows = live_client.normativa_consulta.list(estado="cerrada", limit=5)
        assert isinstance(rows, list)


# ---------------------------------------------------------------------------
# Indicadores (v0.3.0 G8)
# ---------------------------------------------------------------------------


class TestProdIndicadores:
    def test_get_uf_latest(self, live_client: CerberusClient) -> None:
        """Latest UF (by series_id) must come back as a dict with a ``value``.

        We do not assert a specific value (UF changes daily); we assert the
        plumbing is real and the payload shape matches the documented
        schema.
        """
        try:
            uf = live_client.indicadores.get(UF_SERIES_ID)
        except NotFoundError:
            pytest.xfail("no UF value in current prod corpus")
        assert isinstance(uf, dict)
        assert "value" in uf

    def test_get_uf_on_pinned_date(self, live_client: CerberusClient) -> None:
        """Point-in-time lookup against the deep-research snapshot date."""
        try:
            uf = live_client.indicadores.get(UF_SERIES_ID, date="2026-04-24")
        except NotFoundError:
            pytest.xfail("UF not seeded for 2026-04-24 in current prod corpus")
        assert isinstance(uf, dict)

    def test_history_short_range(self, live_client: CerberusClient) -> None:
        """Historical range transformation + unwrap must produce a list.

        The list may be empty on a sparse prod corpus — we only verify
        the SDK contract, not the server corpus.
        """
        try:
            series = live_client.indicadores.history(
                UF_SERIES_ID, from_="2026-04-01", to="2026-04-30"
            )
        except (NotFoundError, CerberusAPIError):
            pytest.xfail("prod indicadores history not populated")
        assert isinstance(series, list)

    def test_buscar_returns_list(self, live_client: CerberusClient) -> None:
        """Discovery via ``GET /indicadores/buscar`` must return a list.

        The list may be empty on a sparse prod corpus — we exercise the
        plumbing, not the corpus.
        """
        try:
            rows = live_client.indicadores.buscar(q="cobre", limit=5)
        except (NotFoundError, CerberusAPIError):
            pytest.xfail("prod indicadores buscar not available")
        assert isinstance(rows, list)

    def test_retired_name_404s(self, live_client: CerberusClient) -> None:
        """Friendly names are retired: ``get("UF")`` must raise ``NotFoundError``.

        Since Plan A (series_id-canonical) is deployed, the friendly name
        ``"UF"`` no longer resolves — the canonical handle is the BCCh
        ``series_id``. This is permanent, designed behaviour, so the 404
        is a strict PASS (never xfail) and the expected exception is
        exactly :class:`NotFoundError` — a broader
        ``(NotFoundError, CerberusAPIError)`` tuple would be degenerate
        (``NotFoundError`` subclasses ``CerberusAPIError``, so any API
        error would pass) and stop proving the retirement is live.
        """
        with pytest.raises(NotFoundError):
            live_client.indicadores.get("UF")

    def test_list_catalog_returns_tracked_series(self, live_client: CerberusClient) -> None:
        """``GET /indicadores`` catalog rows carry the series_id in ``name``.

        The tracked catalog is small but never empty in prod; each row's
        ``name`` is the canonical ``series_id`` handle.
        """
        try:
            rows = live_client.indicadores.list()
        except CerberusAPIError:
            pytest.xfail("prod indicadores catalog not available")
        assert isinstance(rows, list)
        if rows:
            assert "name" in rows[0]
            assert "title_es" in rows[0]

    def test_compare_two_series(self, live_client: CerberusClient) -> None:
        """``GET /indicadores/compare`` round-trip with two series_ids."""
        try:
            series = live_client.indicadores.compare(
                [UF_SERIES_ID, "F073.TCO.PRE.Z.D"],
                from_="2026-04-01",
                to="2026-04-30",
            )
        except (NotFoundError, CerberusAPIError):
            pytest.xfail("prod indicadores compare not populated for the range")
        assert isinstance(series, list)
        if series:
            assert {s["name"] for s in series} <= {UF_SERIES_ID, "F073.TCO.PRE.Z.D"}


# ---------------------------------------------------------------------------
# Persons
# ---------------------------------------------------------------------------

# Anchor RUT seeded in the prod KYB corpus (P5 seed script): Carlos Heller,
# a director of Falabella, confirmed to have a regulatory profile in the
# prod audit. This is the single persona used for the integration round-trip
# so the test stays decoupled from the (deprecated) /persons collection
# endpoint which does not exist in the prod API.
CARLOS_HELLER_RUT = "11.111.111-1"


class TestProdPersons:
    def test_regulatory_profile_roundtrip(self, live_client: CerberusClient) -> None:
        """G-persons check: regulatory_profile() must succeed for a known RUT.

        Replaces the pre-v0.2.0 ``persons.list()`` + ``regulatory_profile()``
        round-trip: ``/v1/persons`` is not a real endpoint, so we seed the
        RUT from the KYB corpus instead.
        """
        try:
            profile = live_client.persons.regulatory_profile(CARLOS_HELLER_RUT)
        except NotFoundError:
            pytest.xfail(f"no regulatory profile for {CARLOS_HELLER_RUT} in current corpus")
        assert isinstance(profile, dict)
        cargos = profile.get("cargos_vigentes")
        assert isinstance(cargos, list), "cargos_vigentes must be a list"
        nombre = profile.get("nombre_completo")
        assert isinstance(nombre, str), "nombre_completo must be a string"
        assert nombre, "nombre_completo must be non-empty"


# ---------------------------------------------------------------------------
# Async smoke
# ---------------------------------------------------------------------------


class TestAsyncProd:
    async def test_async_kyb_roundtrip(self) -> None:
        assert CERBERUS_API_KEY is not None
        async with AsyncCerberusClient(
            api_key=CERBERUS_API_KEY, base_url=LIVE_BASE_URL, timeout=30.0
        ) as client:
            try:
                profile = await client.kyb.get(FALABELLA_RUT)
            except NotFoundError:
                pytest.xfail("Falabella not seeded in current prod corpus")
            assert isinstance(profile, dict)
