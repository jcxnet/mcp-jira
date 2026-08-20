"""Pilot-driven behavioral tests for ``InstallApp`` (design: Testing Strategy, Pilot).

Each test runs the app headless (``run_test(headless=True, size=(80, 24))``)
with injected per-target config paths in a temp dir, then drives the widgets
like a user — design D-TEST/D-WRAP. The scenarios mirror the client-installer
delta spec: §install subcommand (interactive install, default selection is
all, ctrl+c aborts cleanly) and §Testability (Pilot drives the interactive
flow). Write-safety semantics (mode preservation, one-time ``.bak``, merge
not clobber, post-write re-parse) are pinned here at the app level and in
``test_installer.py`` at the pure-function level.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from textual.widgets import SelectionList, Static

from mcp_jira.installer import _IDS
from mcp_jira.tui import ConfirmModal, InstallApp

_OPENCODE_ENTRY = {
    "type": "local",
    "command": [sys.executable, "-m", "mcp_jira"],
    "enabled": True,
}
_CLAUDE_ENTRY = {"command": sys.executable, "args": ["-m", "mcp_jira"]}


def _paths(tmp_path: Path) -> dict[str, Path]:
    return {
        "opencode": tmp_path / "opencode.json",
        "claude": tmp_path / "claude.json",
        "desktop": tmp_path / "claude_desktop_config.json",
    }


def _notices(app: InstallApp) -> str:
    # The selection screen stays mounted under the pushed ConfirmModal, so the
    # inline notices are still queryable on the app after Continue.
    return str(app.query_one("#notices", Static).content)


async def test_success_merges_all_three_targets_with_modes_and_backups(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    paths["opencode"].write_text('{"existing": true}', encoding="utf-8")
    paths["claude"].write_text('{"keep": true}', encoding="utf-8")
    paths["desktop"].write_text('{"x": 1}', encoding="utf-8")
    os.chmod(paths["opencode"], 0o644)
    os.chmod(paths["claude"], 0o600)
    os.chmod(paths["desktop"], 0o600)
    app = InstallApp(config_paths=lambda: paths)
    async with app.run_test(headless=True, size=(80, 24)) as pilot:
        await pilot.click("#continue")
        assert isinstance(app.screen, ConfirmModal)
        await pilot.click("#write")

        opencode = json.loads(paths["opencode"].read_text(encoding="utf-8"))
        assert opencode == {"existing": True, "mcp": {"mcp-jira": _OPENCODE_ENTRY}}
        assert (paths["opencode"].stat().st_mode & 0o777) == 0o644
        assert json.loads(paths["opencode"].with_suffix(".json.bak").read_text()) == {
            "existing": True
        }

        claude = json.loads(paths["claude"].read_text(encoding="utf-8"))
        assert claude == {"keep": True, "mcpServers": {"mcp-jira": _CLAUDE_ENTRY}}
        assert (paths["claude"].stat().st_mode & 0o777) == 0o600
        assert json.loads(paths["claude"].with_suffix(".json.bak").read_text()) == {"keep": True}

        desktop = json.loads(paths["desktop"].read_text(encoding="utf-8"))
        assert desktop == {"x": 1, "mcpServers": {"mcp-jira": _CLAUDE_ENTRY}}
        assert (paths["desktop"].stat().st_mode & 0o777) == 0o600
        assert json.loads(paths["desktop"].with_suffix(".json.bak").read_text()) == {"x": 1}

        await pilot.click("#ok")
    assert app.return_code == 0


async def test_default_selection_is_all_three_clients(tmp_path: Path) -> None:
    """Scenario 'Default selection is all clients': continue without changing."""
    paths = _paths(tmp_path)
    app = InstallApp(config_paths=lambda: paths)
    async with app.run_test(headless=True, size=(80, 24)) as pilot:
        assert app.query_one("#targets", SelectionList).selected == list(_IDS)
        await pilot.click("#continue")
        assert isinstance(app.screen, ConfirmModal)
        await pilot.click("#write")
        await pilot.click("#ok")
    assert app.return_code == 0
    for path in paths.values():
        assert path.exists()


async def test_subset_writes_only_selected_targets(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    app = InstallApp(config_paths=lambda: paths)
    async with app.run_test(headless=True, size=(80, 24)) as pilot:
        app.query_one("#targets", SelectionList).deselect("opencode")
        await pilot.click("#continue")
        assert isinstance(app.screen, ConfirmModal)
        summary = str(app.screen.query_one(Static).content)
        assert "opencode.json" not in summary
        assert "claude.json" in summary
        assert "claude_desktop_config.json" in summary
        await pilot.click("#write")
        await pilot.click("#ok")
    assert app.return_code == 0
    assert not paths["opencode"].exists()
    assert paths["claude"].exists()
    assert paths["desktop"].exists()


async def test_already_registered_shows_notice_and_preserves_client(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    original = '{"mcp": {"mcp-jira": {"type": "local", "command": ["old"]}}}'
    paths["opencode"].write_text(original, encoding="utf-8")
    app = InstallApp(config_paths=lambda: paths)
    async with app.run_test(headless=True, size=(80, 24)) as pilot:
        await pilot.click("#continue")
        assert "already registered" in _notices(app)
        assert "OpenCode" in _notices(app)
        await pilot.click("#write")
        await pilot.click("#ok")
    assert app.return_code == 0
    assert paths["opencode"].read_text(encoding="utf-8") == original  # untouched
    assert not paths["opencode"].with_suffix(".json.bak").exists()  # never rewritten
    assert paths["claude"].exists()
    assert paths["desktop"].exists()


async def test_corrupt_config_notice_skips_and_leaves_file_untouched(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    corrupt = "{not json"
    paths["opencode"].write_text(corrupt, encoding="utf-8")
    app = InstallApp(config_paths=lambda: paths)
    async with app.run_test(headless=True, size=(80, 24)) as pilot:
        await pilot.click("#continue")
        assert "not valid JSON" in _notices(app)
        assert "OpenCode (global)" in _notices(app)
        await pilot.click("#write")
        await pilot.click("#ok")
    assert app.return_code == 0
    assert paths["opencode"].read_text(encoding="utf-8") == corrupt  # untouched
    assert not paths["opencode"].with_suffix(".json.bak").exists()
    assert paths["claude"].exists()
    assert paths["desktop"].exists()


async def test_confirm_declined_writes_nothing_and_exits_1(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    app = InstallApp(config_paths=lambda: paths)
    async with app.run_test(headless=True, size=(80, 24)) as pilot:
        await pilot.click("#continue")
        assert isinstance(app.screen, ConfirmModal)
        await pilot.click("#cancel")
    assert app.return_code == 1
    assert not any(path.exists() for path in paths.values())


async def test_ctrl_c_on_selection_screen_writes_nothing_and_exits_1(tmp_path: Path) -> None:
    """Scenario 'Ctrl-C aborts cleanly': abort on the SelectionList screen."""
    paths = _paths(tmp_path)
    app = InstallApp(config_paths=lambda: paths)
    async with app.run_test(headless=True, size=(80, 24)) as pilot:
        await pilot.press("ctrl+c")
    assert app.return_code == 1
    assert not any(path.exists() for path in paths.values())
