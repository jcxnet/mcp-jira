"""`mcp-jira setup` wizard: prompts, /myself check, confirmation, 0600 write.

Interactive flow (server-config §setup wizard): prompt the Jira URL and a
hidden PAT (``getpass``), the optional ``language``/``read_only`` fields, verify
connectivity with ``GET /rest/api/2/myself``, confirm the collected values,
write ``~/.config/mcp-jira/config.json`` with 0600 permissions, and report the
result. Nothing is written unless connectivity succeeds AND the user confirms;
``^C`` at any prompt aborts cleanly with nothing written. Without a TTY the
wizard prints the config path plus guidance and exits non-zero (AC-US-9).
"""

from __future__ import annotations

import getpass
import json
import os
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from mcp_jira.client import JiraClient
from mcp_jira.config import SUPPORTED_LANGUAGES, default_config_path
from mcp_jira.errors import JiraError

_GUIDANCE = (
    "Run `mcp-jira setup` on a terminal to create it, or write it yourself "
    "with keys `jira_url` and `jira_pat` (optional: `language`, `read_only`)."
)

_REQUIRED_MSG = "Both a Jira URL and a PAT are required; nothing was written."

_URL_PROMPT = "Jira URL (e.g. https://jira.example.com): "


def _is_interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _valid_url(url: str) -> bool:
    """True iff ``url`` is an ``http(s)`` URL with a host (design D3)."""
    parts = urlsplit(url)
    return parts.scheme in {"http", "https"} and bool(parts.netloc)


def run_wizard(
    *,
    config_path: Path | None = None,
    interactive: bool | None = None,
    prompt: Callable[[str], str] = input,
    hidden_prompt: Callable[[str], str] = getpass.getpass,
    select: Callable[[str, Sequence[str], str], str] = lambda p, o, d: input(p),
    confirm: Callable[[str, bool], str] = lambda p, d: input(p),
    transport: httpx.BaseTransport | None = None,
) -> int:
    """Run the setup wizard; returns the process exit code (0 = success).

    ``interactive``/``prompt``/``hidden_prompt``/``select``/``confirm``/
    ``transport`` are injectable so tests run without a TTY and without a live
    Jira instance; the defaults behave per the spec.
    """
    path = config_path or default_config_path()
    if interactive is None:
        interactive = _is_interactive()
    if not interactive:
        print(f"Config path: {path}")
        print(_GUIDANCE)
        return 1
    try:
        url = prompt(_URL_PROMPT).strip()
        pat = hidden_prompt("Personal Access Token (hidden input): ").strip()
        if not url or not pat:
            print(_REQUIRED_MSG, file=sys.stderr)
            return 1
        while not _valid_url(url):
            if not url:
                print(_REQUIRED_MSG, file=sys.stderr)
                return 1
            print(f"Invalid URL: {url!r} must start with http:// or https://.", file=sys.stderr)
            url = prompt(_URL_PROMPT).strip()
        lang_prompt = (
            f"Language ({'/'.join(SUPPORTED_LANGUAGES)}, default {SUPPORTED_LANGUAGES[0]}): "
        )
        while True:
            lang = select(lang_prompt, SUPPORTED_LANGUAGES, SUPPORTED_LANGUAGES[0]).strip().lower()
            if not lang:
                lang = SUPPORTED_LANGUAGES[0]
            if lang in SUPPORTED_LANGUAGES:
                break
            print(
                f"Invalid language: {lang!r}; choose {', '.join(SUPPORTED_LANGUAGES)}.",
                file=sys.stderr,
            )
        while True:
            answer = confirm("Read-only mode? (y/N, default no): ", False).strip().lower()
            if not answer:
                read_only = False
                break
            if answer in ("y", "yes"):
                read_only = True
                break
            if answer in ("n", "no"):
                read_only = False
                break
            print(f"Invalid answer: {answer!r}; answer y or n.", file=sys.stderr)
        try:
            JiraClient(url, pat, transport=transport).request("GET", "/rest/api/2/myself")
        except JiraError as exc:
            print(f"Connection failed: {exc}", file=sys.stderr)
            return 1
        print(f"Summary: URL {url} | language {lang} | read_only {read_only}.")
        answer = confirm(f"Write config to {path}? (y/N, default no): ", False).strip().lower()
        if answer not in ("y", "yes"):
            print("Aborted; nothing was written.", file=sys.stderr)
            return 1
    except KeyboardInterrupt:
        print("Aborted.", file=sys.stderr)
        return 1
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(
            {"jira_url": url, "jira_pat": pat, "language": lang, "read_only": read_only},
            fh,
        )
    os.chmod(path, 0o600)  # enforce even if the file pre-existed with looser perms
    print(f"Config written to {path} (mode 600).")
    return 0
