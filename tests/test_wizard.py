"""Unit tests for mcp_jira.wizard (0600 write, connectivity failure, non-interactive)."""

from __future__ import annotations

import json

from conftest import AUTH_401, BASE_URL, REST

from mcp_jira import wizard


def test_interactive_success_writes_0600_config(tmp_path, jira_mock, capsys) -> None:
    cfg = tmp_path / "config.json"
    code = wizard.run_wizard(
        config_path=cfg,
        interactive=True,
        prompt=lambda _: BASE_URL,
        hidden_prompt=lambda _: "tok",
        transport=jira_mock.transport,
    )
    assert code == 0
    assert (cfg.stat().st_mode & 0o777) == 0o600
    assert json.loads(cfg.read_text()) == {"jira_url": BASE_URL, "jira_pat": "tok"}
    assert "Config written" in capsys.readouterr().out


def test_connectivity_failure_reports_and_writes_nothing(tmp_path, jira_mock, capsys) -> None:
    jira_mock.route("GET", f"{REST}/myself", status=401, payload=AUTH_401)
    cfg = tmp_path / "config.json"
    code = wizard.run_wizard(
        config_path=cfg,
        interactive=True,
        prompt=lambda _: BASE_URL,
        hidden_prompt=lambda _: "bad-pat",
        transport=jira_mock.transport,
    )
    assert code == 1
    assert not cfg.exists()
    err = capsys.readouterr().err
    assert "Connection failed" in err
    assert "AUTH_UNAUTHORIZED" in err
    assert "bad-pat" not in err  # the PAT must never surface


def test_empty_prompt_writes_nothing(tmp_path, capsys) -> None:
    cfg = tmp_path / "config.json"
    code = wizard.run_wizard(
        config_path=cfg,
        interactive=True,
        prompt=lambda _: "   ",
        hidden_prompt=lambda _: "",
    )
    assert code == 1
    assert not cfg.exists()
    assert "required" in capsys.readouterr().err


def test_non_interactive_prints_path_and_exits_nonzero(tmp_path, capsys) -> None:
    cfg = tmp_path / "config.json"
    code = wizard.run_wizard(config_path=cfg, interactive=False)
    assert code == 1
    out = capsys.readouterr().out
    assert str(cfg) in out  # prints the config path
    assert "jira_url" in out  # guidance names the config keys
    assert not cfg.exists()
