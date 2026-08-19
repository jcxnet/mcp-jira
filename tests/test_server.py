"""Integration tests for mcp_jira.server (startup sequence + tool registration).

``create_server`` runs the fail-fast startup: config -> /myself -> /field ->
registration. Startup failures raise before any tool is registered, so the
"exposes no tools" guarantee is proven by the raised §4.4 code.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import AUTH_401, BASE_URL, REST, SERVER_500

from mcp_jira.errors import JiraError
from mcp_jira.i18n import TOOL_IDS
from mcp_jira.server import create_server


def _write_config(tmp_path: Path, **overrides: object) -> Path:
    data = {"jira_url": BASE_URL, "jira_pat": "tok", **overrides}
    path = tmp_path / "config.json"
    path.write_text(json.dumps(data))
    return path


def _names(app) -> list[str]:
    return [t.name for t in app._tool_manager.list_tools()]


def test_registers_all_nine_tools_with_en_names(jira_mock, tmp_path) -> None:
    app = create_server(config_path=_write_config(tmp_path), transport=jira_mock.transport)
    assert _names(app) == list(TOOL_IDS)


def test_es_language_switches_names_and_descriptions(jira_mock, tmp_path) -> None:
    app = create_server(
        config_path=_write_config(tmp_path, language="es"), transport=jira_mock.transport
    )
    tools = {t.name: t for t in app._tool_manager.list_tools()}
    assert "buscar_incidencias" in tools
    assert "Busca incidencias" in tools["buscar_incidencias"].description


def test_unknown_language_falls_back_to_en(jira_mock, tmp_path) -> None:
    app = create_server(
        config_path=_write_config(tmp_path, language="fr"), transport=jira_mock.transport
    )
    assert _names(app) == list(TOOL_IDS)


def test_read_only_still_registers_all_tools(jira_mock, tmp_path) -> None:
    app = create_server(
        config_path=_write_config(tmp_path, read_only=True), transport=jira_mock.transport
    )
    assert len(_names(app)) == 9


@pytest.mark.parametrize(
    ("kind", "code"),
    [
        ("absent", "CONFIG_MISSING"),
        ("no_pat", "CONFIG_MISSING"),
        ("malformed", "CONFIG_INVALID"),
    ],
)
def test_bad_config_fails_fast(tmp_path, kind: str, code: str) -> None:
    path = tmp_path / "config.json"
    if kind == "absent":
        path = tmp_path / "absent.json"
    elif kind == "no_pat":
        _write_config(tmp_path, jira_pat="")
    else:
        path.write_text("{not json")
    with pytest.raises(JiraError) as exc:
        create_server(config_path=path)
    assert exc.value.code == code


def test_myself_401_raises_auth_unauthorized(jira_mock, tmp_path) -> None:
    jira_mock.route("GET", f"{REST}/myself", status=401, payload=AUTH_401)
    with pytest.raises(JiraError) as exc:
        create_server(config_path=_write_config(tmp_path), transport=jira_mock.transport)
    assert exc.value.code == "AUTH_UNAUTHORIZED"


def test_field_cache_failure_fails_fast(jira_mock, tmp_path) -> None:
    jira_mock.route("GET", f"{REST}/field", status=500, payload=SERVER_500)
    with pytest.raises(JiraError) as exc:
        create_server(config_path=_write_config(tmp_path), transport=jira_mock.transport)
    assert exc.value.code == "SERVER_ERROR"
