"""TDD tests for `cerberus_compliance.errors`.

Covers:
- The public class hierarchy and dataclass shape.
- Body parsing (bytes / str / dict / None / malformed).
- Status -> subclass dispatch in `CerberusAPIError.from_response`.
- `Retry-After` parsing for `RateLimitError` (numeric, HTTP-date, malformed, missing).
- `__str__` formatting variants (with/without detail and request_id).
- `ValidationError.errors` property convenience.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from typing import Any

import pytest

from cerberus_compliance.errors import (
    AuthError,
    CerberusAPIError,
    QuotaError,
    RateLimitError,
    ServerError,
    ValidationError,
)

# ---------------------------------------------------------------------------
# Class hierarchy / shape
# ---------------------------------------------------------------------------


def test_cerberus_api_error_is_exception() -> None:
    err = CerberusAPIError(status=400, problem={"title": "Bad Request"})
    assert isinstance(err, Exception)


@pytest.mark.parametrize(
    "subclass",
    [AuthError, QuotaError, ValidationError, RateLimitError, ServerError],
)
def test_subclasses_inherit_from_base(subclass: type[CerberusAPIError]) -> None:
    assert issubclass(subclass, CerberusAPIError)


def test_dataclass_fields(problem_json: Callable[..., dict[str, Any]]) -> None:
    body = problem_json(status=400, title="Bad Request", detail="oops")
    err = CerberusAPIError(status=400, problem=body, request_id="req-1")
    assert err.status == 400
    assert err.problem is body
    assert err.request_id == "req-1"


def test_request_id_defaults_to_none() -> None:
    err = CerberusAPIError(status=400, problem={"title": "Bad Request"})
    assert err.request_id is None


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------


def test_title_from_problem() -> None:
    err = CerberusAPIError(status=400, problem={"title": "Bad Request"})
    assert err.title == "Bad Request"


def test_title_falls_back_to_http_reason() -> None:
    err = CerberusAPIError(status=404, problem={})
    assert err.title == "Not Found"


def test_title_falls_back_to_unknown_for_nonstandard_status() -> None:
    err = CerberusAPIError(status=799, problem={})
    assert err.title == "Unknown"


def test_detail_present_and_absent() -> None:
    with_detail = CerberusAPIError(status=400, problem={"detail": "thing went wrong"})
    without_detail = CerberusAPIError(status=400, problem={})
    assert with_detail.detail == "thing went wrong"
    assert without_detail.detail is None


def test_type_default_about_blank() -> None:
    err = CerberusAPIError(status=400, problem={})
    assert err.type == "about:blank"


def test_type_from_problem() -> None:
    err = CerberusAPIError(status=400, problem={"type": "https://errors.cerberus.cl/invalid-rut"})
    assert err.type == "https://errors.cerberus.cl/invalid-rut"


def test_instance_present_and_absent() -> None:
    with_inst = CerberusAPIError(status=400, problem={"instance": "/v1/req/123"})
    without_inst = CerberusAPIError(status=400, problem={})
    assert with_inst.instance == "/v1/req/123"
    assert without_inst.instance is None


# ---------------------------------------------------------------------------
# __str__ formatting
# ---------------------------------------------------------------------------


def test_str_with_detail_and_request_id() -> None:
    err = CerberusAPIError(
        status=400,
        problem={"title": "Bad Request", "detail": "missing field"},
        request_id="req-abc",
    )
    assert str(err) == "400 Bad Request: missing field [request_id=req-abc]"


def test_str_without_detail() -> None:
    err = CerberusAPIError(status=400, problem={"title": "Bad Request"}, request_id="req-abc")
    assert str(err) == "400 Bad Request [request_id=req-abc]"


def test_str_without_request_id() -> None:
    err = CerberusAPIError(status=400, problem={"title": "Bad Request", "detail": "missing field"})
    assert str(err) == "400 Bad Request: missing field"


def test_str_without_detail_or_request_id() -> None:
    err = CerberusAPIError(status=400, problem={"title": "Bad Request"})
    assert str(err) == "400 Bad Request"


# ---------------------------------------------------------------------------
# Body parsing
# ---------------------------------------------------------------------------


def test_from_response_bytes_valid_json(
    problem_json: Callable[..., dict[str, Any]],
) -> None:
    import json

    body = json.dumps(problem_json(status=400, title="Bad Request", detail="oops")).encode("utf-8")
    err = CerberusAPIError.from_response(status=400, body=body)
    assert err.problem["title"] == "Bad Request"
    assert err.problem["detail"] == "oops"
    assert err.status == 400


def test_from_response_str_valid_json() -> None:
    err = CerberusAPIError.from_response(
        status=400, body='{"title": "Bad Request", "detail": "oops"}'
    )
    assert err.problem["title"] == "Bad Request"
    assert err.problem["detail"] == "oops"


def test_from_response_dict() -> None:
    body: dict[str, Any] = {"title": "Bad Request", "detail": "oops"}
    err = CerberusAPIError.from_response(status=400, body=body)
    assert err.problem is body


def test_from_response_none_body_uses_http_reason() -> None:
    err = CerberusAPIError.from_response(status=404, body=None)
    assert err.problem == {"title": "Not Found", "status": 404}


def test_from_response_none_body_unknown_status() -> None:
    err = CerberusAPIError.from_response(status=799, body=None)
    assert err.problem == {"title": "Unknown", "status": 799}


def test_from_response_malformed_bytes_falls_back() -> None:
    err = CerberusAPIError.from_response(status=400, body=b"not json at all")
    assert err.problem["title"] == "Bad Request"
    assert err.problem["detail"] == "not json at all"
    assert err.problem["status"] == 400


def test_from_response_malformed_str_falls_back() -> None:
    err = CerberusAPIError.from_response(status=500, body="oh no")
    assert err.problem["title"] == "Internal Server Error"
    assert err.problem["detail"] == "oh no"
    assert err.problem["status"] == 500


def test_from_response_json_non_dict_falls_back() -> None:
    # JSON parses but isn't an object -> fall back to envelope.
    err = CerberusAPIError.from_response(status=500, body=b"[1, 2, 3]")
    assert err.problem["title"] == "Internal Server Error"
    assert err.problem["detail"] == "[1, 2, 3]"
    assert err.problem["status"] == 500


def test_from_response_propagates_request_id() -> None:
    err = CerberusAPIError.from_response(status=400, body=None, request_id="req-xyz")
    assert err.request_id == "req-xyz"


# ---------------------------------------------------------------------------
# Status -> subclass dispatch
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "expected_cls"),
    [
        (401, AuthError),
        (403, AuthError),
        (402, QuotaError),
        (422, ValidationError),
        (429, RateLimitError),
        (500, ServerError),
        (503, ServerError),
        (599, ServerError),
        (418, CerberusAPIError),
        (451, CerberusAPIError),
    ],
)
def test_from_response_dispatch(status: int, expected_cls: type[CerberusAPIError]) -> None:
    err = CerberusAPIError.from_response(status=status, body=None)
    assert type(err) is expected_cls
    assert err.status == status


# ---------------------------------------------------------------------------
# RateLimitError + Retry-After
# ---------------------------------------------------------------------------


def test_rate_limit_numeric_retry_after() -> None:
    err = CerberusAPIError.from_response(status=429, body=None, retry_after="60")
    assert isinstance(err, RateLimitError)
    assert err.retry_after == pytest.approx(60.0)


def test_rate_limit_http_date_retry_after() -> None:
    future = datetime.now(timezone.utc) + timedelta(seconds=120)
    header = format_datetime(future, usegmt=True)
    err = CerberusAPIError.from_response(status=429, body=None, retry_after=header)
    assert isinstance(err, RateLimitError)
    assert err.retry_after is not None
    # Allow a small fudge factor for the time passed during the call.
    assert 100.0 <= err.retry_after <= 120.5


def test_rate_limit_past_http_date_clamped_to_zero() -> None:
    past = datetime.now(timezone.utc) - timedelta(seconds=120)
    header = format_datetime(past, usegmt=True)
    err = CerberusAPIError.from_response(status=429, body=None, retry_after=header)
    assert isinstance(err, RateLimitError)
    assert err.retry_after == 0.0


def test_rate_limit_malformed_retry_after() -> None:
    err = CerberusAPIError.from_response(status=429, body=None, retry_after="banana")
    assert isinstance(err, RateLimitError)
    assert err.retry_after is None


def test_rate_limit_missing_retry_after() -> None:
    err = CerberusAPIError.from_response(status=429, body=None)
    assert isinstance(err, RateLimitError)
    assert err.retry_after is None


def test_rate_limit_blank_retry_after() -> None:
    err = CerberusAPIError.from_response(status=429, body=None, retry_after="   ")
    assert isinstance(err, RateLimitError)
    assert err.retry_after is None


def test_rate_limit_naive_http_date_assumed_utc() -> None:
    # Some upstreams emit HTTP-dates without a timezone marker; we assume UTC.
    future = datetime.now(timezone.utc) + timedelta(seconds=90)
    # Strip the timezone token so `parsedate_to_datetime` returns a naive datetime.
    header = future.strftime("%a, %d %b %Y %H:%M:%S")
    err = CerberusAPIError.from_response(status=429, body=None, retry_after=header)
    assert isinstance(err, RateLimitError)
    assert err.retry_after is not None
    assert 70.0 <= err.retry_after <= 90.5


def test_rate_limit_retry_after_ignored_for_non_429() -> None:
    # Other subclasses must not accept retry_after silently as an attribute.
    err = CerberusAPIError.from_response(status=500, body=None, retry_after="60")
    assert isinstance(err, ServerError)
    assert not hasattr(err, "retry_after")


# ---------------------------------------------------------------------------
# ValidationError.errors
# ---------------------------------------------------------------------------


def test_validation_error_errors_empty_when_missing() -> None:
    err = CerberusAPIError.from_response(status=422, body=None)
    assert isinstance(err, ValidationError)
    assert err.errors == []


def test_validation_error_errors_returns_list() -> None:
    body = {
        "title": "Unprocessable Entity",
        "errors": [
            {"field": "rut", "message": "invalid checksum"},
            {"field": "email", "message": "missing"},
        ],
    }
    err = CerberusAPIError.from_response(status=422, body=body)
    assert isinstance(err, ValidationError)
    assert err.errors == body["errors"]


# ---------------------------------------------------------------------------
# Sanity: raising and catching as ordinary exception
# ---------------------------------------------------------------------------


def test_can_be_raised_and_caught_as_base() -> None:
    with pytest.raises(CerberusAPIError) as exc_info:
        raise CerberusAPIError.from_response(status=401, body=None)
    assert isinstance(exc_info.value, AuthError)
    assert exc_info.value.status == 401
