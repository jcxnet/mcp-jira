"""Unit tests for the installer's Rich prompt adapters (bool→str, free-text select).

The wizard-side adapter tests were removed with the wizard's ``_rich_*``
functions (task 3.1); this file keeps the installer adapters until task 3.3
deletes them along with the Rich prompt layer. Covers installer D4 (Confirm
bool → "y"/"n" str contract, default always False) and D5 (free-text
multi-select without ``choices=``).
"""

from __future__ import annotations

from mcp_jira import installer

# --- D4: Confirm.ask bool → "y"/"n" str contract ---------------------------


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
