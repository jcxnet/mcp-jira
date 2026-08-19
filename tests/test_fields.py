"""Unit tests for mcp_jira.fields (FieldMap fetch, resolve, ambiguity, normalization)."""

from __future__ import annotations

import pytest
from conftest import BASE_URL, FIELDS_OK, REST

from mcp_jira.client import JiraClient
from mcp_jira.errors import JiraError
from mcp_jira.fields import FieldMap


def test_resolve_display_name_to_id() -> None:
    fm = FieldMap(FIELDS_OK)
    assert fm.resolve("Story Points") == "customfield_10001"


def test_resolve_raw_id_passes_through() -> None:
    fm = FieldMap(FIELDS_OK)
    assert fm.resolve("customfield_10001") == "customfield_10001"
    # Raw ids are sent unchanged even when not present in the map (spec scenario).
    assert fm.resolve("customfield_99999") == "customfield_99999"


def test_resolve_ambiguous_name_fails() -> None:
    fm = FieldMap(
        [
            {"id": "customfield_1", "name": "Dup", "custom": True},
            {"id": "customfield_2", "name": "Dup", "custom": True},
        ]
    )
    with pytest.raises(JiraError) as exc:
        fm.resolve("Dup")
    assert exc.value.code == "VALIDATION_ERROR"
    assert "ambiguous" in exc.value.message


def test_resolve_unknown_name_fails() -> None:
    fm = FieldMap(FIELDS_OK)
    with pytest.raises(JiraError) as exc:
        fm.resolve("Nope")
    assert exc.value.code == "VALIDATION_ERROR"


def test_allowed_values_normalized_to_list() -> None:
    fm = FieldMap(FIELDS_OK)
    fields = {f["id"]: f for f in fm.all_fields()}
    assert fields["customfield_10001"]["allowed_values"] == [1, 2, 3, 5]
    assert fields["summary"]["allowed_values"] == []


def test_from_http_fetches_and_caches(jira_mock) -> None:
    client = JiraClient(BASE_URL, "tok", transport=jira_mock.transport)
    fm = FieldMap.from_http(client)
    assert fm.resolve("Story Points") == "customfield_10001"
    assert fm.resolve("Summary") == "summary"


def test_from_http_non_list_raises_internal(jira_mock) -> None:
    jira_mock.route("GET", f"{REST}/field", status=200, payload={"nope": True})
    client = JiraClient(BASE_URL, "tok", transport=jira_mock.transport)
    with pytest.raises(JiraError) as exc:
        FieldMap.from_http(client)
    assert exc.value.code == "INTERNAL"
