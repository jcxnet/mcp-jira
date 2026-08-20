"""Unit tests for mcp_jira.wizard (non-TTY gate + 0600 write semantics).

The interactive flow is covered by Textual Pilot tests in ``test_tui_setup.py``;
this file pins the non-TTY branch byte-identical and the ``_write_config``
write semantics (spec server-config §Wizard testability).
"""

from __future__ import annotations

import json

from mcp_jira import wizard


def test_non_interactive_prints_path_and_exits_nonzero(tmp_path, capsys) -> None:
    cfg = tmp_path / "config.json"
    code = wizard.run_wizard(config_path=cfg, interactive=False)
    assert code == 1
    out = capsys.readouterr().out
    assert str(cfg) in out  # prints the config path
    assert "jira_url" in out  # guidance names the config keys
    assert not cfg.exists()


def test_non_interactive_defaults_to_tty_detection(tmp_path, capsys) -> None:
    # pytest capture is never a TTY, so run_wizard() with no kwargs must take
    # the non-TTY branch via _is_interactive() (design D-TTY).
    cfg = tmp_path / "config.json"
    code = wizard.run_wizard(config_path=cfg)
    assert code == 1
    out = capsys.readouterr().out
    assert str(cfg) in out
    assert not cfg.exists()


def test_write_config_writes_four_keys_0600(tmp_path) -> None:
    cfg = tmp_path / "config.json"
    wizard._write_config(
        cfg,
        jira_url="https://jira.example.test",
        jira_pat="tok",
        language="en",
        read_only=False,
    )
    assert (cfg.stat().st_mode & 0o777) == 0o600
    assert json.loads(cfg.read_text()) == {
        "jira_url": "https://jira.example.test",
        "jira_pat": "tok",
        "language": "en",
        "read_only": False,
    }


def test_write_config_enforces_0600_on_preexisting_loose_perms(tmp_path) -> None:
    cfg = tmp_path / "config.json"
    cfg.write_text('{"jira_url": "old"}')
    cfg.chmod(0o644)
    wizard._write_config(cfg, jira_url="u", jira_pat="p", language="en", read_only=True)
    assert (cfg.stat().st_mode & 0o777) == 0o600  # os.chmod enforcement


def test_write_config_creates_parent_dirs(tmp_path) -> None:
    cfg = tmp_path / "nested" / "dir" / "config.json"
    wizard._write_config(cfg, jira_url="u", jira_pat="p", language="es", read_only=True)
    assert json.loads(cfg.read_text()) == {
        "jira_url": "u",
        "jira_pat": "p",
        "language": "es",
        "read_only": True,
    }


def test_write_config_overwrites_existing_contents(tmp_path) -> None:
    cfg = tmp_path / "config.json"
    cfg.write_text('{"stale": true}')
    wizard._write_config(cfg, jira_url="u", jira_pat="p", language="en", read_only=False)
    assert json.loads(cfg.read_text()) == {
        "jira_url": "u",
        "jira_pat": "p",
        "language": "en",
        "read_only": False,
    }
