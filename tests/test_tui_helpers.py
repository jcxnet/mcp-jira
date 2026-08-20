"""Unit tests for the pure TUI helpers (design: Testing Strategy, helpers only).

The widget apps themselves are exercised by the pilot/interaction tests in a
later change; these cover the shared pure logic — the 0600 config write, the
target resolution, and the pending collection — that the apps rely on.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcp_jira.installer import _IDS, _collect_pending, _resolve_targets
from mcp_jira.wizard import _write_config


def test_write_config_writes_0600_with_four_keys(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    _write_config(
        path,
        jira_url="https://jira.example.test",
        jira_pat="secret",
        language="en",
        read_only=True,
    )
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data == {
        "jira_url": "https://jira.example.test",
        "jira_pat": "secret",
        "language": "en",
        "read_only": True,
    }
    assert path.stat().st_mode & 0o777 == 0o600


def test_write_config_creates_parent_dirs(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "config.json"
    _write_config(
        path,
        jira_url="https://jira.example.test",
        jira_pat="secret",
        language="en",
        read_only=False,
    )
    assert path.is_file()


def test_resolve_targets_empty_means_all() -> None:
    assert _resolve_targets([], _IDS) == list(_IDS)


def test_resolve_targets_dedupes_and_preserves_order() -> None:
    assert _resolve_targets(["desktop", "opencode", "desktop", "claude"], _IDS) == [
        "desktop",
        "opencode",
        "claude",
    ]


def test_collect_pending_skips_corrupt_and_untouched(tmp_path: Path) -> None:
    corrupt = tmp_path / "opencode.json"
    corrupt.write_text("not json", encoding="utf-8")
    pending, notices = _collect_pending(["opencode"], {"opencode": corrupt})
    assert pending == []
    assert len(notices) == 1
    assert "not valid JSON" in notices[0]
    assert "leaving it untouched" in notices[0]
    assert corrupt.read_text(encoding="utf-8") == "not json"


def test_collect_pending_skips_already_registered(tmp_path: Path) -> None:
    config = tmp_path / "claude.json"
    config.write_text(json.dumps({"mcpServers": {"mcp-jira": {}}}), encoding="utf-8")
    pending, notices = _collect_pending(["claude"], {"claude": config})
    assert pending == []
    assert len(notices) == 1
    assert "already registered" in notices[0]


def test_collect_pending_returns_pending_targets(tmp_path: Path) -> None:
    config = tmp_path / "opencode.json"
    config.write_text(json.dumps({"mcp": {"servers": {}}}), encoding="utf-8")
    pending, notices = _collect_pending(["opencode"], {"opencode": config})
    assert notices == []
    assert len(pending) == 1
    label, path, data = pending[0]
    assert label == "OpenCode (global)"
    assert path == config
    assert data["mcp"]["mcp-jira"] is not None


def test_collect_pending_missing_file_creates_config(tmp_path: Path) -> None:
    missing = tmp_path / "claude.json"
    pending, notices = _collect_pending(["claude"], {"claude": missing})
    assert notices == []
    assert len(pending) == 1
    _, path, data = pending[0]
    assert path == missing
    assert data["mcpServers"]["mcp-jira"] is not None
