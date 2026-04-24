"""Walk through every exception raised by the Cerberus Compliance SDK.

Runnable: ``CERBERUS_API_KEY=<your-key> python examples/error_handling.py``
Tier required: ``professional`` is enough (the examples trigger 401/404
deliberately and never touch quota-metered endpoints heavily).
Expected runtime: ~500 ms.

Each section triggers a specific error and prints the parsed RFC 7807
problem document plus the ``X-Request-Id`` so design partners can see
what their exception handlers will observe in production:

1. ``ValueError`` at construction — missing API key.
2. ``AuthError`` (401) — key is syntactically valid but unknown.
3. ``NotFoundError`` (404) — unknown RUT.
4. ``ValidationError`` (422) — malformed RUT the server refuses to parse.
   (Many *structurally* invalid RUTs actually return 404, not 422;
   the example accepts either outcome gracefully.)
5. Deprecation shim — ``client.persons.list()`` surfaces both a
   ``DeprecationWarning`` and a ``NotImplementedError``.

``RateLimitError`` (429) and ``QuotaError`` (402) are only documented
here — triggering them live would be antisocial to other tenants and
the professional test key has plenty of headroom. See the inline
comments for how to catch them.
"""

from __future__ import annotations

import logging
import os
import sys
import warnings

from cerberus_compliance import (
    AuthError,
    CerberusAPIError,
    CerberusClient,
    NotFoundError,
    QuotaError,  # noqa: F401 — imported for the "how to catch" demo.
    RateLimitError,  # noqa: F401 — imported for the "how to catch" demo.
    ValidationError,
)

logger = logging.getLogger("cerberus_compliance.examples.error_handling")


def _print_header(title: str) -> None:
    """Print a wide headline above each section."""
    bar = "=" * 72
    print(f"\n{bar}\n{title}\n{bar}")


def _describe(exc: CerberusAPIError) -> None:
    """Print the status, title, detail and request_id that an exception exposes."""
    print(f"  type       : {type(exc).__name__}")
    print(f"  status     : {exc.status}")
    print(f"  title      : {exc.title}")
    print(f"  detail     : {exc.detail}")
    print(f"  problem.type: {exc.type}")
    print(f"  request_id : {exc.request_id}")


def _demo_missing_key() -> None:
    """Section 1: no api_key, no env var → ValueError at construction."""
    _print_header("1. ValueError — missing API key")
    saved = os.environ.pop("CERBERUS_API_KEY", None)
    try:
        try:
            CerberusClient()
        except ValueError as exc:
            print(f"  raised {type(exc).__name__}: {exc}")
    finally:
        if saved is not None:
            os.environ["CERBERUS_API_KEY"] = saved


def _demo_auth_error() -> None:
    """Section 2: syntactically valid key the server rejects → AuthError (401)."""
    _print_header("2. AuthError (401) — unknown API key")
    with CerberusClient(api_key="ck_test_invalid_abc123") as client:
        try:
            client.kyb.get("96.505.760-9")
        except AuthError as exc:
            _describe(exc)


def _demo_not_found(client: CerberusClient) -> None:
    """Section 3: valid key but unknown RUT → NotFoundError (404)."""
    _print_header("3. NotFoundError (404) — unknown entity")
    try:
        client.entities.by_rut("00.000.000-0")
    except NotFoundError as exc:
        _describe(exc)


def _demo_validation_error(client: CerberusClient) -> None:
    """Section 4: malformed RUT that fails server-side validation.

    Upstream has tightened its RUT validator over time; many syntactically
    invalid RUTs now hit 404 rather than 422. We accept both outcomes so
    the example stays green regardless of which the server chose.
    """
    _print_header("4. ValidationError (422) — bad input")
    try:
        client.kyb.get("not-a-valid-rut")
    except ValidationError as exc:
        _describe(exc)
        if exc.errors:
            print("  field errors:")
            for field_err in exc.errors:
                print(f"    - {field_err}")
        else:
            print("  (no field-level errors attached)")
    except NotFoundError as exc:
        # The prod validator sometimes short-circuits malformed RUTs to 404
        # instead of 422. Treat that as a valid, documented outcome for the
        # demo rather than crashing the example.
        _describe(exc)
        print("  (server responded 404 for this malformed RUT — 422 is also possible)")


def _demo_deprecation(client: CerberusClient) -> None:
    """Section 5: deprecated method triggers DeprecationWarning + NotImplementedError."""
    _print_header("5. DeprecationWarning + NotImplementedError — deprecated shim")
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always", DeprecationWarning)
        try:
            client.persons.list()  # deprecated in v0.2.0
        except NotImplementedError as exc:
            first = captured[0] if captured else None
            print(f"  DeprecationWarning count : {len(captured)}")
            if first is not None:
                print(f"  first warning category   : {first.category.__name__}")
                print(f"  first warning message    : {first.message}")
            print(f"  NotImplementedError      : {exc}")


def _print_documented_recipes() -> None:
    """Print the boilerplate for RateLimitError and QuotaError without triggering them."""
    _print_header("6. RateLimitError (429) + QuotaError (402) — catch-block recipes")
    print("""  # Rate-limited — honour the Retry-After hint the SDK parsed for you:
  try:
      client.kyb.get(rut)
  except RateLimitError as exc:
      sleep_for = exc.retry_after or 1.0
      logger.warning("rate limited, sleeping %.1fs", sleep_for)
      time.sleep(sleep_for)

  # Quota exhausted — stop: upgrading the tier is the only way out:
  try:
      client.kyb.get(rut)
  except QuotaError as exc:
      logger.error("tier quota exhausted: %s [request_id=%s]", exc.detail, exc.request_id)
      raise
""")


def main() -> int:
    """Run every section in order; returns 0 if each demo produced its expected error."""
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    _demo_missing_key()
    _demo_auth_error()

    try:
        client = CerberusClient()
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    with client:
        try:
            _demo_not_found(client)
            _demo_validation_error(client)
            _demo_deprecation(client)
        except CerberusAPIError as exc:
            # Any *other* API failure bubbles up to a single visible handler
            # so design partners can see exactly what a caller-level except
            # block would look like in their own code.
            print(f"\nunexpected api error: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1

    _print_documented_recipes()
    return 0


if __name__ == "__main__":
    sys.exit(main())
