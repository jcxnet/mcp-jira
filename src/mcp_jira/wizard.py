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

import json
import os
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from mcp_jira.client import JiraClient
from mcp_jira.config import SUPPORTED_LANGUAGES, default_config_path
from mcp_jira.errors import JiraError
from mcp_jira.ui import console, error_console

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


def _rich_prompt(p: str) -> str:
    """Rich ``Prompt.ask`` for a plain text answer (design D3/D4)."""
    return Prompt.ask(escape(p))


def _rich_hidden(p: str) -> str:
    """Rich ``Prompt.ask`` with hidden input (``getpass`` equivalent)."""
    return Prompt.ask(escape(p), password=True)


def _rich_select(p: str, options: Sequence[str], default: str) -> str:
    """Rich ``Prompt.ask`` with validated choices; returns the chosen option."""
    return Prompt.ask(escape(p), choices=list(options), default=default, show_choices=True)


def _rich_confirm(p: str, default: bool) -> str:
    """Rich ``Confirm.ask`` adapted to the ``"y"``/``"n"`` str contract (D4)."""
    return "y" if Confirm.ask(escape(p), default=default) else "n"


def run_wizard(
    *,
    config_path: Path | None = None,
    interactive: bool | None = None,
    prompt: Callable[[str], str] = _rich_prompt,
    hidden_prompt: Callable[[str], str] = _rich_hidden,
    select: Callable[[str, Sequence[str], str], str] = _rich_select,
    confirm: Callable[[str, bool], str] = _rich_confirm,
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
            error_console.print(_REQUIRED_MSG, style="bold red")
            return 1
        while not _valid_url(url):
            if not url:
                error_console.print(_REQUIRED_MSG, style="bold red")
                return 1
            error_console.print(
                f"Invalid URL: {escape(repr(url))} must start with http:// or https://.",
                style="bold red",
            )
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
            error_console.print(
                f"Invalid language: {escape(repr(lang))}; choose {', '.join(SUPPORTED_LANGUAGES)}.",
                style="bold red",
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
            error_console.print(
                f"Invalid answer: {escape(repr(answer))}; answer y or n.", style="bold red"
            )
        try:
            with console.status("Checking Jira connectivity..."):
                JiraClient(url, pat, transport=transport).request("GET", "/rest/api/2/myself")
        except JiraError as exc:
            error_console.print(f"Connection failed: {escape(str(exc))}", style="bold red")
            return 1
        console.print(
            Panel(
                f"URL {escape(url)} | language {lang} | read_only {read_only}",
                title="Summary",
                title_align="left",
            )
        )
        answer = confirm(f"Write config to {path}? (y/N, default no): ", False).strip().lower()
        if answer not in ("y", "yes"):
            error_console.print("Aborted; nothing was written.", style="bold red")
            return 1
    except KeyboardInterrupt:
        error_console.print("Aborted.", style="bold red")
        return 1
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(
            {"jira_url": url, "jira_pat": pat, "language": lang, "read_only": read_only},
            fh,
        )
    os.chmod(path, 0o600)  # enforce even if the file pre-existed with looser perms
    console.print(f"Config written to {escape(str(path))} (mode 600).", style="bold green")
    return 0
