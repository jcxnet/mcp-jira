"""Integration tests for the 9 tool handlers (jira-tools §3.1 + read-only mode)."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from conftest import (
    AUTH_401,
    BASE_URL,
    COMMENT_OK,
    CREATE_OK,
    FIELDS_OK,
    ISSUE,
    REST,
    SEARCH_OK,
)

from mcp_jira.client import JiraClient
from mcp_jira.config import Settings
from mcp_jira.errors import JiraError
from mcp_jira.fields import FieldMap
from mcp_jira.tools import Tools

TRANSITIONS = {"transitions": [{"id": "31", "name": "In Progress"}, {"id": "41", "name": "Done"}]}
SETTINGS = Settings(BASE_URL, "tok")


def _tools(jira_mock, *, read_only: bool = False) -> Tools:
    client = JiraClient(BASE_URL, "tok", transport=jira_mock.transport)
    return Tools(client, FieldMap(FIELDS_OK), Settings(BASE_URL, "tok", read_only=read_only))


def _rec(handler: Callable[[httpx.Request], httpx.Response]) -> tuple[JiraClient, dict[str, Any]]:
    seen: dict[str, Any] = {}

    def wrap(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["params"] = dict(request.url.params)
        seen["json"] = request.content
        return handler(request)

    return JiraClient(BASE_URL, "tok", transport=httpx.MockTransport(wrap)), seen


# -- search_issues -----------------------------------------------------------


def test_search_defaults_and_caps_max_results() -> None:
    client, seen = _rec(lambda r: httpx.Response(200, json=SEARCH_OK))
    tools = Tools(client, FieldMap(FIELDS_OK), SETTINGS)
    tools.search_issues("jql")
    assert seen["params"]["maxResults"] == "50"
    tools.search_issues("jql", 500)
    assert seen["params"]["maxResults"] == "100"


def test_search_maps_output_contract(jira_mock) -> None:
    issue = _tools(jira_mock).search_issues("jql")["issues"][0]
    assert issue == {
        "key": "PROJ-1",
        "summary": "Example issue",
        "status": "Open",
        "assignee": "Ada Lovelace",
        "priority": "High",
        "issue_type": "Task",
    }


# -- get_issue ---------------------------------------------------------------


def test_get_issue_expands_transitions_and_selects_fields() -> None:
    client, seen = _rec(lambda r: httpx.Response(200, json=ISSUE))
    tools = Tools(client, FieldMap(FIELDS_OK), SETTINGS)
    result = tools.get_issue("PROJ-1")
    assert seen["params"]["expand"] == "transitions"
    assert result["transitions"] == [{"id": "31", "name": "In Progress"}]
    assert result["fields"]["customfield_10001"] == 5
    assert tools.get_issue("PROJ-1", fields=["Summary"])["fields"] == {"summary": "Example issue"}


def test_get_issue_ambiguous_field_name_fails() -> None:
    dup = [
        {"id": "customfield_1", "name": "Dup", "custom": True},
        {"id": "customfield_2", "name": "Dup", "custom": True},
    ]
    client, _ = _rec(lambda r: httpx.Response(200, json=ISSUE))
    tools = Tools(client, FieldMap(dup), SETTINGS)
    with pytest.raises(JiraError) as exc:
        tools.get_issue("PROJ-1", fields=["Dup"])
    assert exc.value.code == "VALIDATION_ERROR"


# -- create/update/transition/comment ---------------------------------------


def test_create_issue_returns_key_and_resolves_fields() -> None:
    client, seen = _rec(lambda r: httpx.Response(201, json=CREATE_OK))
    tools = Tools(client, FieldMap(FIELDS_OK), SETTINGS)
    assert tools.create_issue("PROJ", "Task", "New", fields={"Story Points": 5}) == {
        "key": "PROJ-2"
    }
    body = json.loads(seen["json"])["fields"]
    assert body["project"] == {"key": "PROJ"}
    assert body["issuetype"] == {"name": "Task"}
    assert body["customfield_10001"] == 5


def test_update_issue_raw_id_passes_through() -> None:
    client, seen = _rec(lambda r: httpx.Response(204))
    tools = Tools(client, FieldMap(FIELDS_OK), SETTINGS)
    assert tools.update_issue("PROJ-1", {"customfield_10001": 3}) == {"updated": True}
    assert json.loads(seen["json"])["fields"]["customfield_10001"] == 3


def test_transition_by_name_and_by_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json=TRANSITIONS)
        return httpx.Response(204)

    client, seen = _rec(handler)
    tools = Tools(client, FieldMap(FIELDS_OK), SETTINGS)
    assert tools.transition_issue("PROJ-1", "In Progress") == {"transitioned": True}
    assert json.loads(seen["json"]) == {"transition": {"id": "31"}}
    assert tools.transition_issue("PROJ-1", "41") == {"transitioned": True}
    assert json.loads(seen["json"]) == {"transition": {"id": "41"}}


def test_transition_invalid_lists_available() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json=TRANSITIONS)
        raise AssertionError("no POST expected for an invalid transition")

    client, _ = _rec(handler)
    tools = Tools(client, FieldMap(FIELDS_OK), SETTINGS)
    with pytest.raises(JiraError) as exc:
        tools.transition_issue("PROJ-1", "Nope")
    assert exc.value.code == "TRANSITION_INVALID"
    assert "In Progress" in exc.value.message
    assert "Done" in exc.value.message


def test_add_comment_returns_id_and_created() -> None:
    client, seen = _rec(lambda r: httpx.Response(201, json=COMMENT_OK))
    tools = Tools(client, FieldMap(FIELDS_OK), SETTINGS)
    assert tools.add_comment("PROJ-1", "First!") == {
        "id": "10010",
        "created": COMMENT_OK["created"],
    }
    assert json.loads(seen["json"]) == {"body": "First!"}


def test_get_comments_maps_author(jira_mock) -> None:
    assert _tools(jira_mock).get_comments("PROJ-1") == {
        "comments": [
            {
                "id": "10010",
                "author": "Ada Lovelace",
                "created": COMMENT_OK["created"],
                "body": "First!",
            }
        ]
    }


# -- list_projects / list_fields --------------------------------------------


def test_list_projects_maps_issue_types(jira_mock) -> None:
    assert _tools(jira_mock).list_projects() == {
        "projects": [{"key": "PROJ", "name": "Example Project", "issue_types": ["Task"]}]
    }


def test_list_fields_normalized_allowed_values(jira_mock) -> None:
    fields = {f["id"]: f for f in _tools(jira_mock).list_fields()["fields"]}
    assert fields["customfield_10001"]["allowed_values"] == [1, 2, 3, 5]
    assert fields["customfield_10001"]["type"] == "number"
    assert fields["customfield_10001"]["custom"] is True
    assert fields["summary"]["allowed_values"] == []


# -- read-only mode ----------------------------------------------------------


def test_read_only_blocks_mutations_without_http() -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"unexpected HTTP: {request.method} {request.url}")

    client = JiraClient(BASE_URL, "tok", transport=httpx.MockTransport(fail))
    tools = Tools(client, FieldMap(FIELDS_OK), Settings(BASE_URL, "tok", read_only=True))
    calls = [
        lambda: tools.create_issue("P", "Task", "s"),
        lambda: tools.update_issue("PROJ-1", {"summary": "x"}),
        lambda: tools.transition_issue("PROJ-1", "In Progress"),
        lambda: tools.add_comment("PROJ-1", "hi"),
    ]
    for call in calls:
        with pytest.raises(JiraError) as exc:
            call()
        assert exc.value.code == "READ_ONLY_MODE"


def test_read_only_reads_unaffected(jira_mock) -> None:
    tools = _tools(jira_mock, read_only=True)
    assert tools.search_issues("jql")["issues"][0]["key"] == "PROJ-1"
    assert tools.list_projects()["projects"][0]["key"] == "PROJ"


# -- error mapping through the tool -> client -> mapper chain ----------------


@pytest.mark.parametrize(
    ("key", "code"),
    [
        ("PROJ-401", "AUTH_UNAUTHORIZED"),
        ("PROJ-403", "AUTH_FORBIDDEN"),
        ("PROJ-404", "NOT_FOUND"),
        ("PROJ-429", "RATE_LIMITED"),
        ("PROJ-500", "SERVER_ERROR"),
    ],
)
def test_get_issue_maps_http_errors(jira_mock, key: str, code: str) -> None:
    if key == "PROJ-401":
        jira_mock.route("GET", f"{REST}/issue/PROJ-401", status=401, payload=AUTH_401)
    with pytest.raises(JiraError) as exc:
        _tools(jira_mock).get_issue(key)
    assert exc.value.code == code
