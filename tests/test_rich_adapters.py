"""Unit tests for the Rich prompt adapters (bool→str, escaping, markup safety).

Covers design D4 (Confirm bool → "y"/"n" str contract), D5 (free-text
multi-select without ``choices=``), and D6 (``rich.markup.escape`` on every
interpolated value) for both the wizard and the installer adapters.
"""

from __future__ import annotations

from conftest import BASE_URL

from mcp_jira import installer, wizard

# --- D4: Confirm.ask bool → "y"/"n" str contract ---------------------------


def test_wizard_rich_confirm_maps_true_to_y(monkeypatch) -> None:
    calls: list[tuple[str, bool]] = []

    def fake_ask(prompt: str, default: bool = False) -> bool:
        calls.append((prompt, default))
        return True

    monkeypatch.setattr(wizard.Confirm, "ask", fake_ask)
    assert wizard._rich_confirm("Write config? ", False) == "y"
    assert calls == [("Write config? ", False)]


def test_wizard_rich_confirm_maps_false_to_n_and_forwards_default(monkeypatch) -> None:
    calls: list[tuple[str, bool]] = []

    def fake_ask(prompt: str, default: bool = False) -> bool:
        calls.append((prompt, default))
        return False

    monkeypatch.setattr(wizard.Confirm, "ask", fake_ask)
    assert wizard._rich_confirm("Write config? ", True) == "n"
    assert calls == [("Write config? ", True)]  # default forwarded unchanged


def test_installer_rich_confirm_forces_default_false(monkeypatch) -> None:
    calls: list[tuple[str, bool]] = []

    def fake_ask(prompt: str, default: bool = False) -> bool:
        calls.append((prompt, default))
        return False

    monkeypatch.setattr(installer.Confirm, "ask", fake_ask)
    assert installer._rich_confirm("Write config(s)? ") == "n"
    assert calls == [("Write config(s)? ", False)]  # Enter still = decline


def test_installer_rich_confirm_accepts_true(monkeypatch) -> None:
    monkeypatch.setattr(installer.Confirm, "ask", lambda p, default=False: True)
    assert installer._rich_confirm("Write config(s)? ") == "y"


# --- D6: escape() keeps load-bearing prompts, escapes markup brackets --------


def test_rich_confirm_keeps_write_config_prompt_intact(monkeypatch) -> None:
    calls: list[tuple[str, bool]] = []

    def fake_ask(prompt: str, default: bool = False) -> bool:
        calls.append((prompt, default))
        return True

    monkeypatch.setattr(wizard.Confirm, "ask", fake_ask)
    wizard._rich_confirm("Write config to /tmp/cfg? (y/N, default no): ", False)
    assert calls[0][0] == "Write config to /tmp/cfg? (y/N, default no): "  # bracket-free


def test_rich_prompt_escapes_markup_brackets(monkeypatch) -> None:
    seen: list[str] = []

    def fake_ask(prompt: str, **kwargs) -> str:
        seen.append(prompt)
        return "answer"

    monkeypatch.setattr(wizard.Prompt, "ask", fake_ask)
    assert wizard._rich_prompt("Jira URL [required]: ") == "answer"
    assert seen == ["Jira URL \\[required]: "]


# --- D5: installer multi-select stays free text (no choices=) ----------------


def test_rich_targets_selected_no_choices_free_text(monkeypatch) -> None:
    seen_prompt = ""
    seen_kwargs: dict[str, object] = {}

    def fake_ask(prompt: str, **kwargs) -> str:
        nonlocal seen_prompt, seen_kwargs
        seen_prompt = prompt
        seen_kwargs = kwargs
        return "1,3"

    monkeypatch.setattr(installer.Prompt, "ask", fake_ask)
    assert (
        installer._rich_targets_selected("Select MCP clients: ", ("opencode", "claude"), "")
        == "1,3"
    )
    assert seen_prompt == "Select MCP clients: "  # bracket-free prompt, escape-transparent
    assert seen_kwargs == {"default": ""}
    assert "choices" not in seen_kwargs  # the _select_targets loop stays authoritative


def test_rich_select_uses_choices_and_default(monkeypatch) -> None:
    seen_prompt = ""
    seen_kwargs: dict[str, object] = {}

    def fake_ask(prompt: str, **kwargs) -> str:
        nonlocal seen_prompt, seen_kwargs
        seen_prompt = prompt
        seen_kwargs = kwargs
        return "es"

    monkeypatch.setattr(wizard.Prompt, "ask", fake_ask)
    assert wizard._rich_select("Language (en/es, default en): ", ("en", "es"), "en") == "es"
    assert seen_kwargs == {"choices": ["en", "es"], "default": "en", "show_choices": True}


# --- D6: invalid URL with a bracket keeps the bracket in stderr ---------------


def test_invalid_url_with_bracket_kept_in_stderr(tmp_path, jira_mock, capsys) -> None:
    cfg = tmp_path / "config.json"
    answers = iter(["not a [url", BASE_URL])

    def prompt(_: str) -> str:
        return next(answers)

    code = wizard.run_wizard(
        config_path=cfg,
        interactive=True,
        prompt=prompt,
        hidden_prompt=lambda _: "tok",
        select=lambda *_: "",
        confirm=lambda p, _: "y" if "Write config" in p else "",
        transport=jira_mock.transport,
    )
    assert code == 0  # invalid URL re-prompts, then writes
    err = capsys.readouterr().err
    assert "Invalid URL" in err
    assert "not a [url" in err  # bracket preserved, not eaten as markup
