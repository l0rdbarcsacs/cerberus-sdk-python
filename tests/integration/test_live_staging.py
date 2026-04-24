"""Integration tests against Cerberus Compliance staging.

These tests hit the real staging API
(``https://staging-compliance.cerberus.cl/v1``) and are therefore:

* Skipped when ``CERBERUS_STAGING_KEY`` is not set in the env.
* Opt-in in CI — Instance D wires this via a GitHub Actions secret of
  the same name. See docs/HANDOFF_P51_A.md for the orchestration plan.

Run locally::

    export CERBERUS_STAGING_KEY=ck_test_...
    pytest tests/integration/ -q

If the endpoint exists but returns an empty result (404 for a missing
RUT, empty list for a filter that matches nothing), the test *passes* —
we exercise the plumbing, not the corpus. Tests that strictly require
a populated fixture (e.g. Falabella must exist) are marked with an
``xfail(strict=False)`` so a fresh staging DB doesn't break CI.
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

CERBERUS_STAGING_KEY = os.getenv("CERBERUS_STAGING_KEY")
STAGING_BASE_URL = os.getenv(
    "CERBERUS_STAGING_BASE_URL", "https://staging-compliance.cerberus.cl/v1"
)

# Anchor RUT seeded in the staging corpus (P5 seed script): Falabella.
FALABELLA_RUT = "96.505.760-9"

pytestmark = pytest.mark.skipif(
    not CERBERUS_STAGING_KEY,
    reason="CERBERUS_STAGING_KEY not set; integration tests require staging access",
)


@pytest.fixture
def staging_client() -> Iterator[CerberusClient]:
    """Sync client pointing at the staging base URL."""
    assert CERBERUS_STAGING_KEY is not None  # narrow for type-checker; pytestmark skips otherwise
    client = CerberusClient(api_key=CERBERUS_STAGING_KEY, base_url=STAGING_BASE_URL, timeout=30.0)
    try:
        yield client
    finally:
        client.close()


# ---------------------------------------------------------------------------
# KYB (G1)
# ---------------------------------------------------------------------------


class TestStagingKYB:
    def test_kyb_get_falabella(self, staging_client: CerberusClient) -> None:
        try:
            profile = staging_client.kyb.get(FALABELLA_RUT)
        except NotFoundError:
            pytest.xfail("Falabella not seeded in current staging corpus")
        assert isinstance(profile, dict)
        # legal_name is the single documented stable field across cache states.
        assert "legal_name" in profile or "rut" in profile

    def test_kyb_get_missing_raises_not_found(self, staging_client: CerberusClient) -> None:
        with pytest.raises((NotFoundError, CerberusAPIError)):
            staging_client.kyb.get("76000000-0")


# ---------------------------------------------------------------------------
# Entities (G12, G13)
# ---------------------------------------------------------------------------


class TestStagingEntities:
    def test_list(self, staging_client: CerberusClient) -> None:
        entities = staging_client.entities.list(limit=1)
        assert isinstance(entities, list)

    def test_by_rut(self, staging_client: CerberusClient) -> None:
        try:
            entity = staging_client.entities.by_rut(FALABELLA_RUT)
        except NotFoundError:
            pytest.xfail("Falabella not seeded in current staging corpus")
        assert isinstance(entity, dict)
        assert "id" in entity or "rut" in entity

    def test_get_then_ownership(self, staging_client: CerberusClient) -> None:
        entities = staging_client.entities.list(limit=1)
        if not entities:
            pytest.skip("no entities in staging corpus")
        entity_id = entities[0].get("id")
        if entity_id is None:
            pytest.skip("entity payload missing id field")
        full = staging_client.entities.get(str(entity_id))
        assert isinstance(full, dict)
        try:
            ownership = staging_client.entities.ownership(str(entity_id))
        except NotFoundError:
            pytest.xfail("entity has no ownership record in current corpus")
        assert isinstance(ownership, dict)


# ---------------------------------------------------------------------------
# Sanctions (G2)
# ---------------------------------------------------------------------------


class TestStagingSanctions:
    def test_list(self, staging_client: CerberusClient) -> None:
        results = staging_client.sanctions.list(limit=1)
        assert isinstance(results, list)

    def test_by_entity_via_entities_sanctions(self, staging_client: CerberusClient) -> None:
        """G2 check: entities.sanctions(id) must succeed against the real API.

        Uses the first entity from /entities/list as the target so this
        test stays decoupled from whether any specific RUT is seeded.
        """
        entities = staging_client.entities.list(limit=1)
        if not entities:
            pytest.skip("no entities in staging corpus")
        entity_id = entities[0].get("id")
        if entity_id is None:
            pytest.skip("entity payload missing id field")
        # Even when the entity has zero hits, we expect a 200 with an empty
        # list — not a 404 for the endpoint itself.
        hits = staging_client.entities.sanctions(str(entity_id))
        assert isinstance(hits, list)


# ---------------------------------------------------------------------------
# Regulations + search (G16)
# ---------------------------------------------------------------------------


class TestStagingRegulations:
    def test_list(self, staging_client: CerberusClient) -> None:
        regs = staging_client.regulations.list(limit=1)
        assert isinstance(regs, list)

    def test_search(self, staging_client: CerberusClient) -> None:
        results = staging_client.regulations.search("Ley")
        assert isinstance(results, list)


# ---------------------------------------------------------------------------
# RPSF (G14)
# ---------------------------------------------------------------------------


class TestStagingRPSF:
    def test_list(self, staging_client: CerberusClient) -> None:
        records = staging_client.rpsf.list(limit=1)
        assert isinstance(records, list)


# ---------------------------------------------------------------------------
# Normativa (G15)
# ---------------------------------------------------------------------------


class TestStagingNormativa:
    def test_list(self, staging_client: CerberusClient) -> None:
        norms = staging_client.normativa.list(limit=1)
        assert isinstance(norms, list)


# ---------------------------------------------------------------------------
# Persons
# ---------------------------------------------------------------------------


class TestStagingPersons:
    def test_list(self, staging_client: CerberusClient) -> None:
        persons = staging_client.persons.list(limit=1)
        assert isinstance(persons, list)

    def test_regulatory_profile_roundtrip(self, staging_client: CerberusClient) -> None:
        persons = staging_client.persons.list(limit=1)
        if not persons:
            pytest.skip("no persons in staging corpus")
        person_id = persons[0].get("id")
        if person_id is None:
            pytest.skip("person payload missing id field")
        try:
            profile = staging_client.persons.regulatory_profile(str(person_id))
        except NotFoundError:
            pytest.xfail("person has no regulatory profile")
        assert isinstance(profile, dict)


# ---------------------------------------------------------------------------
# Async smoke
# ---------------------------------------------------------------------------


class TestAsyncStaging:
    async def test_async_kyb_roundtrip(self) -> None:
        assert CERBERUS_STAGING_KEY is not None
        async with AsyncCerberusClient(
            api_key=CERBERUS_STAGING_KEY, base_url=STAGING_BASE_URL, timeout=30.0
        ) as client:
            try:
                profile = await client.kyb.get(FALABELLA_RUT)
            except NotFoundError:
                pytest.xfail("Falabella not seeded in current staging corpus")
            assert isinstance(profile, dict)
