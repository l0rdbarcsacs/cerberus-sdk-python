"""FastAPI webhook receiver for Cerberus Compliance outbound events.

Runnable: ``CERBERUS_WEBHOOK_SECRET=<secret> python examples/webhook_handler.py``
   (invoked without the secret set: prints a setup hint and exits 0 so the
   release gate is not blocked by a missing webhook subscription.)
Tier required: ``enterprise`` for live webhook subscriptions. Receiving the
secret via the developer portal is a one-time setup step.
Expected runtime: indefinite while the receiver is running.

This example demonstrates how to verify and dispatch webhooks emitted by the
Cerberus Compliance platform (P9 in the roadmap). Cerberus signs each webhook
with HMAC-SHA256 over ``"{timestamp}.{raw_body}"`` using a per-subscription
secret, and includes the signature in the ``X-Cerberus-Signature`` header
(``sha256=<hex>``) along with the unix timestamp in ``X-Cerberus-Timestamp``.

Prerequisites (the example keeps these OPTIONAL so that ``import`` succeeds in
minimal environments)::

    pip install fastapi uvicorn

Environment variables:

* ``CERBERUS_WEBHOOK_SECRET`` (required at runtime) — the shared secret issued
  by Cerberus when you create a webhook subscription.
* ``CERBERUS_WEBHOOK_MAX_SKEW_SECONDS`` (optional, default ``300``) — maximum
  clock drift allowed between the webhook timestamp and the receiver, in
  seconds. Requests outside this window are rejected to defend against replay.

Run it locally::

    export CERBERUS_WEBHOOK_SECRET="whsec_..."
    python -m examples.webhook_handler
    # -> listens on http://0.0.0.0:8000/webhooks/cerberus

Example curl invocation (payload, timestamp, and signature must all match)::

    BODY='{"id":"evt_1","type":"sanction.added","occurred_at":"2026-01-01T00:00:00Z","data":{"entity_id":"ent_42"}}'
    TS=$(date +%s)
    SIG=$(printf "%s.%s" "$TS" "$BODY" | openssl dgst -sha256 -hmac "$CERBERUS_WEBHOOK_SECRET" | awk '{print $2}')
    curl -X POST http://localhost:8000/webhooks/cerberus \\
        -H "Content-Type: application/json" \\
        -H "X-Cerberus-Timestamp: $TS" \\
        -H "X-Cerberus-Signature: sha256=$SIG" \\
        -d "$BODY"
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import sys
import time
from collections.abc import Callable
from typing import Any

try:
    from fastapi import FastAPI, HTTPException, Request, status  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - optional dep for examples
    FastAPI = None  # type: ignore[assignment,misc]
    HTTPException = None  # type: ignore[assignment,misc]
    Request = None  # type: ignore[assignment,misc]
    status = None  # type: ignore[assignment,misc]
    _FASTAPI_AVAILABLE = False
else:
    _FASTAPI_AVAILABLE = True

from cerberus_compliance import CerberusAPIError  # noqa: F401  # imported for handler extensions

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("cerberus.webhook")

SIGNATURE_PREFIX = "sha256="
DEFAULT_MAX_SKEW_SECONDS = 300


# ---------------------------------------------------------------------------
# Event handlers (stubs — replace with your own business logic)
# ---------------------------------------------------------------------------


def handle_material_event(event: dict[str, Any]) -> None:
    """Handle a ``material_event.published`` webhook.

    A material event is a CMF-reportable corporate event (e.g. a board
    resolution, dividend, or earnings release). In production you would push
    this into your downstream pipeline (queue, datalake, notification system).
    """
    data = event.get("data", {})
    logger.info(
        "received %s for entity=%s event_id=%s",
        event.get("type"),
        data.get("entity_id"),
        event.get("id"),
    )


def handle_sanction_added(event: dict[str, Any]) -> None:
    """Handle a ``sanction.added`` webhook.

    Fires when a monitored entity/person appears on a newly ingested sanctions
    list (OFAC, UN, EU, CMF). Typical reaction: escalate to compliance ops.
    """
    data = event.get("data", {})
    logger.info(
        "received %s for entity=%s event_id=%s",
        event.get("type"),
        data.get("entity_id"),
        event.get("id"),
    )


# Dispatch table keyed by event ``type``. Unknown types are ACKed with
# ``{"status": "ignored"}`` so Cerberus does not schedule retries for events
# this receiver doesn't care about.
EventHandler = Callable[[dict[str, Any]], None]
HANDLERS: dict[str, EventHandler] = {
    "material_event.published": handle_material_event,
    "sanction.added": handle_sanction_added,
}


# ---------------------------------------------------------------------------
# Signature verification
# ---------------------------------------------------------------------------


def _verify_signature(
    *,
    secret: str,
    raw_body: bytes,
    signature_header: str | None,
    timestamp_header: str | None,
    max_skew_seconds: int,
    now: float | None = None,
) -> None:
    """Verify the HMAC-SHA256 signature and timestamp freshness.

    Raises :class:`fastapi.HTTPException` with 401 on any failure. Uses
    :func:`hmac.compare_digest` to avoid timing side-channels.
    """
    if HTTPException is None:  # pragma: no cover - guarded by _FASTAPI_AVAILABLE
        raise RuntimeError("FastAPI is required to verify signatures")

    if not signature_header or not timestamp_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid signature",
        )

    try:
        ts = int(timestamp_header)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid signature",
        ) from exc

    current = now if now is not None else time.time()
    if abs(current - ts) > max_skew_seconds:
        logger.warning(
            "rejected webhook: timestamp skew %.0fs exceeds %ds", current - ts, max_skew_seconds
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid signature",
        )

    if not signature_header.startswith(SIGNATURE_PREFIX):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid signature",
        )
    provided = signature_header[len(SIGNATURE_PREFIX) :]

    signed_payload = f"{ts}.{raw_body.decode('utf-8', errors='strict')}".encode()
    expected = hmac.new(
        secret.encode("utf-8"), msg=signed_payload, digestmod=hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected, provided):
        logger.warning("rejected webhook: signature mismatch")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid signature",
        )


# ---------------------------------------------------------------------------
# Configuration + app factory
# ---------------------------------------------------------------------------


def _load_secret() -> str:
    secret = os.environ.get("CERBERUS_WEBHOOK_SECRET")
    if not secret:
        raise RuntimeError("CERBERUS_WEBHOOK_SECRET is required")
    return secret


def _load_max_skew() -> int:
    raw = os.environ.get("CERBERUS_WEBHOOK_MAX_SKEW_SECONDS")
    if raw is None or raw == "":
        return DEFAULT_MAX_SKEW_SECONDS
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(
            "CERBERUS_WEBHOOK_MAX_SKEW_SECONDS must be an integer number of seconds"
        ) from exc
    if value <= 0:
        raise RuntimeError("CERBERUS_WEBHOOK_MAX_SKEW_SECONDS must be positive")
    return value


def _build_app() -> Any:
    """Construct the FastAPI app. Only called when FastAPI is importable."""
    if not _FASTAPI_AVAILABLE:  # pragma: no cover - defensive
        raise RuntimeError("FastAPI is not installed; run `pip install fastapi`.")

    fastapi_app = FastAPI(title="Cerberus Webhook Receiver", version="0.1.0")

    # Configuration resolved at startup (fail fast on missing secret).
    state: dict[str, Any] = {}

    @fastapi_app.on_event("startup")
    async def _configure() -> None:
        state["secret"] = _load_secret()
        state["max_skew_seconds"] = _load_max_skew()
        logger.info("webhook receiver ready: max_skew_seconds=%d", state["max_skew_seconds"])

    @fastapi_app.post("/webhooks/cerberus")
    async def receive_webhook(request: Request) -> dict[str, str]:
        raw_body = await request.body()

        _verify_signature(
            secret=state["secret"],
            raw_body=raw_body,
            signature_header=request.headers.get("X-Cerberus-Signature"),
            timestamp_header=request.headers.get("X-Cerberus-Timestamp"),
            max_skew_seconds=state["max_skew_seconds"],
        )

        try:
            event: dict[str, Any] = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="malformed json body",
            ) from exc

        if not isinstance(event, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="event must be a JSON object",
            )

        event_type = event.get("type")
        if not isinstance(event_type, str) or not event_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="missing event type",
            )

        handler = HANDLERS.get(event_type)
        if handler is None:
            logger.info("ignoring unhandled event type=%s id=%s", event_type, event.get("id"))
            return {"status": "ignored"}

        handler(event)
        return {"status": "ok"}

    return fastapi_app


app = _build_app() if _FASTAPI_AVAILABLE else None


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def _main() -> int:
    if not _FASTAPI_AVAILABLE or app is None:
        # FastAPI is an optional dev dependency; do not fail the release gate
        # just because it is absent. The example body above is still valid and
        # can be imported as a module for unit testing.
        sys.stdout.write(
            "fastapi is not installed. Install it with `pip install fastapi uvicorn` "
            "to run the webhook receiver. (Exiting 0: this example is optional.)\n"
        )
        return 0

    if not os.environ.get("CERBERUS_WEBHOOK_SECRET"):
        # No secret = no subscription yet. Print the setup hint and exit
        # cleanly so "run every example with zero args" release checks pass.
        sys.stdout.write(
            "CERBERUS_WEBHOOK_SECRET is not set; skipping the webhook listener.\n"
            "Issue a webhook subscription on the developer portal, then re-run "
            "with:  CERBERUS_WEBHOOK_SECRET=whsec_... python examples/webhook_handler.py\n"
        )
        return 0

    try:
        import uvicorn  # type: ignore[import-not-found]
    except ImportError:
        sys.stdout.write(
            "uvicorn is not installed. Install it with `pip install uvicorn` "
            "to run the webhook receiver. (Exiting 0: this example is optional.)\n"
        )
        return 0

    uvicorn.run(app, host="0.0.0.0", port=8000)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
