---
title: "Errors"
description: "The CerberusAPIError hierarchy, RFC 7807 problem details, and common recipes."
---

# Errors

Every non-2xx HTTP response is translated into a typed exception. The SDK never
returns an error dict — any time a call returns normally, you can trust the body is a
successful payload.

## The hierarchy

```text
CerberusAPIError
├── AuthError          (401, 403)
├── QuotaError         (402)
├── ValidationError    (422) — .errors: list[dict]
├── RateLimitError     (429) — .retry_after: float | None
└── ServerError        (5xx)
```

All five concrete subclasses are re-exported from the top-level package:

```python
from cerberus_compliance import (
    CerberusAPIError,
    AuthError,
    QuotaError,
    ValidationError,
    RateLimitError,
    ServerError,
)
```

Status codes that fall outside the dispatch table (for example an unexpected 418)
raise the base `CerberusAPIError` directly. Any 5xx status that is not otherwise
mapped resolves to `ServerError`.

## Fields on every error

Every `CerberusAPIError` exposes the following:

| Attribute     | Type                 | Description                                                   |
|---------------|----------------------|---------------------------------------------------------------|
| `.status`     | `int`                | HTTP status code returned by the API.                         |
| `.problem`    | `dict[str, Any]`     | Full RFC 7807 problem document (see below).                   |
| `.request_id` | `str \| None`        | Value of the `X-Request-Id` response header.                  |
| `.title`      | `str` (property)     | `problem["title"]`, falling back to the HTTP reason phrase.   |
| `.detail`     | `str \| None` (prop) | `problem["detail"]`, or `None` when absent.                   |
| `.type`       | `str` (property)     | `problem["type"]`, defaulting to `"about:blank"` per RFC 7807.|
| `.instance`   | `str \| None` (prop) | `problem["instance"]`, or `None` when absent.                 |

`str(exc)` renders a compact, log-friendly line, for example:

```text
422 Unprocessable Entity: rut is not a valid Chilean tax id [request_id=req_01HW...]
```

## The `problem` dict

The Cerberus API follows [RFC 7807](https://datatracker.ietf.org/doc/html/rfc7807)
(`application/problem+json`). A typical body looks like:

```json
{
  "type": "https://developers.cerberus.cl/problems/validation",
  "title": "Unprocessable Entity",
  "status": 422,
  "detail": "rut is not a valid Chilean tax id",
  "instance": "/v1/entities",
  "errors": [
    {"field": "rut", "code": "invalid_format", "message": "must include check digit"}
  ]
}
```

The SDK exposes the full dict as `exc.problem`, so any extra fields the server chose
to include (vendor extensions, tenant ids, trace ids) remain accessible without
parsing the body yourself.

The SDK is **defensive**: if the server returns an empty body, malformed JSON, a JSON
array, or a plain-text error, `.problem` is still a `dict` (with a synthetic `title`
populated from the HTTP reason phrase). You never have to null-check it.

## Handling specific errors

### Detecting a bad API key

```python
from cerberus_compliance import CerberusClient, AuthError

try:
    with CerberusClient() as client:
        client._request("GET", "/entities", params={"limit": 1})
except AuthError as exc:
    raise SystemExit(
        f"Cerberus rejected the API key ({exc.status} {exc.title}); "
        f"check CERBERUS_API_KEY. request_id={exc.request_id}"
    ) from exc
```

`AuthError` covers both **401** (invalid / missing key) and **403** (key lacks the
scope needed for the endpoint). Read `exc.detail` to distinguish.

### Handling a rate limit

```python
import time
from cerberus_compliance import CerberusClient, RateLimitError

with CerberusClient() as client:
    try:
        client._request("GET", "/material_events", params={"limit": 100})
    except RateLimitError as exc:
        time.sleep(exc.retry_after or 5)
```

`exc.retry_after` is a parsed `float` (seconds-from-now) derived from the
`Retry-After` header. It accepts both the delta-seconds form (`"60"`) and the
HTTP-date form (`"Wed, 21 Oct 2026 07:28:00 GMT"`), and is `None` if the header was
missing or unparseable.

### Inspecting validation errors

```python
from cerberus_compliance import CerberusClient, ValidationError

with CerberusClient() as client:
    try:
        client._request("GET", "/entities", params={"rut": "not-a-rut"})
    except ValidationError as exc:
        for err in exc.errors:
            print(f"{err.get('field')}: {err.get('code')} — {err.get('message')}")
```

`exc.errors` is the field-level list from `problem["errors"]`, filtered to
dict-shaped entries. It is always a list (empty when the server omitted the field),
so you can iterate without a null check.

## Retries vs raises

`CerberusClient` retries transient failures **before** raising. The default
`RetryConfig` retries HTTP **429, 500, 502, 503, 504** and transport-layer errors
with exponential backoff (+ jitter) up to `max_attempts=3`.

That means:

- When your code sees `RateLimitError` or `ServerError`, the SDK has **already**
  retried `max_attempts - 1` times and exhausted its budget. Your exception handler
  runs only for the final failure.
- `AuthError`, `QuotaError`, and `ValidationError` are **not** retried — they reflect
  caller-side problems (bad credentials, exhausted quota, invalid input) that a retry
  cannot fix. They are raised on the first response.
- When the server returns a `Retry-After` header on a 429, the SDK uses its value to
  compute the sleep instead of the exponential schedule (capped by
  `max_delay_ms`).

Tune the policy via `CerberusClient(retry=RetryConfig(...))` — see the README's
"Retries" section and the `cerberus_compliance.retry` module docstrings.

## Using `request_id` for support

Every raised `CerberusAPIError` preserves the `X-Request-Id` header returned by the
Cerberus API gateway. When you file a support ticket, paste this id verbatim —
Cerberus operations can trace exactly that request end-to-end, across the gateway,
the service that handled it, and the downstream regulatory source. Example triage
line you should aim to log:

```python
logger.error(
    "cerberus.api_error",
    extra={
        "status": exc.status,
        "title": exc.title,
        "detail": exc.detail,
        "request_id": exc.request_id,
    },
)
```

Reports with a `request_id` typically resolve an order of magnitude faster than
reports with a copy-pasted stack trace alone.
