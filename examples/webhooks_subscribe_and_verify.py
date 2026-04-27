"""Subscribe to a webhook + verify an incoming signature offline.

Two halves:

1. **Subscription** (run once at app boot or via deploy script).
   Creates a webhook, prints the plaintext secret — capture it from
   stdout immediately because it's only returned ONCE.

2. **Verification** (runs inside the receiving HTTP handler).
   Demonstrates the offline ``WebhooksResource.verify_signature``
   helper, exposed at the package level as
   ``cerberus_compliance.verify_webhook_signature`` so you do not need
   to instantiate a client to validate incoming requests.

Run subscription:
    CERBERUS_API_KEY=ck_live_... python examples/webhooks_subscribe_and_verify.py
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time

from cerberus_compliance import CerberusClient, verify_webhook_signature


def subscribe() -> None:
    client = CerberusClient(api_key=os.environ["CERBERUS_API_KEY"])
    hook = client.webhooks.create(
        callback_url="https://example.com/cerberus/webhook",
        event_types=[
            "hecho_esencial.new",
            "sancion.new",
            "resolucion.new",
        ],
        description="prod compliance alerting",
    )
    print(f"webhook id:    {hook['id']}")
    print(f"secret:        {hook['secret']}   ← STORE THIS NOW; only returned once")
    print(f"event_types:   {hook['event_types']}")
    print(f"status:        {hook['status']}")
    print()
    print("Subsequent reads will not include the secret:")
    refetch = client.webhooks.get(hook["id"])
    print(f"  refetch.secret = {refetch.get('secret', '<absent>')!r}")


def verify_demo() -> None:
    """Synthetic round-trip: build a signed payload, verify it.

    In production the ``signature_header`` and ``payload`` come from the
    incoming HTTP request (``request.headers['X-Cerberus-Signature']``
    and ``request.body``); the secret comes from your secret store.
    """
    secret = "whk_secret_demo_only_for_round_trip"
    payload = b'{"event_type":"hecho_esencial.new","entity_rut":"97004000-5"}'
    ts = int(time.time())
    sig = hmac.new(secret.encode(), f"{ts}.".encode() + payload, hashlib.sha256).hexdigest()
    header = f"t={ts},v1={sig}"

    assert verify_webhook_signature(payload=payload, signature_header=header, secret=secret), (
        "round-trip should verify"
    )

    # Tampered payload → False (fail-safe, never raises)
    bogus = verify_webhook_signature(
        payload=b'{"tampered":true}', signature_header=header, secret=secret
    )
    assert bogus is False, "tampered payload must NOT verify"

    print("verify_webhook_signature round-trip OK (and correctly rejects tampering)")


if __name__ == "__main__":
    subscribe()
    print()
    verify_demo()
