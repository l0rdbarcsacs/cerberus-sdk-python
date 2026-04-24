"""Shared pytest fixtures for the cerberus-compliance SDK test suite.

Imports of the SDK happen lazily inside fixtures so that unit tests for individual
modules (errors, retry, auth) can run even before client.py is fully wired.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
import respx

DUMMY_API_KEY = "ck_test_unit_test_key"
TEST_BASE_URL = "https://mock.test/v1"


@pytest.fixture
def api_key() -> str:
    return DUMMY_API_KEY


@pytest.fixture
def base_url() -> str:
    return TEST_BASE_URL


@pytest.fixture
def respx_mock() -> Iterator[respx.MockRouter]:
    """`respx` router scoped to a single test, asserting all mocks were called."""
    with respx.mock(
        assert_all_called=False,
        assert_all_mocked=True,
        base_url=TEST_BASE_URL,
    ) as router:
        yield router


@pytest.fixture
def sync_client(api_key: str, base_url: str) -> Iterator[Any]:
    """A `CerberusClient` configured for the test mock host."""
    from cerberus_compliance.client import CerberusClient

    client = CerberusClient(api_key=api_key, base_url=base_url, timeout=2.0)
    try:
        yield client
    finally:
        client.close()


@pytest.fixture
async def async_client(api_key: str, base_url: str) -> AsyncIterator[Any]:
    """An `AsyncCerberusClient` configured for the test mock host."""
    from cerberus_compliance.client import AsyncCerberusClient

    client = AsyncCerberusClient(api_key=api_key, base_url=base_url, timeout=2.0)
    try:
        yield client
    finally:
        await client.close()


@pytest.fixture
def problem_json() -> Callable[..., dict[str, Any]]:
    """Build a RFC 7807 problem document with sensible defaults."""

    def _build(
        *,
        status: int = 500,
        title: str = "Internal Server Error",
        detail: str | None = None,
        type_uri: str = "about:blank",
        instance: str | None = None,
        **extras: Any,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "type": type_uri,
            "title": title,
            "status": status,
        }
        if detail is not None:
            body["detail"] = detail
        if instance is not None:
            body["instance"] = instance
        body.update(extras)
        return body

    return _build


@pytest.fixture(scope="session")
def openapi_sample_path() -> Path:
    return Path(__file__).parent / "fixtures" / "openapi-sample.json"


@pytest.fixture(scope="session")
def openapi_sample(openapi_sample_path: Path) -> dict[str, Any]:
    with openapi_sample_path.open(encoding="utf-8") as fh:
        loaded: dict[str, Any] = json.load(fh)
    return loaded
