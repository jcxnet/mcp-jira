"""Unit tests for mcp_jira.errors (§4.4 codes, 400 discriminator, precedence, redaction)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from mcp_jira.errors import (
    EN_MESSAGES,
    ERROR_PRECEDENCE,
    JiraError,
    _classify_400,
    map_http_error,
    network_error,
    redact_pat,
)


def test_error_precedence_matches_spec() -> None:
    assert ERROR_PRECEDENCE == (
        "CONFIG_MISSING",
        "CONFIG_INVALID",
        "AUTH_UNAUTHORIZED",
        "AUTH_FORBIDDEN",
        "RATE_LIMITED",
        "VALIDATION_ERROR",
        "JQL_INVALID",
        "TRANSITION_INVALID",
        "FIELD_NOT_EDITABLE",
        "NOT_FOUND",
        "SERVER_ERROR",
        "NETWORK_ERROR",
        "INTERNAL",
    )


def test_all_spec_codes_have_en_templates() -> None:
    assert set(ERROR_PRECEDENCE) | {"READ_ONLY_MODE"} <= set(EN_MESSAGES)


def test_jira_error_str_includes_code_and_message() -> None:
    err = JiraError("RATE_LIMITED", "Retry after 30s.")
    assert str(err) == "RATE_LIMITED: Retry after 30s."


def test_jira_error_is_frozen() -> None:
    err = JiraError("INTERNAL", "boom")
    with pytest.raises(FrozenInstanceError):
        err.code = "AUTH_UNAUTHORIZED"


def test_classify_400_errors_dict_wins() -> None:
    body = {"errors": {"summary": "missing"}, "errorMessages": ["bad field"]}
    assert _classify_400(body, "search") == "VALIDATION_ERROR"
    assert _classify_400(body, "issue") == "VALIDATION_ERROR"


def test_classify_400_jql_on_search() -> None:
    assert _classify_400({"errorMessages": ["bad field"], "errors": {}}, "search") == "JQL_INVALID"


def test_classify_400_endpoint_fallback() -> None:
    empty = {"errorMessages": [], "errors": {}}
    assert _classify_400(empty, "search") == "JQL_INVALID"
    assert _classify_400(empty, "issue") == "VALIDATION_ERROR"


def test_map_401_auth_unauthorized() -> None:
    assert map_http_error(401, {"errorMessages": ["Login refused"]}).code == "AUTH_UNAUTHORIZED"


def test_map_403_auth_forbidden() -> None:
    assert map_http_error(403).code == "AUTH_FORBIDDEN"


def test_map_404_not_found_keeps_verbatim_detail() -> None:
    err = map_http_error(404, {"errorMessages": ["Issue Does Not Exist"]})
    assert err.code == "NOT_FOUND"
    assert "Issue Does Not Exist" in err.message


def test_map_429_surfaces_retry_after() -> None:
    err = map_http_error(429, headers={"Retry-After": "30"})
    assert err.code == "RATE_LIMITED"
    assert "30s" in err.message


def test_map_429_without_header() -> None:
    assert "unknown" in map_http_error(429).message


def test_map_400_validation_keeps_field_errors_verbatim() -> None:
    body = {"errors": {"summary": "You must specify a summary of the issue."}}
    err = map_http_error(400, body)
    assert err.code == "VALIDATION_ERROR"
    assert "You must specify a summary" in err.message


def test_map_400_jql_keeps_message_verbatim() -> None:
    body = {"errorMessages": ["The value 'bogus' does not exist for the field 'text'."]}
    err = map_http_error(400, body, endpoint="search")
    assert err.code == "JQL_INVALID"
    assert "bogus" in err.message


def test_map_400_errors_win_over_jql_signal() -> None:
    # VALIDATION_* outranks the JQL hint within a single 400 (design Risk 2).
    body = {"errors": {"summary": "x"}, "errorMessages": ["bad field"]}
    assert map_http_error(400, body, endpoint="search").code == "VALIDATION_ERROR"


def test_map_500_server_error_includes_status() -> None:
    err = map_http_error(500)
    assert err.code == "SERVER_ERROR"
    assert "500" in err.message


def test_map_unhandled_status_internal() -> None:
    assert map_http_error(418).code == "INTERNAL"


def test_map_http_error_localized_messages() -> None:
    es = {"SERVER_ERROR": "Error del servidor de Jira ({status})."}
    err = map_http_error(500, messages=es)
    assert err.code == "SERVER_ERROR"
    assert "Error del servidor" in err.message


def test_redact_pat_replaces_all_occurrences() -> None:
    assert redact_pat("token abc secret abc", "abc") == "token [REDACTED] secret [REDACTED]"


def test_redact_pat_empty_noop() -> None:
    assert redact_pat("keep secret", "") == "keep secret"


def test_map_http_error_redacts_pat_from_message() -> None:
    pat = "supersecretpat"
    err = map_http_error(404, {"errorMessages": [f"Issue {pat} missing"]}, pat=pat)
    assert pat not in err.message
    assert "[REDACTED]" in err.message


def test_network_error() -> None:
    err = network_error("https://jira.example.test", "Connection refused")
    assert err.code == "NETWORK_ERROR"
    assert "https://jira.example.test" in err.message
    assert "Connection refused" in err.message
