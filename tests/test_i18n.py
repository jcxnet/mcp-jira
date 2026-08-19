"""Unit tests for mcp_jira.i18n (fallback to en, both locales render)."""

from __future__ import annotations

from mcp_jira.i18n import (
    LANGUAGES,
    MESSAGES,
    TOOL_IDS,
    message,
    tool_description,
    tool_name,
)


def test_supported_languages() -> None:
    assert LANGUAGES == ("en", "es")


def test_all_nine_tools_covered() -> None:
    assert TOOL_IDS == (
        "search_issues",
        "get_issue",
        "create_issue",
        "update_issue",
        "transition_issue",
        "add_comment",
        "get_comments",
        "list_projects",
        "list_fields",
    )


def test_en_tool_name_is_identifier() -> None:
    for tool in TOOL_IDS:
        assert tool_name(tool, "en") == tool


def test_es_tool_names_translated_and_unique() -> None:
    es_names = [tool_name(tool, "es") for tool in TOOL_IDS]
    assert len(set(es_names)) == len(es_names)
    assert tool_name("search_issues", "es") == "buscar_incidencias"


def test_descriptions_nonempty_in_both_locales() -> None:
    for tool in TOOL_IDS:
        assert tool_description(tool, "en")
        assert tool_description(tool, "es")


def test_unknown_language_falls_back_to_en() -> None:
    assert tool_name("search_issues", "fr") == "search_issues"
    assert tool_description("get_issue", "fr") == tool_description("get_issue", "en")
    assert message("SERVER_ERROR", "fr", status=500) == message("SERVER_ERROR", "en", status=500)


def test_es_table_covers_every_code() -> None:
    assert set(MESSAGES["es"]) >= set(MESSAGES["en"])


def test_message_renders_in_both_locales() -> None:
    assert "30s" in message("RATE_LIMITED", "en", retry_after="30s")
    assert "30s" in message("RATE_LIMITED", "es", retry_after="30s")
    assert (
        message("JQL_INVALID", "es", detail="campo no existe") == "JQL no válido: campo no existe."
    )


def test_verbatim_detail_not_translated() -> None:
    # Jira-provided detail stays verbatim even in es.
    out = message(
        "JQL_INVALID", "es", detail="The value 'bogus' does not exist for the field 'text'."
    )
    assert "The value 'bogus'" in out


def test_unknown_code_falls_back_safely() -> None:
    assert "Unexpected error" in message("NOPE", "en", detail="x")
    assert "Unexpected error" in message("NOPE", "es", detail="x")


def test_default_language_is_en() -> None:
    assert message("AUTH_UNAUTHORIZED") == message("AUTH_UNAUTHORIZED", "en")
