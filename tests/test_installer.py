"""Unit tests for mcp_jira.installer (merge/backup/validate, TTY gate, targets).

The interactive flow is covered by Textual Pilot tests in ``test_tui_install.py``;
this file pins the non-TTY branch byte-identical and the pure functions
(``load_json``/``upsert_client``/``write_with_backup``/``probe_desktop_dir``/
``_resolve_targets``) with injected paths and fake configs in temp dirs (spec
client-installer §Testability).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from mcp_jira import installer, platform

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


# --- 4.1 unit: load_json / upsert_client / write_with_backup / probe ---------


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


def test_write_with_backup_skips_chmod_on_windows(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(platform, "is_windows", lambda: True)
    p = tmp_path / "new.json"
    installer.write_with_backup(p, {"a": 1})
    assert json.loads(p.read_text()) == {"a": 1}


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


# --- 4.2 unit: _resolve_targets (empty→all, dedupe, order-preserving) -------


def test_resolve_targets_empty_selects_all() -> None:
    assert installer._resolve_targets([], installer._IDS) == list(installer._IDS)


def test_resolve_targets_dedupes_preserving_first_seen_order() -> None:
    assert installer._resolve_targets(
        ["desktop", "desktop", "opencode", "claude"], installer._IDS
    ) == [
        "desktop",
        "opencode",
        "claude",
    ]


def test_resolve_targets_keeps_selected_order_not_ids_order() -> None:
    assert installer._resolve_targets(["desktop", "opencode"], installer._IDS) == [
        "desktop",
        "opencode",
    ]


# --- 4.3 TTY gate: non-TTY guidance ------------------------------------------


def test_non_interactive_prints_guidance_exits_1(tmp_path, capsys) -> None:
    code = installer.run_installer(interactive=False, config_paths=lambda: _fake_paths(tmp_path))
    assert code == 1
    assert "terminal" in capsys.readouterr().out


# --- 4.4 unit: _available_clients --------------------------------------------


def test_available_clients_all_available_when_configs_exist(tmp_path, monkeypatch) -> None:
    paths = _fake_paths(tmp_path)
    for p in paths.values():
        p.write_text("{}")
    monkeypatch.setattr(installer.shutil, "which", lambda name: None)
    assert installer._available_clients(paths) == {
        "opencode": None,
        "claude": None,
        "desktop": None,
    }


def test_available_clients_unavailable_without_config_or_binary(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(installer.shutil, "which", lambda name: None)
    assert installer._available_clients(_fake_paths(tmp_path)) == {
        "opencode": "OpenCode not found (no config or opencode binary on PATH)",
        "claude": "Claude CLI not found (no ~/.claude.json or claude binary on PATH)",
        "desktop": "Claude Desktop not found (no claude_desktop_config.json)",
    }


def test_available_clients_opencode_and_claude_via_binary(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        installer.shutil,
        "which",
        lambda name: f"/usr/bin/{name}" if name in ("opencode", "claude") else None,
    )
    result = installer._available_clients(_fake_paths(tmp_path))
    assert result["opencode"] is None
    assert result["claude"] is None
    assert result["desktop"] is not None


def test_available_clients_desktop_requires_config_not_binary(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(installer.shutil, "which", lambda name: f"/usr/bin/{name}")
    result = installer._available_clients(_fake_paths(tmp_path))
    assert result["opencode"] is None  # binary on PATH is enough
    assert result["claude"] is None
    assert result["desktop"] is not None  # desktop only checks its config file


# --- cross-platform: per-OS client paths --------------------------------------


def test_default_config_paths_linux(monkeypatch) -> None:
    monkeypatch.setattr(platform, "is_windows", lambda: False)
    monkeypatch.setattr(platform, "is_macos", lambda: False)
    home = Path("/home/u")
    monkeypatch.setattr(Path, "home", lambda: home)
    paths = installer.default_config_paths()
    assert paths["opencode"] == home / ".config/opencode/opencode.json"
    assert paths["claude"] == home / ".claude.json"
    assert paths["desktop"] == home / ".config/Claude/claude_desktop_config.json"


def test_default_config_paths_macos(monkeypatch) -> None:
    monkeypatch.setattr(platform, "is_windows", lambda: False)
    monkeypatch.setattr(platform, "is_macos", lambda: True)
    home = Path("/Users/u")
    monkeypatch.setattr(Path, "home", lambda: home)
    paths = installer.default_config_paths()
    assert (
        paths["desktop"] == home / "Library/Application Support/Claude/claude_desktop_config.json"
    )


def test_default_config_paths_windows(monkeypatch) -> None:
    monkeypatch.setattr(platform, "is_windows", lambda: True)
    monkeypatch.setattr(platform, "is_macos", lambda: False)
    home = Path("C:/Users/u")
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.setattr(os, "environ", {"APPDATA": "C:/Users/u/AppData/Roaming"}, raising=False)
    paths = installer.default_config_paths()
    assert paths["desktop"] == Path("C:/Users/u/AppData/Roaming/Claude/claude_desktop_config.json")


# --- cross-platform: frozen binary vs venv registration -----------------------


def test_server_command_venv(monkeypatch) -> None:
    monkeypatch.setattr(platform, "is_frozen", lambda: False)
    assert platform.server_command() == [sys.executable, "-m", "mcp_jira"]


def test_server_command_frozen(monkeypatch) -> None:
    monkeypatch.setattr(platform, "is_frozen", lambda: True)
    assert platform.server_command() == [sys.executable]


def test_targets_derive_command_from_server_cmd() -> None:
    """_TARGETS entries are wired from _SERVER_CMD (frozen-aware at import)."""
    cmd = installer._SERVER_CMD
    opencode = installer._TARGETS[0][3]
    claude = installer._TARGETS[1][3]
    desktop = installer._TARGETS[2][3]
    assert opencode["command"] == cmd
    assert claude == {"command": cmd[0], "args": cmd[1:]}
    assert desktop == {"command": cmd[0], "args": cmd[1:]}
