"""Shared test fixtures: in-memory Jira Data Center REST v2 mock.

Serves the §3.1 tool endpoints and §4.4 error payloads defined in the specs.
Routes are keyed by ``(method, url path)``; query strings are ignored so tests
can pass any parameters. Tests override a route by calling ``MockRouter.route``
again with the same key.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx
import pytest

BASE_URL = "https://jira.example.test"
REST = f"{BASE_URL}/rest/api/2"

# --- §3.1 success payloads -------------------------------------------------

ISSUE_FIELDS: dict[str, Any] = {
    "summary": "Example issue",
    "description": "A sample issue body.",
    "status": {"name": "Open"},
    "assignee": {"displayName": "Ada Lovelace"},
    "priority": {"name": "High"},
    "issuetype": {"name": "Task"},
    "customfield_10001": 5,
}

ISSUE: dict[str, Any] = {
    "key": "PROJ-1",
    "fields": ISSUE_FIELDS,
    "transitions": [{"id": "31", "name": "In Progress"}],
}

SEARCH_OK: dict[str, Any] = {"issues": [ISSUE], "total": 1, "maxResults": 50}
CREATE_OK: dict[str, Any] = {"id": "10002", "key": "PROJ-2", "self": f"{REST}/issue/10002"}
COMMENT_OK: dict[str, Any] = {
    "id": "10010",
    "created": "2026-08-19T12:00:00.000+0000",
    "author": {"displayName": "Ada Lovelace"},
    "body": "First!",
}
COMMENTS_OK: dict[str, Any] = {"comments": [COMMENT_OK], "total": 1}
PROJECTS_OK: list[dict[str, Any]] = [
    {"key": "PROJ", "name": "Example Project", "issueTypes": [{"name": "Task", "subtask": False}]},
]
FIELDS_OK: list[dict[str, Any]] = [
    {"id": "summary", "name": "Summary", "custom": False, "schema": {"type": "string"}},
    {
        "id": "customfield_10001",
        "name": "Story Points",
        "custom": True,
        "schema": {"type": "number"},
        "allowedValues": [1, 2, 3, 5],
    },
]
MYSELF_OK: dict[str, Any] = {"key": "ada", "displayName": "Ada Lovelace", "active": True}

# --- §4.4 error payloads (Jira DC response shapes) -------------------------

AUTH_401: dict[str, Any] = {"errorMessages": ["Login refused"], "errors": {}}
FORBIDDEN_403: dict[str, Any] = {
    "errorMessages": ["You do not have the permission to see the specified issue."],
    "errors": {},
}
NOT_FOUND_404: dict[str, Any] = {"errorMessages": ["Issue Does Not Exist"], "errors": {}}
RATE_429: dict[str, Any] = {"errorMessages": ["Rate limit exceeded"], "errors": {}}
JQL_400: dict[str, Any] = {
    "errorMessages": ["The value 'bogus' does not exist for the field 'text'."],
    "errors": {},
}
VALIDATION_400: dict[str, Any] = {
    "errorMessages": [],
    "errors": {"summary": "You must specify a summary of the issue."},
}
SERVER_500: dict[str, Any] = {"errorMessages": ["Internal server error"], "errors": {}}

_RETRY_AFTER = {"Retry-After": "30"}


class MockRouter:
    """In-memory Jira mock keyed by ``(method, url path)``."""

    def __init__(self) -> None:
        self._routes: dict[tuple[str, str], httpx.Response] = {}

    def route(
        self,
        method: str,
        url: str,
        *,
        status: int = 200,
        payload: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Register or override a route. Last registration wins."""
        # Keys are matched against ``request.url.path`` in ``_handle``, so a
        # full URL is normalized to its path component.
        path = urlparse(url).path if "://" in url else url
        self._routes[(method.upper(), path)] = httpx.Response(
            status, json=payload, headers=headers or {}
        )

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._handle)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        key = (request.method.upper(), request.url.path)
        try:
            return self._routes[key]
        except KeyError:
            return httpx.Response(
                404,
                json={"errorMessages": [f"no mock route for {request.method} {request.url.path}"]},
            )


@pytest.fixture
def jira_mock() -> MockRouter:
    """Router pre-seeded with §3.1 success routes and §4.4 error routes.

    Error routes that must live on a success endpoint's path (401 on /myself,
    400-JQL on /search, 400-validation on POST /issue) are not pre-registered;
    tests override the success route with the matching payload constant, e.g.
    ``jira_mock.route("GET", f"{REST}/search", status=400, payload=JQL_400)``.
    """
    router = MockRouter()
    router.route("GET", f"{REST}/myself", payload=MYSELF_OK)
    router.route("GET", f"{REST}/search", payload=SEARCH_OK)
    router.route("GET", f"{REST}/issue/PROJ-1", payload=ISSUE)
    router.route("POST", f"{REST}/issue", status=201, payload=CREATE_OK)
    router.route("PUT", f"{REST}/issue/PROJ-1", status=204)
    router.route("POST", f"{REST}/issue/PROJ-1/transitions", status=204)
    router.route("POST", f"{REST}/issue/PROJ-1/comment", status=201, payload=COMMENT_OK)
    router.route("GET", f"{REST}/issue/PROJ-1/comment", payload=COMMENTS_OK)
    router.route("GET", f"{REST}/project", payload=PROJECTS_OK)
    router.route("GET", f"{REST}/field", payload=FIELDS_OK)
    # §4.4 error routes (distinct paths so they never shadow success routes)
    router.route("GET", f"{REST}/issue/PROJ-403", status=403, payload=FORBIDDEN_403)
    router.route("GET", f"{REST}/issue/PROJ-404", status=404, payload=NOT_FOUND_404)
    router.route(
        "GET", f"{REST}/issue/PROJ-429", status=429, payload=RATE_429, headers=_RETRY_AFTER
    )
    router.route("GET", f"{REST}/issue/PROJ-500", status=500, payload=SERVER_500)
    return router
