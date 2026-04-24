"""Unit tests for `cerberus_compliance.auth`.

Strict TDD: all tests written before any implementation. Covers `ApiKeyAuth`
(header injection, validation, single-pass auth_flow) and `resolve_api_key`
(explicit-arg → env var → ValueError resolution chain).
"""

from __future__ import annotations

import httpx
import pytest
import respx

from cerberus_compliance import __version__
from cerberus_compliance.auth import API_KEY_ENV_VAR, ApiKeyAuth, resolve_api_key

# ---------------------------------------------------------------------------
# ApiKeyAuth — construction
# ---------------------------------------------------------------------------


class TestApiKeyAuthInit:
    def test_stores_api_key(self) -> None:
        auth = ApiKeyAuth("secret-key")
        assert auth.api_key == "secret-key"

    def test_rejects_empty_string(self) -> None:
        with pytest.raises(ValueError, match="api_key"):
            ApiKeyAuth("")

    @pytest.mark.parametrize("ws", [" ", "    ", "\t", "\n", " \t\n "])
    def test_rejects_whitespace_only(self, ws: str) -> None:
        with pytest.raises(ValueError, match="api_key"):
            ApiKeyAuth(ws)

    def test_no_body_required(self) -> None:
        # httpx.Auth contract — class attrs control whether httpx buffers req/resp body.
        assert ApiKeyAuth.requires_request_body is False
        assert ApiKeyAuth.requires_response_body is False


# ---------------------------------------------------------------------------
# ApiKeyAuth — auth_flow header injection
# ---------------------------------------------------------------------------


class TestAuthFlow:
    def test_adds_authorization_bearer(self) -> None:
        auth = ApiKeyAuth("foo")
        request = httpx.Request("GET", "https://api.example.com/v1/health")
        flow = auth.auth_flow(request)
        prepared = next(flow)
        assert prepared.headers["Authorization"] == "Bearer foo"

    def test_sets_default_user_agent_when_absent(self) -> None:
        auth = ApiKeyAuth("foo")
        request = httpx.Request("GET", "https://api.example.com/v1/health")
        flow = auth.auth_flow(request)
        prepared = next(flow)
        assert prepared.headers["User-Agent"] == f"cerberus-compliance/{__version__}"

    def test_preserves_existing_user_agent(self) -> None:
        auth = ApiKeyAuth("foo")
        request = httpx.Request(
            "GET",
            "https://api.example.com/v1/health",
            headers={"User-Agent": "my-app/1.2.3"},
        )
        flow = auth.auth_flow(request)
        prepared = next(flow)
        assert prepared.headers["User-Agent"] == "my-app/1.2.3"

    def test_auth_flow_yields_exactly_one_request(self) -> None:
        auth = ApiKeyAuth("foo")
        request = httpx.Request("GET", "https://api.example.com/v1/health")
        flow = auth.auth_flow(request)
        next(flow)  # first (and only) request
        # A fake response to feed back; flow must terminate without yielding again.
        fake_response = httpx.Response(200, request=request)
        with pytest.raises(StopIteration):
            flow.send(fake_response)

    def test_authorization_overrides_existing_header(self) -> None:
        # Even if caller passes an Authorization header, ApiKeyAuth wins —
        # this is the standard httpx.Auth contract.
        auth = ApiKeyAuth("foo")
        request = httpx.Request(
            "GET",
            "https://api.example.com/v1/health",
            headers={"Authorization": "Bearer should-be-replaced"},
        )
        flow = auth.auth_flow(request)
        prepared = next(flow)
        assert prepared.headers["Authorization"] == "Bearer foo"


# ---------------------------------------------------------------------------
# ApiKeyAuth — integration with httpx.Client + respx
# ---------------------------------------------------------------------------


class TestApiKeyAuthThroughHttpx:
    def test_outgoing_request_carries_bearer(self, respx_mock: respx.MockRouter) -> None:
        route = respx_mock.get("/ping").respond(200, json={"ok": True})
        with httpx.Client(
            base_url="https://mock.test/v1", auth=ApiKeyAuth("ck_live_xyz")
        ) as client:
            resp = client.get("/ping")
        assert resp.status_code == 200
        assert route.called
        sent = route.calls.last.request
        assert sent.headers["Authorization"] == "Bearer ck_live_xyz"
        assert sent.headers["User-Agent"] == f"cerberus-compliance/{__version__}"


# ---------------------------------------------------------------------------
# resolve_api_key — resolution order
# ---------------------------------------------------------------------------


class TestResolveApiKey:
    def test_explicit_argument_wins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(API_KEY_ENV_VAR, "from-env")
        assert resolve_api_key("explicit") == "explicit"

    def test_env_var_used_when_argument_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(API_KEY_ENV_VAR, "from-env")
        assert resolve_api_key(None) == "from-env"

    def test_env_var_used_when_argument_whitespace(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(API_KEY_ENV_VAR, "from-env")
        assert resolve_api_key("   ") == "from-env"

    def test_raises_when_no_argument_and_no_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(API_KEY_ENV_VAR, raising=False)
        with pytest.raises(ValueError, match="Cerberus API key not provided"):
            resolve_api_key(None)

    def test_raises_when_argument_empty_and_env_empty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(API_KEY_ENV_VAR, "   ")
        with pytest.raises(ValueError, match="Cerberus API key not provided"):
            resolve_api_key("")

    def test_raises_when_argument_whitespace_and_env_unset(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(API_KEY_ENV_VAR, raising=False)
        with pytest.raises(ValueError, match="Cerberus API key not provided"):
            resolve_api_key("   ")

    def test_env_var_constant_value(self) -> None:
        # Lock the env-var name as part of the public contract.
        assert API_KEY_ENV_VAR == "CERBERUS_API_KEY"
