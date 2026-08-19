"""Nine Jira REST v2 tool handlers (jira-tools §3.1 contracts) + read-only guard.

Handlers consume ``JiraClient`` (retry + §4.4 error mapping), ``FieldMap``
(custom-field resolution in get/create/update), i18n messages, and ``Settings``.
Mutating tools (create/update/transition/add_comment) raise ``READ_ONLY_MODE``
before any HTTP when ``read_only`` is set (jira-tools §read-only mode).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mcp_jira import i18n
from mcp_jira.client import JiraClient
from mcp_jira.config import Settings
from mcp_jira.errors import JiraError
from mcp_jira.fields import FieldMap

_SEARCH_PATH = "/rest/api/2/search"
_MAX_RESULTS = 100
_DEFAULT_MAX_RESULTS = 50


def _name(obj: Any, key: str = "name") -> Any:
    return obj.get(key) if isinstance(obj, dict) else None


class Tools:
    """Binds the 9 tool handlers to a client, a field map, and settings."""

    def __init__(self, client: JiraClient, fields: FieldMap, settings: Settings) -> None:
        self._client = client
        self._fields = fields
        self._settings = settings

    def _guard(self) -> None:
        if self._settings.read_only:
            raise JiraError(
                "READ_ONLY_MODE",
                i18n.message("READ_ONLY_MODE", self._settings.language),
            )

    def _resolve(self, fields: Mapping[str, Any]) -> dict[str, Any]:
        return {self._fields.resolve(name): value for name, value in fields.items()}

    # -- tools --------------------------------------------------------------

    def search_issues(self, jql: str, max_results: int = _DEFAULT_MAX_RESULTS) -> dict[str, Any]:
        """Search issues by JQL (max_results capped at 100)."""
        data = self._client.request(
            "GET",
            _SEARCH_PATH,
            params={
                "jql": jql,
                "maxResults": max(1, min(max_results, _MAX_RESULTS)),
            },
        )
        issues = []
        for issue in data.get("issues") or []:
            flds = issue.get("fields") or {}
            issues.append(
                {
                    "key": issue.get("key"),
                    "summary": flds.get("summary"),
                    "status": _name(flds.get("status")),
                    "assignee": _name(flds.get("assignee"), "displayName"),
                    "priority": _name(flds.get("priority")),
                    "issue_type": _name(flds.get("issuetype")),
                }
            )
        return {"issues": issues}

    def get_issue(self, issue_key: str, fields: list[str] | None = None) -> dict[str, Any]:
        """Get an issue; ``fields`` selects returned field ids by name or raw id."""
        selected = {self._fields.resolve(name) for name in fields} if fields else None
        data = self._client.request(
            "GET",
            f"/rest/api/2/issue/{issue_key}",
            params={"expand": "transitions"},
        )
        flds = data.get("fields") or {}
        if selected is not None:
            flds = {k: v for k, v in flds.items() if k in selected}
        return {
            "key": data.get("key"),
            "summary": flds.get("summary"),
            "description": flds.get("description"),
            "status": _name(flds.get("status")),
            "assignee": _name(flds.get("assignee"), "displayName"),
            "priority": _name(flds.get("priority")),
            "fields": flds,
            "transitions": data.get("transitions"),
        }

    def create_issue(
        self,
        project_key: str,
        issue_type: str,
        summary: str,
        description: str = "",
        fields: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create an issue; custom fields by display name or raw id."""
        self._guard()
        payload = {
            "fields": {
                "project": {"key": project_key},
                "issuetype": {"name": issue_type},
                "summary": summary,
                "description": description,
            }
        }
        if fields:
            payload["fields"].update(self._resolve(fields))
        data = self._client.request("POST", "/rest/api/2/issue", json=payload)
        return {"key": data.get("key")}

    def update_issue(self, issue_key: str, fields: dict[str, Any]) -> dict[str, Any]:
        """Update issue fields; custom fields by display name or raw id."""
        self._guard()
        self._client.request(
            "PUT",
            f"/rest/api/2/issue/{issue_key}",
            json={"fields": self._resolve(fields)},
        )
        return {"updated": True}

    def transition_issue(self, issue_key: str, transition: str) -> dict[str, Any]:
        """Transition an issue by transition name or id."""
        self._guard()
        data = self._client.request("GET", f"/rest/api/2/issue/{issue_key}/transitions")
        available = data.get("transitions") or []
        found = next(
            (
                t
                for t in available
                if str(t.get("id")) == transition
                or str(t.get("name", "")).lower() == transition.lower()
            ),
            None,
        )
        if found is None:
            names = ", ".join(str(t.get("name")) for t in available) or "none"
            raise JiraError(
                "TRANSITION_INVALID",
                i18n.message(
                    "TRANSITION_INVALID",
                    self._settings.language,
                    name=transition,
                    available=names,
                ),
            )
        self._client.request(
            "POST",
            f"/rest/api/2/issue/{issue_key}/transitions",
            json={"transition": {"id": found.get("id")}},
        )
        return {"transitioned": True}

    def add_comment(self, issue_key: str, body: str) -> dict[str, Any]:
        """Add a comment to an issue."""
        self._guard()
        data = self._client.request(
            "POST",
            f"/rest/api/2/issue/{issue_key}/comment",
            json={"body": body},
        )
        return {"id": data.get("id"), "created": data.get("created")}

    def get_comments(self, issue_key: str) -> dict[str, Any]:
        """List comments on an issue."""
        data = self._client.request("GET", f"/rest/api/2/issue/{issue_key}/comment")
        return {
            "comments": [
                {
                    "id": c.get("id"),
                    "author": _name(c.get("author"), "displayName"),
                    "created": c.get("created"),
                    "body": c.get("body"),
                }
                for c in data.get("comments") or []
            ]
        }

    def list_projects(self) -> dict[str, Any]:
        """List projects with keys, names, and issue types."""
        data = self._client.request("GET", "/rest/api/2/project")
        return {
            "projects": [
                {
                    "key": p.get("key"),
                    "name": p.get("name"),
                    "issue_types": [it.get("name") for it in p.get("issueTypes") or []],
                }
                for p in data or []
            ]
        }

    def list_fields(self) -> dict[str, Any]:
        """List all fields from the cached map (allowed_values normalized)."""
        return {
            "fields": [
                {
                    "id": f.get("id"),
                    "name": f.get("name"),
                    "custom": f.get("custom"),
                    "type": (f.get("schema") or {}).get("type"),
                    "allowed_values": f.get("allowed_values"),
                }
                for f in self._fields.all_fields()
            ]
        }
