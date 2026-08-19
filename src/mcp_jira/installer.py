"""`mcp-jira install`: register the server into MCP clients (OpenCode/Claude).

Interactive flow mirroring ``wizard.py``'s form-loop + injectable pattern:
select clients (multi-select, default all), load+upsert each config (skipping
unparseable or already-registered files), confirm before writing, then write
with a one-time ``.bak`` backup, atomic rename, and post-write JSON validation.
``^C`` at any prompt aborts with exit 1 and nothing written. Without a TTY the
installer prints guidance and exits non-zero.

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

from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from mcp_jira.ui import console, error_console

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


def _select_targets(
    prompt: Callable[[str, Sequence[str], str], str],
    options: Sequence[str],
) -> list[str]:
    """Form-style multi-select; empty answer selects all, else comma numbers."""
    while True:
        answer = prompt(_selection_prompt(), options, "").strip()
        if not answer:
            return list(options)
        chosen: list[str] = []
        for part in answer.split(","):
            part = part.strip()
            if part.isdigit() and 1 <= int(part) <= len(options):
                chosen.append(options[int(part) - 1])
            else:
                chosen = []
                break
        if chosen:
            return list(dict.fromkeys(chosen))
        error_console.print(
            f"Invalid selection: {escape(repr(answer))}; enter numbers separated by commas "
            "(or nothing for all).",
            style="bold red",
        )


def _selection_prompt() -> str:
    lines = ["Select MCP clients to register (comma-separated numbers, default all):"]
    lines += [f"  {i}) {label}" for i, (_, label, _, _) in enumerate(_TARGETS, start=1)]
    return "\n".join(lines) + "\nSelection: "


def _rich_targets_selected(p: str, options: Sequence[str], default: str) -> str:
    """Rich free-text ``Prompt.ask``; no ``choices=`` so comma lists parse (D5).

    The ``_select_targets`` loop stays the authoritative parser (empty→all,
    dedupe, invalid→re-prompt); this adapter only styles the prompt.
    """
    return Prompt.ask(escape(p), default=default)


def _rich_confirm(p: str) -> str:
    """Rich ``Confirm.ask`` (default no) adapted to the ``"y"``/``"n"`` str contract."""
    return "y" if Confirm.ask(escape(p), default=False) else "n"


def run_installer(
    *,
    interactive: bool | None = None,
    config_paths: Callable[[], dict[str, Path]] | None = None,
    targets_selected: Callable[[str, Sequence[str], str], str] | None = None,
    confirm: Callable[[str], str] = _rich_confirm,
) -> int:
    """Run the installer; returns the process exit code (0 = success)."""
    if interactive is None:
        interactive = _is_interactive()
    if not interactive:
        print(_GUIDANCE)
        return 1
    try:
        selected = _select_targets(targets_selected or _rich_targets_selected, _IDS)
        paths = (config_paths or default_config_paths)()
        pending: list[tuple[str, Path, dict]] = []
        for cid, label, container, entry in _TARGETS:
            if cid not in selected:
                continue
            path = paths[cid]
            try:
                config = load_json(path)
            except ValueError:
                error_console.print(
                    f"Skipping {escape(label)}: {escape(str(path))} is not valid JSON; "
                    "leaving it untouched.",
                    style="bold red",
                )
                continue
            if config is None:
                config = {}
            if not upsert_client(config, container, entry):
                console.print(f"{escape(label)}: mcp-jira already registered; skipping.")
                continue
            pending.append((label, path, config))
        if not pending:
            console.print("Nothing to register.")
            return 0
        console.print(
            Panel(
                "\n".join(
                    f"  - {escape(label)} ({escape(str(path))})" for label, path, _ in pending
                ),
                title=f"Summary: {len(pending)} config(s) will be modified",
                title_align="left",
            )
        )
        answer = confirm("Write config(s)? (y/N, default no): ").strip().lower()
        if answer not in ("y", "yes"):
            error_console.print("Aborted; nothing was written.", style="bold red")
            return 1
        for _, path, config in pending:
            try:
                write_with_backup(path, config)
            except (OSError, ValueError) as exc:
                error_console.print(
                    f"Failed to write {escape(str(path))}: {escape(str(exc))}; "
                    "original config left untouched.",
                    style="bold red",
                )
                return 1
            console.print(f"Registered mcp-jira in {escape(str(path))}", style="bold green")
    except KeyboardInterrupt:
        error_console.print("Aborted.", style="bold red")
        return 1
    return 0
