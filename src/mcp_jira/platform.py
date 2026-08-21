"""Per-OS path resolution (stdlib only): config dirs and client config paths.

Windows uses ``%APPDATA%``, macOS uses ``~/Library/Application Support``, and
Linux uses ``$XDG_CONFIG_HOME`` (default ``~/.config``). ``is_frozen`` detects
a PyInstaller binary so the installer registers the bare executable instead of
a ``python -m`` invocation.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def is_windows() -> bool:
    return os.name == "nt"


def is_macos() -> bool:
    return sys.platform == "darwin"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def config_dir() -> Path:
    """Return the mcp-jira config directory for the current OS."""
    if is_windows():
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / "mcp-jira"
    if is_macos():
        return Path.home() / "Library" / "Application Support" / "mcp-jira"
    base = Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config"))
    return base / "mcp-jira"


def claude_desktop_config_path(home: Path) -> Path:
    """Return Claude Desktop's config path for the current OS.

    Linux probes ``~/.config/Claude`` then ``~/.config/claude`` (case
    variants), falling back to capitalized; macOS and Windows use the
    platform-native Application Support / APPDATA locations.
    """
    if is_windows():
        base = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
        return base / "Claude" / "claude_desktop_config.json"
    if is_macos():
        return home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    for name in ("Claude", "claude"):
        candidate = home / ".config" / name
        if candidate.is_dir():
            return candidate / "claude_desktop_config.json"
    return home / ".config" / "Claude" / "claude_desktop_config.json"


def server_command() -> list[str]:
    """Return the command that launches the MCP server on this host.

    Frozen (PyInstaller one-file) builds run the executable directly; the
    venv/source layout runs ``python -m mcp_jira``.
    """
    if is_frozen():
        return [sys.executable]
    return [sys.executable, "-m", "mcp_jira"]
