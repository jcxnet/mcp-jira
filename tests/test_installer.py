"""Tests for mcp_jira.installer (merge/backup/validate, flow control, secrets).

Injectable-driven like test_wizard: tmp_path configs, no real home writes.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from mcp_jira import installer

FKEY = "sk-figma-1234"
CLAUDE_ENTRY = {"command": sys.executable, "args": ["-m", "mcp_jira"]}
OPENCODE_ENTRY = {
    "type": "local",
    "command": [sys.executable, "-m", "mcp_jira"],
    "enabled": True,
}


def _fake_paths(tmp_path: Path) -> dict[str, Path]:
    return {
        "opencode": tmp_path / "opencode.json",
        "claude": tmp_path / "claude.json",
        "desktop": tmp_path / "claude_desktop_config.json",
    }


def _install(
    paths: dict[str, Path],
    *,
    targets: str = "",
    confirm_answer: str = "y",
) -> int:
    return installer.run_installer(
        interactive=True,
        config_paths=lambda: paths,
        targets_selected=lambda p, o, d: targets,
        confirm=lambda p: confirm_answer,
    )


# --- 4.1 integration: all targets, merge, modes, .bak, idempotency ----------


def test_install_merges_all_targets_preserves_secrets_and_modes(tmp_path, capsys) -> None:
    paths = _fake_paths(tmp_path)
    paths["opencode"].write_text(
        json.dumps(
            {
                "mcp": {
                    "figma": {"type": "local", "command": ["figma"], "env": {"FIGMA_API_KEY": FKEY}}
                }
            }
        )
    )
    paths["claude"].write_text(
        json.dumps({"state": "keep", "mcpServers": {"other": {"command": "x"}}})
    )
    os.chmod(paths["claude"], 0o600)
    orig_claude = paths["claude"].read_bytes()

    assert _install(paths) == 0

    oc = json.loads(paths["opencode"].read_text())
    assert oc["mcp"]["figma"]["env"]["FIGMA_API_KEY"] == FKEY
    assert oc["mcp"]["mcp-jira"] == OPENCODE_ENTRY
    cl = json.loads(paths["claude"].read_text())
    assert cl["state"] == "keep"
    assert cl["mcpServers"]["other"] == {"command": "x"}
    assert cl["mcpServers"]["mcp-jira"] == CLAUDE_ENTRY
    dt = json.loads(paths["desktop"].read_text())
    assert dt["mcpServers"]["mcp-jira"] == CLAUDE_ENTRY

    assert (paths["claude"].stat().st_mode & 0o777) == 0o600  # mode preserved
    assert (paths["desktop"].stat().st_mode & 0o777) == 0o644  # new file
    bak = paths["claude"].with_suffix(".json.bak")
    assert bak.read_bytes() == orig_claude  # backup holds the pre-merge original
    assert not paths["desktop"].with_suffix(".json.bak").exists()  # new file: no backup

    out = capsys.readouterr().out
    assert "Registered mcp-jira in" in out
    assert FKEY not in out


def test_install_idempotent_rerun_reports_already_registered(tmp_path, capsys) -> None:
    paths = _fake_paths(tmp_path)
    paths["claude"].write_text(json.dumps({"mcpServers": {}}))
    assert _install(paths) == 0
    after_first = {p: p.read_bytes() for p in paths.values()}

    assert _install(paths) == 0
    assert all(p.read_bytes() == b for p, b in after_first.items())  # unchanged
    out = capsys.readouterr().out
    assert out.count("already registered") == 3
    assert "Nothing to register." in out


def test_select_subset_writes_only_selected(tmp_path) -> None:
    paths = _fake_paths(tmp_path)
    assert _install(paths, targets="2") == 0
    assert not paths["opencode"].exists()
    assert not paths["desktop"].exists()
    assert "mcp-jira" in json.loads(paths["claude"].read_text())["mcpServers"]


# --- 4.2 unit: load_json / upsert_client / write_with_backup / probe ---------


def test_load_json_missing_returns_none(tmp_path) -> None:
    assert installer.load_json(tmp_path / "nope.json") is None


def test_load_json_corrupt_raises(tmp_path) -> None:
    p = tmp_path / "broken.json"
    p.write_text("{not json")
    with pytest.raises(ValueError):
        installer.load_json(p)


def test_upsert_client_existing_returns_false_and_untouched() -> None:
    cfg = {"mcpServers": {"mcp-jira": {"command": "x"}}}
    assert installer.upsert_client(cfg, "mcpServers", CLAUDE_ENTRY) is False
    assert cfg["mcpServers"]["mcp-jira"] == {"command": "x"}


def test_upsert_client_adds_and_creates_container() -> None:
    cfg: dict = {}
    assert installer.upsert_client(cfg, "mcp", OPENCODE_ENTRY) is True
    assert cfg == {"mcp": {"mcp-jira": OPENCODE_ENTRY}}


def test_write_with_backup_new_file_0644(tmp_path) -> None:
    p = tmp_path / "new.json"
    installer.write_with_backup(p, {"a": 1})
    assert (p.stat().st_mode & 0o777) == 0o644
    assert json.loads(p.read_text()) == {"a": 1}
    assert not p.with_suffix(".json.bak").exists()


def test_write_with_backup_backup_once_and_preserves_mode(tmp_path) -> None:
    p = tmp_path / "cfg.json"
    p.write_text('{"keep": true}')
    os.chmod(p, 0o600)
    installer.write_with_backup(p, {"keep": True, "mcp-jira": {"a": 1}})
    bak = p.with_suffix(".json.bak")
    assert json.loads(bak.read_text()) == {"keep": True}  # original, not overwritten later
    assert (p.stat().st_mode & 0o777) == 0o600
    installer.write_with_backup(p, {"keep": True, "mcp-jira": {"a": 2}})
    assert json.loads(bak.read_text()) == {"keep": True}  # .bak created once


def test_write_with_backup_corrupt_write_restores_bak(tmp_path, monkeypatch) -> None:
    p = tmp_path / "cfg.json"
    p.write_text('{"keep": true}')
    monkeypatch.setattr(installer.json, "dumps", lambda *a, **k: "{corrupted")
    with pytest.raises(ValueError):
        installer.write_with_backup(p, {"x": 1})
    assert json.loads(p.read_text()) == {"keep": True}  # restored from .bak


def test_write_with_backup_corrupt_new_file_removed(tmp_path, monkeypatch) -> None:
    p = tmp_path / "new.json"
    monkeypatch.setattr(installer.json, "dumps", lambda *a, **k: "{corrupted")
    with pytest.raises(ValueError):
        installer.write_with_backup(p, {})
    assert not p.exists()


def test_probe_desktop_dir_capital_wins(tmp_path) -> None:
    cap = tmp_path / ".config" / "Claude"
    cap.mkdir(parents=True)
    (tmp_path / ".config" / "claude").mkdir()
    assert installer.probe_desktop_dir(tmp_path) == cap


def test_probe_desktop_dir_lowercase_used(tmp_path) -> None:
    low = tmp_path / ".config" / "claude"
    low.mkdir(parents=True)
    assert installer.probe_desktop_dir(tmp_path) == low


def test_probe_desktop_dir_default_capital(tmp_path) -> None:
    assert installer.probe_desktop_dir(tmp_path) == tmp_path / ".config" / "Claude"


# --- 4.3 flow: non-TTY, ^C, decline, corrupt skip, secrets -------------------


def test_non_interactive_prints_guidance_exits_1(tmp_path, capsys) -> None:
    code = installer.run_installer(interactive=False, config_paths=lambda: _fake_paths(tmp_path))
    assert code == 1
    assert "terminal" in capsys.readouterr().out


def test_ctrl_c_at_selection_aborts_without_writing(tmp_path, capsys) -> None:
    paths = _fake_paths(tmp_path)

    def boom(p: str, o: object, d: str) -> str:
        raise KeyboardInterrupt

    code = installer.run_installer(
        interactive=True, config_paths=lambda: paths, targets_selected=boom
    )
    assert code == 1
    assert not any(p.exists() for p in paths.values())
    assert "Aborted" in capsys.readouterr().err


def test_declined_confirm_writes_nothing(tmp_path, capsys) -> None:
    paths = _fake_paths(tmp_path)
    assert _install(paths, confirm_answer="") == 1
    assert not any(p.exists() for p in paths.values())
    assert "nothing was written" in capsys.readouterr().err


def test_corrupt_config_skipped_untouched(tmp_path, capsys) -> None:
    paths = _fake_paths(tmp_path)
    paths["opencode"].write_text("{broken")
    assert _install(paths) == 0
    assert paths["opencode"].read_text() == "{broken"
    assert "mcp-jira" in json.loads(paths["claude"].read_text())["mcpServers"]
    captured = capsys.readouterr()
    assert "not valid JSON" in captured.err
    assert FKEY not in captured.out
