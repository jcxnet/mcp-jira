"""`mcp-jira setup` wizard: prompt URL + hidden PAT, /myself check, 0600 write.

Interactive flow (server-config §setup wizard): prompt the Jira URL and a
hidden PAT (``getpass``), verify connectivity with ``GET /rest/api/2/myself``,
write ``~/.config/mcp-jira/config.json`` with 0600 permissions, and report the
result. Nothing is written when connectivity fails. Without a TTY the wizard
prints the config path plus guidance and exits non-zero (AC-US-9).
"""

from __future__ import annotations

import getpass
import json
import os
import sys
from collections.abc import Callable
from pathlib import Path

import httpx

from mcp_jira.client import JiraClient
from mcp_jira.config import default_config_path
from mcp_jira.errors import JiraError

_GUIDANCE = (
    "Run `mcp-jira setup` on a terminal to create it, or write it yourself "
    "with keys `jira_url` and `jira_pat` (optional: `language`, `read_only`)."
)


def _is_interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def run_wizard(
    *,
    config_path: Path | None = None,
    interactive: bool | None = None,
    prompt: Callable[[str], str] = input,
    hidden_prompt: Callable[[str], str] = getpass.getpass,
    transport: httpx.BaseTransport | None = None,
) -> int:
    """Run the setup wizard; returns the process exit code (0 = success).

    ``interactive``/``prompt``/``hidden_prompt``/``transport`` are injectable so
    tests run without a TTY and without a live Jira instance; the defaults
    behave per the spec.
    """
    path = config_path or default_config_path()
    if interactive is None:
        interactive = _is_interactive()
    if not interactive:
        print(f"Config path: {path}")
        print(_GUIDANCE)
        return 1
    url = prompt("Jira URL (e.g. https://jira.example.com): ").strip()
    pat = hidden_prompt("Personal Access Token (hidden input): ").strip()
    if not url or not pat:
        print("Both a Jira URL and a PAT are required; nothing was written.", file=sys.stderr)
        return 1
    try:
        JiraClient(url, pat, transport=transport).request("GET", "/rest/api/2/myself")
    except JiraError as exc:
        print(f"Connection failed: {exc}", file=sys.stderr)
        return 1
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump({"jira_url": url, "jira_pat": pat}, fh)
    os.chmod(path, 0o600)  # enforce even if the file pre-existed with looser perms
    print(f"Config written to {path} (mode 600).")
    return 0
