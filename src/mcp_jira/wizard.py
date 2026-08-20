"""`mcp-jira setup` wizard: TTY gate + 0600 config write.

Without a TTY the wizard prints the config path plus guidance and exits
non-zero (AC-US-9), byte-identical to the previous Rich behavior. On an
interactive terminal it runs :class:`mcp_jira.tui.SetupApp`, which collects
URL/PAT/``language``/``read_only``, verifies connectivity with
``GET /rest/api/2/myself``, confirms the summary, and writes
``~/.config/mcp-jira/config.json`` with 0600 permissions. Nothing is written
unless connectivity succeeds AND the user confirms; ``ctrl+c``/``ctrl+q``
abort with exit 1 and nothing written.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from mcp_jira.config import default_config_path

_GUIDANCE = (
    "Run `mcp-jira setup` on a terminal to create it, or write it yourself "
    "with keys `jira_url` and `jira_pat` (optional: `language`, `read_only`)."
)

_REQUIRED_MSG = "Both a Jira URL and a PAT are required; nothing was written."


def _is_interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _valid_url(url: str) -> bool:
    """True iff ``url`` is an ``http(s)`` URL with a host (design D3)."""
    parts = urlsplit(url)
    return parts.scheme in {"http", "https"} and bool(parts.netloc)


def _write_config(
    path: Path,
    *,
    jira_url: str,
    jira_pat: str,
    language: str,
    read_only: bool,
) -> None:
    """Write the wizard config with 0600 perms: os.open + chmod, 4 keys.

    Shared with ``tui.SetupApp`` (design: extraction from the inline write).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "jira_url": jira_url,
                "jira_pat": jira_pat,
                "language": language,
                "read_only": read_only,
            },
            fh,
        )
    os.chmod(path, 0o600)  # enforce even if the file pre-existed with looser perms


def run_wizard(
    *,
    config_path: Path | None = None,
    interactive: bool | None = None,
    transport: httpx.BaseTransport | None = None,
) -> int:
    """Run the setup wizard; returns the process exit code (0 = success).

    Without a TTY (or with ``interactive=False``) prints the config path plus
    guidance and returns 1, byte-identical to the previous Rich behavior. With
    a TTY the wizard hands off to :class:`mcp_jira.tui.SetupApp` and returns
    its exit code; ``transport`` is injected for tests (design D-WRAP).
    """
    path = config_path or default_config_path()
    if interactive is None:
        interactive = _is_interactive()
    if not interactive:
        print(f"Config path: {path}")
        print(_GUIDANCE)
        return 1
    # Local import: tui.py imports wizard helpers at module level (design ^D-2).
    from mcp_jira.tui import SetupApp

    app = SetupApp(config_path=path, transport=transport)
    result = app.run()
    # run() is typed int | None; SetupApp always exits with a code, so None
    # (no explicit exit) is unreachable and treated as success.
    return 0 if result is None else result
