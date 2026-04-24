---
title: "Authentication"
description: "API keys, environment variables, and secret hygiene for the Cerberus SDK."
---

# Authentication

The Cerberus Compliance API uses **bearer API keys**. Every outbound request made by
`CerberusClient` and `AsyncCerberusClient` carries an
`Authorization: Bearer <api_key>` header, plus a
`User-Agent: cerberus-compliance/<version>` identifying the SDK.

## API keys overview

- Keys are issued per tenant from the Cerberus admin dashboard.
- The first 8 characters of a key form a **stable, non-secret prefix** that is safe to
  log and attach to audit trails (for example `ck_live_`). The remainder is the secret
  material — never log it, never ship it to the browser.
- Key rotation is handled server-side: existing keys keep working until you revoke
  them, so you can overlap old and new keys during a deploy.
- The SDK never caches the key to disk. It is held on the `CerberusClient` instance
  only.

## The `CERBERUS_API_KEY` environment variable

By default the SDK reads the API key from the `CERBERUS_API_KEY` environment variable.
This is the recommended production pattern — keys live in your secret manager and are
injected into the process environment at boot.

```python
from cerberus_compliance import CerberusClient

client = CerberusClient()  # reads $CERBERUS_API_KEY
```

If neither an explicit `api_key=` argument nor the `CERBERUS_API_KEY` environment
variable is set, the constructor raises `ValueError`:

```text
ValueError: Cerberus API key not provided. Pass api_key= or set CERBERUS_API_KEY.
```

The environment-variable name is also exported as a constant in case your application
wants to reference it programmatically:

```python
from cerberus_compliance.auth import API_KEY_ENV_VAR  # "CERBERUS_API_KEY"
```

## Passing a key explicitly

For one-off scripts, testing, or multi-tenant processes that juggle several keys,
pass the key directly:

```python
from cerberus_compliance import CerberusClient

client = CerberusClient(api_key="ck_live_...")
```

Explicit arguments always win over the environment variable.

## Custom base URL

For staging environments, regional endpoints, or local mock servers, override
`base_url`:

```python
from cerberus_compliance import CerberusClient

client = CerberusClient(
    api_key="ck_test_...",
    base_url="https://staging-api.cerberus.cl/v1",
)
```

The default is `https://api.cerberus.cl/v1`. A trailing slash on `base_url` is
stripped automatically — both `https://example.com/v1` and `https://example.com/v1/`
work identically. During unit tests you can point the SDK at a `respx` or
`http.server` mock running on `http://127.0.0.1:<port>`.

## Custom `httpx.Client` / `httpx.AsyncClient`

For advanced deployments — corporate proxies, custom trust stores, mutual TLS, request
tracing — inject your own `httpx` client. The SDK will reuse it verbatim (including any
transport, proxy, or event hooks you configure) and apply its own `ApiKeyAuth` on top.

```python
import httpx
from cerberus_compliance import CerberusClient

transport = httpx.HTTPTransport(proxy="http://corp-proxy:3128", retries=0)
my_http = httpx.Client(
    base_url="https://api.cerberus.cl/v1",
    timeout=30.0,
    transport=transport,
    verify="/etc/ssl/corp-ca-bundle.pem",
)

client = CerberusClient(api_key="ck_live_...", http_client=my_http)
```

The same hook exists on `AsyncCerberusClient` via `http_client=` accepting an
`httpx.AsyncClient`. When you supply your own client you also own its lifecycle —
`CerberusClient.close()` calls `http_client.close()`, so the SDK's context-manager
semantics still work. If you share the same `httpx` client across multiple SDK
instances, build it once, wire it into each `CerberusClient` with `http_client=`,
and call `http_client.close()` yourself at shutdown instead of using the SDK's
context manager on every instance.

## Rotating keys

Rotate early, rotate often. The recommended pattern:

1. **Create** a new API key in the admin dashboard. Note both its prefix and its
   secret.
2. **Deploy** the new secret to your secret manager and your running services. Leave
   the old key active during this window.
3. **Verify** the new key is serving live traffic (check the prefix in your request
   logs).
4. **Revoke** the old key from the admin dashboard.

The Cerberus platform honors a **30-day grace period** on revoked keys: once you
delete a key it continues to authenticate for up to 30 days, returning a
`Deprecation` header on every response so your observability stack can surface
lingering usage. Treat this as a safety net, not a migration strategy.

## Secret hygiene

- **Never** commit keys to the repository. Add them to `.gitignore` patterns and scan
  history with tooling such as `gitleaks` or `trufflehog`.
- Prefer **short-lived keys for CI**. Issue a CI-only key with narrow scopes, rotate
  on schedule (e.g. monthly), and revoke immediately on any compromise signal.
- Store production keys in a dedicated **secret manager**: AWS Secrets Manager,
  HashiCorp Vault, GCP Secret Manager, Azure Key Vault, 1Password, or Doppler.
  Application code reads from the manager at boot, not from config files baked into
  the container image.
- Log **prefixes only**. The first 8 characters uniquely identify a key for support
  purposes without leaking secret material.
- For operational references to the key-lifecycle policy, see
  `docs/legal/01-rat/act-006-api-keys.md` in the main Cerberus monorepo.
