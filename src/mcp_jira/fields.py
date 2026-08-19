"""Field map for custom-field resolution (jira-tools §custom-field resolution).

Fetched once from ``GET /rest/api/2/field`` at startup and cached in memory.
:meth:`FieldMap.resolve` maps a display name to its raw id, passes raw
``customfield_XXXXX`` ids through unchanged, and fails with ``VALIDATION_ERROR``
on unknown or ambiguous names. ``allowed_values`` is normalized to ``[]`` when
omitted (design Risk 1).
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from mcp_jira.errors import EN_MESSAGES, JiraError

_CUSTOMFIELD_ID = re.compile(r"^customfield_\d+$")


class FieldMap:
    """In-memory index over the ``/rest/api/2/field`` response."""

    def __init__(self, fields: list[dict[str, Any]] | None = None) -> None:
        self._by_id: dict[str, dict[str, Any]] = {}
        self._by_name: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
        for field in fields or []:
            self._add(field)

    @classmethod
    def from_http(cls, client: Any) -> FieldMap:
        """Fetch and cache the field map via the HTTP client at startup."""
        fields = client.request("GET", "/rest/api/2/field")
        if not isinstance(fields, list):
            raise JiraError(
                "INTERNAL", EN_MESSAGES["INTERNAL"].format(detail="unexpected /field response")
            )
        return cls(fields)

    def resolve(self, key: str) -> str:
        """Resolve ``key`` to a raw field id; raw ``customfield_XXXXX`` ids pass through."""
        if _CUSTOMFIELD_ID.match(key):
            return key
        matches = self._by_name.get(key, [])
        if not matches:
            raise JiraError("VALIDATION_ERROR", _msg(f"Unknown field name '{key}'."))
        if len(matches) > 1:
            raise JiraError(
                "VALIDATION_ERROR",
                _msg(
                    f"Field name '{key}' is ambiguous ({len(matches)} matches); "
                    "use the raw customfield_XXXXX id."
                ),
            )
        return str(matches[0]["id"])

    def all_fields(self) -> list[dict[str, Any]]:
        """All indexed fields with ``allowed_values`` normalized to a list."""
        return list(self._by_id.values())

    def _add(self, field: dict[str, Any]) -> None:
        normalized = dict(field)
        allowed = normalized.get("allowedValues")
        normalized["allowed_values"] = allowed if isinstance(allowed, list) else []
        fid = normalized.get("id")
        name = normalized.get("name")
        if isinstance(fid, str):
            self._by_id[fid] = normalized
            if isinstance(name, str):
                self._by_name[name].append(normalized)


def _msg(detail: str) -> str:
    return EN_MESSAGES["VALIDATION_ERROR"].format(detail=detail)
