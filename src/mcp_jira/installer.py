"""`mcp-jira install`: TTY gate + register the server into MCP clients.

Without a TTY the installer prints guidance and exits 1, byte-identical to the
pre-TUI CLI output. On an interactive terminal it runs
:class:`mcp_jira.tui.InstallApp`, which presents a ``SelectionList`` of the
three clients (all selected by default), collects pending configs (skipping
unparseable or already-registered files), confirms before writing, then writes
with a one-time ``.bak`` backup, atomic rename, and post-write JSON validation.
``ctrl+c``/``ctrl+q`` on any screen aborts with exit 1 and nothing written.

Registered command is ``[sys.executable, "-m", "mcp_jira"]`` (venv-absolute,
cwd-independent). Config contents are never printed — only paths.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

_GUIDANCE = (
    "Run `mcp-jira install` on a terminal to register mcp-jira into MCP "
    "clients (OpenCode global, Claude CLI user scope, Claude Desktop)."
)

# (client id, display label, config container key, entry to register)
_TARGETS: tuple[tuple[str, str, str, dict], ...] = (
    (
        "opencode",
        "OpenCode (global)",
        "mcp",
        {"type": "local", "command": [sys.executable, "-m", "mcp_jira"], "enabled": True},
    ),
    (
        "claude",
        "Claude CLI (user scope)",
        "mcpServers",
        {"command": sys.executable, "args": ["-m", "mcp_jira"]},
    ),
    (
        "desktop",
        "Claude Desktop",
        "mcpServers",
        {"command": sys.executable, "args": ["-m", "mcp_jira"]},
    ),
)

_IDS = tuple(target[0] for target in _TARGETS)


def _is_interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def load_json(path: Path) -> dict | None:
    """Return parsed config, ``None`` when missing; raise on corrupt JSON."""
    if not path.exists():
        return None
    return json.loads(path.read_text())


def upsert_client(config: dict, container: str, entry: dict) -> bool:
    """Add ``mcp-jira`` under ``container``; False if already registered."""
    servers = config.get(container)
    if not isinstance(servers, dict):
        servers = {}
        config[container] = servers
    if "mcp-jira" in servers:
        return False
    servers["mcp-jira"] = entry
    return True


def write_with_backup(path: Path, data: dict) -> None:
    """Write ``data`` atomically: one-time ``.bak``, mode preserved, re-parsed.

    Raises loudly if the written file fails JSON re-parse; the previous file
    (from ``.bak``) is restored, or the new file removed, so the client config
    stays untouched.
    """
    bak = path.with_suffix(path.suffix + ".bak")
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    if path.exists() and not bak.exists():
        shutil.copy2(path, bak)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n")
    os.chmod(tmp, mode)
    os.replace(tmp, path)
    try:
        json.loads(path.read_text())
    except (OSError, ValueError):
        if bak.exists():
            os.replace(bak, path)
        else:
            path.unlink(missing_ok=True)
        raise


def probe_desktop_dir(home: Path) -> Path:
    """Return ``~/.config/Claude`` when it exists, else lowercase, else default."""
    for name in ("Claude", "claude"):
        candidate = home / ".config" / name
        if candidate.is_dir():
            return candidate
    return home / ".config" / "Claude"


def default_config_paths() -> dict[str, Path]:
    """Real target paths: OpenCode global, Claude CLI user, Claude Desktop."""
    home = Path.home()
    return {
        "opencode": home / ".config/opencode/opencode.json",
        "claude": home / ".claude.json",
        "desktop": probe_desktop_dir(home) / "claude_desktop_config.json",
    }


def _resolve_targets(selected: Sequence[str], ids: Sequence[str]) -> list[str]:
    """Resolve the selected ids: empty → all, dedupe, first-seen order (D-SEL)."""
    chosen = list(dict.fromkeys(selected))
    return list(ids) if not chosen else chosen


def _collect_pending(
    selected: Sequence[str],
    paths: dict[str, Path],
) -> tuple[list[tuple[str, Path, dict]], list[str]]:
    """Collect client configs pending registration; returns (pending, notices).

    Corrupt JSON and already-registered clients are skipped with a notice and
    left untouched; ``pending`` is written by the caller. Shared with
    ``tui.InstallApp`` (design: extraction from the inline loop).
    """
    pending: list[tuple[str, Path, dict]] = []
    notices: list[str] = []
    for cid, label, container, entry in _TARGETS:
        if cid not in selected:
            continue
        path = paths[cid]
        try:
            config = load_json(path)
        except ValueError:
            notices.append(f"Skipping {label}: {path} is not valid JSON; leaving it untouched.")
            continue
        if config is None:
            config = {}
        if not upsert_client(config, container, entry):
            notices.append(f"{label}: mcp-jira already registered; skipping.")
            continue
        pending.append((label, path, config))
    return pending, notices


def run_installer(
    *,
    interactive: bool | None = None,
    config_paths: Callable[[], dict[str, Path]] | None = None,
) -> int:
    """Run the installer; returns the process exit code (0 = success).

    Without a TTY (or with ``interactive=False``) prints guidance and returns
    1, byte-identical to the pre-TUI CLI output. With a TTY the installer
    hands off to :class:`mcp_jira.tui.InstallApp` and returns its exit code;
    ``config_paths`` is injected for tests (design D-WRAP).
    """
    if interactive is None:
        interactive = _is_interactive()
    if not interactive:
        print(_GUIDANCE)
        return 1
    # Local import: tui.py imports installer helpers at module level.
    from mcp_jira.tui import InstallApp

    app = InstallApp(config_paths=config_paths)
    app.run()
    # run() returns the app's result; the exit code lives in app.return_code
    # (Textual 8 exit(result, return_code)). InstallApp always exits with a
    # code, so None (no explicit exit) is unreachable and treated as success.
    return 0 if app.return_code is None else app.return_code
