"""Textual widget apps for `mcp-jira setup` and `mcp-jira install` (design ^D-2).

``SetupApp`` and ``InstallApp`` replace the legacy prompt shells with widget
forms. The write/merge/security logic stays in ``wizard``/``installer`` and is
reached through the extracted pure helpers (``_write_config``,
``_collect_pending``, ``_resolve_targets``). Nothing is written unless the user
confirms; ``ctrl+c``/``ctrl+q`` on any app or screen aborts with exit code 1.

This module is unwired from the CLI in its first PR; the wrappers that
construct and run the apps land with the CLI wiring.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

import httpx
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.dom import DOMNode
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button,
    Input,
    Label,
    LoadingIndicator,
    Select,
    SelectionList,
    Static,
    Switch,
)
from textual.widgets._selection_list import Selection
from textual.worker import get_current_worker

from mcp_jira.client import JiraClient
from mcp_jira.config import SUPPORTED_LANGUAGES
from mcp_jira.errors import JiraError
from mcp_jira.installer import (
    _IDS,
    _TARGETS,
    _available_clients,
    _collect_pending,
    _resolve_targets,
    default_config_paths,
    write_with_backup,
)
from mcp_jira.wizard import _REQUIRED_MSG, _valid_url, _write_config

if TYPE_CHECKING:
    from typing import Protocol

    class _Abortable(Protocol):
        """Minimal surface the abort mixin needs (App and every Screen have it)."""

        @property
        def app(self) -> App[object]: ...


def _availability_notices(availability: dict[str, str | None]) -> str:
    """One line per unavailable client: ``'{label}: {reason} — skipped.'``."""
    return "\n".join(
        f"{label}: {availability[cid]} — skipped."
        for cid, label, _, _ in _TARGETS
        if availability[cid] is not None
    )


class _AbortMixin(DOMNode):
    """Priority ``ctrl+c``/``ctrl+q`` abort shared by apps and screens (^D-^C).

    Subclassing ``DOMNode`` (not a plain mixin) is required: Textual merges
    ``BINDINGS`` only from ``DOMNode`` subclasses in the MRO
    (``DOMNode._merge_bindings``), so a plain mixin's bindings would be
    silently dropped and Textual's default ``ctrl+q -> quit`` would win.
    Textual 8.2 ``Screen`` has no ``exit()`` and apps no longer quit on
    ``ctrl+c``; ``app`` resolves on both ``App`` and ``Screen``, so
    ``self.app.exit(return_code=1)`` aborts the whole app with exit code 1
    from any screen. ``priority=True`` wins over focused-widget bindings
    (e.g. Input's copy); ``show=False`` hides both bindings from the footer.
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("ctrl+c", "abort", show=False, priority=True),
        Binding("ctrl+q", "abort", show=False, priority=True),
    ]

    def action_abort(self: _Abortable) -> None:
        # Textual 8: exit() is exit(result, return_code); the code must be
        # keyword-passed or it lands in `result` and return_code stays 0.
        self.app.exit(return_code=1)


class ConfirmModal(_AbortMixin, ModalScreen[bool]):
    """Shared confirm dialog; shows only the passed summary (never PAT/contents)."""

    CSS = """
    ModalScreen { align: center middle; }
    #dialog { width: 68; padding: 1 2; background: $surface; border: round $primary; }
    """

    def __init__(self, summary: list[str]) -> None:
        super().__init__()
        self._summary = summary

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Static("\n".join(self._summary), markup=False)
            yield Button("Write", id="write", variant="primary")
            yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "write")


class ResultScreen(_AbortMixin, Screen[None]):
    """Final result; OK exits the app with the given code (0 success, else 1)."""

    CSS = """
    Screen { align: center middle; }
    #dialog { width: 68; padding: 1 2; }
    """

    def __init__(self, code: int, message: str) -> None:
        super().__init__()
        self._code = code
        self._message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Static(self._message, markup=False)
            yield Button("OK", id="ok", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ok":
            self.app.exit(return_code=self._code)


class SetupApp(_AbortMixin, App[int]):
    """Setup wizard: form -> /myself worker -> confirm -> 0600 write -> result."""

    TITLE = "mcp-jira setup"

    CSS = """
    Screen { align: center middle; }
    #form { width: 72; padding: 1 2; }
    #connectivity_error { color: #e74c3c; margin: 1 0; }
    #loading { display: none; margin: 1 0; }
    """

    def __init__(
        self,
        *,
        config_path: Path,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        super().__init__()
        self._config_path = config_path
        self._transport = transport
        self._values: tuple[str, str] = ("", "")

    def compose(self) -> ComposeResult:
        with Vertical(id="form"):
            yield Label("Jira URL")
            yield Input(placeholder="https://jira.example.com", id="url")
            yield Label("Personal Access Token")
            yield Input(placeholder="Personal Access Token", password=True, id="pat")
            yield Label("Language")
            yield Select([(lang, lang) for lang in SUPPORTED_LANGUAGES], value="en", id="language")
            yield Label("Read-only mode")
            yield Switch(id="read_only")
            yield Static("", id="connectivity_error", markup=False)
            yield LoadingIndicator(id="loading")
            yield Button("Continue", id="continue", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "continue":
            self._submit()

    def _set_error(self, message: str) -> None:
        self.query_one("#connectivity_error", Static).update(message)

    def _submit(self) -> None:
        url = self.query_one("#url", Input).value.strip()
        pat = self.query_one("#pat", Input).value.strip()
        if not url or not pat:
            self._set_error(_REQUIRED_MSG)
            return
        if not _valid_url(url):
            self._set_error(f"Invalid URL: {url!r} must start with http:// or https://.")
            return
        self._values = (url, pat)
        self._set_error("")
        self.query_one("#loading", LoadingIndicator).display = True
        self.check_connectivity(url, pat)

    @work(thread=True)
    def check_connectivity(self, url: str, pat: str) -> None:
        worker = get_current_worker()
        try:
            JiraClient(url, pat, transport=self._transport).request("GET", "/rest/api/2/myself")
        except JiraError as exc:
            if worker.is_cancelled:
                return
            self.call_from_thread(self._connectivity_failed, str(exc))
            return
        if worker.is_cancelled:
            return
        self.call_from_thread(self._connectivity_ok)

    def _connectivity_failed(self, message: str) -> None:
        self.query_one("#loading", LoadingIndicator).display = False
        self._set_error(f"Connection failed: {message}")

    def _connectivity_ok(self) -> None:
        self.query_one("#loading", LoadingIndicator).display = False
        url, _ = self._values
        language = str(self.query_one("#language", Select).value)
        read_only = bool(self.query_one("#read_only", Switch).value)
        self.push_screen(
            ConfirmModal(
                [
                    f"URL: {url}",
                    f"Language: {language}",
                    f"Read-only: {read_only}",
                    f"Config path: {self._config_path}",
                ]
            ),
            self._on_confirm,
        )

    def _on_confirm(self, result: object) -> None:
        if result is not True:
            self.exit(return_code=1)
            return
        url, pat = self._values
        language = str(self.query_one("#language", Select).value)
        read_only = bool(self.query_one("#read_only", Switch).value)
        try:
            _write_config(
                self._config_path,
                jira_url=url,
                jira_pat=pat,
                language=language,
                read_only=read_only,
            )
        except OSError as exc:
            self.push_screen(ResultScreen(1, f"Failed to write config: {exc}"))
            return
        self.push_screen(ResultScreen(0, f"Config written to {self._config_path} (mode 600)."))


class InstallApp(_AbortMixin, App[int]):
    """Install flow: SelectionList -> collect pending -> confirm -> per-path write."""

    TITLE = "mcp-jira install"

    CSS = """
    Screen { align: center middle; }
    #form { width: 72; padding: 1 2; }
    #notices { margin: 1 0; }
    """

    def __init__(
        self,
        *,
        config_paths: Callable[[], dict[str, Path]] | None = None,
    ) -> None:
        super().__init__()
        self._config_paths = config_paths or default_config_paths
        self._pending: list[tuple[str, Path, dict]] = []

    def compose(self) -> ComposeResult:
        availability = _available_clients(self._config_paths())
        options = [
            Selection(
                label,
                cid,
                initial_state=availability[cid] is None,
                disabled=availability[cid] is not None,
                id=cid,
            )
            for cid, label, _, _ in _TARGETS
        ]
        with Vertical(id="form"):
            yield Label("Select MCP clients to register (default: all)")
            yield SelectionList(*options, id="targets")
            yield Static(_availability_notices(availability), id="notices", markup=False)
            yield Button("Continue", id="continue", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "continue":
            self._continue()

    def _continue(self) -> None:
        paths = self._config_paths()
        selected = self.query_one("#targets", SelectionList).selected
        ids = _resolve_targets(selected, _IDS)
        pending, notices = _collect_pending(ids, paths)
        availability = _availability_notices(_available_clients(paths))
        if availability:
            notices = [availability] + notices
        self.query_one("#notices", Static).update("\n".join(notices))
        if not pending:
            self.push_screen(ResultScreen(0, "Nothing to register."))
            return
        self._pending = pending
        self.push_screen(
            ConfirmModal([str(path) for _, path, _ in pending]),
            self._on_confirm,
        )

    def _on_confirm(self, result: object) -> None:
        if result is not True:
            self.exit(return_code=1)
            return
        messages: list[str] = []
        for _, path, config in self._pending:
            try:
                write_with_backup(path, config)
            except (OSError, ValueError) as exc:
                self.push_screen(
                    ResultScreen(
                        1, f"Failed to write {path}: {exc}; original config left untouched."
                    )
                )
                return
            messages.append(f"Registered mcp-jira in {path}")
        self.push_screen(ResultScreen(0, "\n".join(messages)))
