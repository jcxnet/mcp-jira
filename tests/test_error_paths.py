"""Mocked error-path suite (task 6.1): every tool error path maps to §4.4 codes.

End-to-end through the tool -> client -> mapper chain, proving the behavior the
unit tests (test_errors.py) describe in isolation: 401/403/404/429/400-JQL/
400-validation/500 codes, the 400 payload discriminator, retry-once and
429-never-retried policy, read-only guard, and the PRD §3.2 security check
(PAT never leaks across logs or surfaced errors for every tool and status).
``list_fields`` reads the cached FieldMap and never performs HTTP, so it has no
error path. Frozen JiraError assertions stay inside ``pytest.raises`` (a frozen
error escaping a test unhandled triggers FrozenInstanceError on this runtime).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from conftest import (
    AUTH_401,
    BASE_URL,
    FIELDS_OK,
    JQL_400,
    RATE_429,
    REST,
    SERVER_500,
    VALIDATION_400,
)

import mcp_jira.client as client_module
from mcp_jira.client import JiraClient
from mcp_jira.config import Settings
from mcp_jira.errors import JiraError
from mcp_jira.fields import FieldMap
from mcp_jira.tools import Tools

SETTINGS = Settings(BASE_URL, "tok")

# (tool, method, url, invoke, is_search) — list_fields excluded: it reads the
# cached FieldMap and never touches HTTP.
_TOOL_ROUTES: list[tuple[str, str, str, Callable[[Tools], Any], bool]] = [
    ("search_issues", "GET", f"{REST}/search", lambda t: t.search_issues("jql"), True),
    ("get_issue", "GET", f"{REST}/issue/PROJ-1", lambda t: t.get_issue("PROJ-1"), False),
    (
        "create_issue",
        "POST",
        f"{REST}/issue",
        lambda t: t.create_issue("PROJ", "Task", "s"),
        False,
    ),
    (
        "update_issue",
        "PUT",
        f"{REST}/issue/PROJ-1",
        lambda t: t.update_issue("PROJ-1", {"Summary": "x"}),
        False,
    ),
    (
        "transition_issue",
        "GET",
        f"{REST}/issue/PROJ-1/transitions",
        lambda t: t.transition_issue("PROJ-1", "In Progress"),
        False,
    ),
    (
        "add_comment",
        "POST",
        f"{REST}/issue/PROJ-1/comment",
        lambda t: t.add_comment("PROJ-1", "hi"),
        False,
    ),
    (
        "get_comments",
        "GET",
        f"{REST}/issue/PROJ-1/comment",
        lambda t: t.get_comments("PROJ-1"),
        False,
    ),
    ("list_projects", "GET", f"{REST}/project", lambda t: t.list_projects(), False),
]

STATUSES = (400, 401, 403, 404, 429, 500)


def _expected_code(status: int, is_search: bool) -> str:
    return {
        401: "AUTH_UNAUTHORIZED",
        403: "AUTH_FORBIDDEN",
        404: "NOT_FOUND",
        429: "RATE_LIMITED",
        500: "SERVER_ERROR",
    }.get(status) or ("JQL_INVALID" if is_search else "VALIDATION_ERROR")


def _error_body(status: int, pat: str, is_search: bool) -> dict[str, Any]:
    """§4.4 payload shape per status; the PAT is echoed by the "server" in
    every body so the security check proves it never surfaces anywhere."""
    if status == 400:
        if is_search:
            return {"errorMessages": [f"bad field {pat}"], "errors": {}}
        return {"errorMessages": [], "errors": {"summary": f"summary {pat} missing"}}
    if status == 401:
        return {"errorMessages": [f"login refused for {pat}"], "errors": {}}
    if status == 403:
        return {"errorMessages": [f"forbidden for {pat}"], "errors": {}}
    if status == 404:
        return {"errorMessages": [f"missing {pat}"], "errors": {}}
    if status == 429:
        return {"errorMessages": [f"rate {pat}"], "errors": {}}
    return {"errorMessages": [f"server {pat}"], "errors": {}}


def _tools(jira_mock, pat: str = "tok") -> Tools:
    client = JiraClient(BASE_URL, pat, transport=jira_mock.transport)
    return Tools(client, FieldMap(FIELDS_OK), Settings(BASE_URL, pat))


# -- 400 discriminator through the tool chain ---------------------------------


def test_search_400_jql_maps_to_jql_invalid_with_verbatim(jira_mock) -> None:
    jira_mock.route("GET", f"{REST}/search", status=400, payload=JQL_400)
    with pytest.raises(JiraError) as exc:
        _tools(jira_mock).search_issues("bogus")
    assert exc.value.code == "JQL_INVALID"
    assert "bogus" in exc.value.message


def test_create_400_validation_keeps_field_errors_verbatim(jira_mock) -> None:
    jira_mock.route("POST", f"{REST}/issue", status=400, payload=VALIDATION_400)
    with pytest.raises(JiraError) as exc:
        _tools(jira_mock).create_issue("PROJ", "Task", "New")
    assert exc.value.code == "VALIDATION_ERROR"
    assert "You must specify a summary" in exc.value.message


def test_400_discriminator_errors_dict_wins_on_search(jira_mock) -> None:
    # Both signals present: the errors dict outranks the JQL hint (design Risk 2).
    jira_mock.route(
        "GET",
        f"{REST}/search",
        status=400,
        payload={"errorMessages": ["bad field"], "errors": {"summary": "must be set"}},
    )
    with pytest.raises(JiraError) as exc:
        _tools(jira_mock).search_issues("x")
    assert exc.value.code == "VALIDATION_ERROR"


# -- retry policy and precedence through the tool chain -----------------------


def test_5xx_retried_once_through_tool(monkeypatch) -> None:
    calls: list[httpx.Request] = []
    slept: list[float] = []
    monkeypatch.setattr(client_module.time, "sleep", slept.append)

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(500, json=SERVER_500)

    client = JiraClient(BASE_URL, "tok", transport=httpx.MockTransport(handler))
    tools = Tools(client, FieldMap(FIELDS_OK), SETTINGS)
    with pytest.raises(JiraError) as exc:
        tools.search_issues("jql")
    assert exc.value.code == "SERVER_ERROR"
    assert len(calls) == 2
    assert slept == [1.0]


def test_429_never_retried_through_tool(monkeypatch) -> None:
    calls: list[httpx.Request] = []
    slept: list[float] = []
    monkeypatch.setattr(client_module.time, "sleep", slept.append)

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(429, json=RATE_429, headers={"Retry-After": "30"})

    client = JiraClient(BASE_URL, "tok", transport=httpx.MockTransport(handler))
    tools = Tools(client, FieldMap(FIELDS_OK), SETTINGS)
    with pytest.raises(JiraError) as exc:
        tools.search_issues("jql")
    assert exc.value.code == "RATE_LIMITED"
    assert "30s" in exc.value.message
    assert len(calls) == 1
    assert slept == []


def test_401_wins_over_transport_timeout_through_tool(monkeypatch) -> None:
    # §4.4 precedence: auth outranks the preceding network error.
    calls: list[httpx.Request] = []
    slept: list[float] = []
    monkeypatch.setattr(client_module.time, "sleep", slept.append)

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) == 1:
            raise httpx.ReadTimeout("timed out", request=request)
        return httpx.Response(401, json=AUTH_401)

    client = JiraClient(BASE_URL, "tok", transport=httpx.MockTransport(handler))
    tools = Tools(client, FieldMap(FIELDS_OK), SETTINGS)
    with pytest.raises(JiraError) as exc:
        tools.search_issues("jql")
    assert exc.value.code == "AUTH_UNAUTHORIZED"
    assert len(calls) == 2
    assert slept == [1.0]


# -- read-only guard ----------------------------------------------------------


def test_read_only_guard_blocks_without_http_and_redacts(jira_mock) -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"unexpected HTTP: {request.method} {request.url}")

    client = JiraClient(BASE_URL, "tok", transport=httpx.MockTransport(fail))
    tools = Tools(client, FieldMap(FIELDS_OK), Settings(BASE_URL, "tok", read_only=True))
    for call in (
        lambda: tools.create_issue("P", "Task", "s"),
        lambda: tools.update_issue("PROJ-1", {"summary": "x"}),
        lambda: tools.transition_issue("PROJ-1", "In Progress"),
        lambda: tools.add_comment("PROJ-1", "hi"),
    ):
        with pytest.raises(JiraError) as exc:
            call()
        assert exc.value.code == "READ_ONLY_MODE"
        assert "tok" not in exc.value.message


# -- security sweep: every tool x every error status, PAT never leaks ---------


@pytest.mark.parametrize("status", STATUSES)
@pytest.mark.parametrize(
    ("tool", "method", "url", "invoke", "is_search"),
    _TOOL_ROUTES,
)
def test_every_tool_error_path_maps_and_never_leaks_pat(
    jira_mock,
    caplog,
    monkeypatch,
    status: int,
    tool: str,
    method: str,
    url: str,
    invoke: Callable[[Tools], Any],
    is_search: bool,
) -> None:
    pat = "supersecretpat"
    monkeypatch.setattr(client_module.time, "sleep", lambda _: None)  # 500 retry would sleep
    caplog.set_level(logging.INFO)
    jira_mock.route(
        method,
        url,
        status=status,
        payload=_error_body(status, pat, is_search),
        headers={"Retry-After": "30"} if status == 429 else None,
    )
    tools = _tools(jira_mock, pat=pat)
    with pytest.raises(JiraError) as exc:
        invoke(tools)
    assert exc.value.code == _expected_code(status, is_search)
    assert pat not in exc.value.message
    assert pat not in caplog.text
    if status == 429:
        assert "30s" in exc.value.message
    if status in (400, 404):  # detail-bearing templates exercise redaction
        assert "[REDACTED]" in exc.value.message
