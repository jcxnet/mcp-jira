"""Integration tests for mcp_jira.client (retry policy, redaction, correlation id).

Uses the ``jira_mock`` router fixture plus local handlers where call counting
matters (MockTransport does not expose a call log). Backoff timing is verified
by monkeypatching ``time.sleep`` — one recorded 1.0s sleep proves the single
retry happened (sleeps only occur in the retry path).
"""

from __future__ import annotations

import logging

import httpx
import pytest
from conftest import AUTH_401, BASE_URL, REST

import mcp_jira.client as client_module
from mcp_jira.client import JiraClient
from mcp_jira.errors import JiraError


def _client(jira_mock, pat: str = "tok") -> JiraClient:
    return JiraClient(BASE_URL, pat, transport=jira_mock.transport)


def test_success_returns_parsed_json_and_sends_bearer_token() -> None:
    seen: dict[str, str | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("Authorization")
        return httpx.Response(200, json={"issues": []})

    client = JiraClient(BASE_URL, "tok123", transport=httpx.MockTransport(handler))
    assert client.request("GET", "/rest/api/2/search") == {"issues": []}
    assert seen["auth"] == "Bearer tok123"


def test_204_returns_none(jira_mock) -> None:
    assert _client(jira_mock).request("PUT", "/rest/api/2/issue/PROJ-1") is None


def test_5xx_retried_once_with_1s_backoff_then_server_error(jira_mock, monkeypatch) -> None:
    slept: list[float] = []
    monkeypatch.setattr(client_module.time, "sleep", slept.append)
    with pytest.raises(JiraError) as exc:
        _client(jira_mock).request("GET", "/rest/api/2/issue/PROJ-500")
    assert exc.value.code == "SERVER_ERROR"
    assert slept == [1.0]


def test_transport_error_retried_then_succeeds(jira_mock, monkeypatch) -> None:
    calls: list[httpx.Request] = []
    slept: list[float] = []
    monkeypatch.setattr(client_module.time, "sleep", slept.append)

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) == 1:
            raise httpx.ConnectError("conn refused", request=request)
        return httpx.Response(200, json={"issues": []})

    client = JiraClient(BASE_URL, "tok", transport=httpx.MockTransport(handler))
    assert client.request("GET", "/rest/api/2/search") == {"issues": []}
    assert len(calls) == 2
    assert slept == [1.0]


def test_transport_error_twice_raises_network_error(monkeypatch) -> None:
    slept: list[float] = []
    monkeypatch.setattr(client_module.time, "sleep", slept.append)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused", request=request)

    client = JiraClient(BASE_URL, "tok", transport=httpx.MockTransport(handler))
    with pytest.raises(JiraError) as exc:
        client.request("GET", "/rest/api/2/search")
    assert exc.value.code == "NETWORK_ERROR"
    assert "Connection refused" in exc.value.message
    assert slept == [1.0]


def test_401_wins_over_preceding_timeout(monkeypatch) -> None:
    calls: list[httpx.Request] = []
    slept: list[float] = []
    monkeypatch.setattr(client_module.time, "sleep", slept.append)

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) == 1:
            raise httpx.ReadTimeout("timed out", request=request)
        return httpx.Response(401, json=AUTH_401)

    client = JiraClient(BASE_URL, "tok", transport=httpx.MockTransport(handler))
    with pytest.raises(JiraError) as exc:
        client.request("GET", "/rest/api/2/issue/PROJ-1")
    assert exc.value.code == "AUTH_UNAUTHORIZED"
    assert len(calls) == 2
    assert slept == [1.0]


def test_429_never_retried(jira_mock, monkeypatch) -> None:
    slept: list[float] = []
    monkeypatch.setattr(client_module.time, "sleep", slept.append)
    with pytest.raises(JiraError) as exc:
        _client(jira_mock).request("GET", "/rest/api/2/issue/PROJ-429")
    assert exc.value.code == "RATE_LIMITED"
    assert "30s" in exc.value.message
    assert slept == []


def test_other_4xx_never_retried(jira_mock, monkeypatch) -> None:
    slept: list[float] = []
    monkeypatch.setattr(client_module.time, "sleep", slept.append)
    with pytest.raises(JiraError) as exc:
        _client(jira_mock).request("GET", "/rest/api/2/issue/PROJ-404")
    assert exc.value.code == "NOT_FOUND"
    assert slept == []


def test_logs_status_correlation_id_and_redacts_pat(jira_mock, caplog) -> None:
    caplog.set_level(logging.INFO)
    pat = "supersecretpat"
    jira_mock.route(
        "GET",
        f"{REST}/issue/PROJ-1",
        status=404,
        payload={"errorMessages": [f"missing {pat}"], "errors": {}},
        headers={"X-Arequestid": "corr-123"},
    )
    client = JiraClient(BASE_URL, pat, transport=jira_mock.transport)
    with pytest.raises(JiraError) as exc:
        client.request("GET", "/rest/api/2/issue/PROJ-1")
    assert pat not in caplog.text
    assert pat not in exc.value.message
    assert "404" in caplog.text
    assert "corr-123" in caplog.text
    assert "[REDACTED]" in caplog.text


def test_never_logs_to_stdout(jira_mock, capsys) -> None:
    with pytest.raises(JiraError):
        _client(jira_mock).request("GET", "/rest/api/2/issue/PROJ-500")
    assert capsys.readouterr().out == ""
