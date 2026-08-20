"""Pilot-driven behavioral tests for ``SetupApp`` (design: Testing Strategy, Pilot).

Each test runs the app headless (``run_test(headless=True, size=(80, 24))``)
with an injected ``httpx.MockTransport`` and a temp config path, then drives
the widgets like a user — design D-TEST/D-WRAP. The scenarios mirror the
server-config delta spec: Setup wizard (success, optional defaults, invalid
URL, confirmation declined, ctrl+c), connectivity-worker (401 stays on form),
and tui-abort-binding (ctrl+c/ctrl+q on any screen).
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
from textual.widgets import Input, Select, Static, Switch

from mcp_jira.tui import ConfirmModal, SetupApp

_SUCCESS_URL = "https://jira.example.test"
_SUCCESS_PAT = "secret-pat"
_REQUIRED_MSG = "Both a Jira URL and a PAT are required; nothing was written."


def _transport(status: int = 200) -> tuple[list[str], httpx.MockTransport]:
    """Return a (call log, transport) pair; the handler records request paths."""

    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if status == 200:
            return httpx.Response(200, json={"name": "me"})
        return httpx.Response(status, json={"errorMessages": ["nope"]})

    return calls, httpx.MockTransport(handler)


def _fill(app: SetupApp, *, url: str = _SUCCESS_URL, pat: str = _SUCCESS_PAT) -> None:
    app.query_one("#url", Input).value = url
    app.query_one("#pat", Input).value = pat


async def _submit_and_wait(pilot, app: SetupApp) -> None:
    """Click Continue and deterministically wait out the threaded /myself worker."""
    await pilot.click("#continue")
    await app.workers.wait_for_complete()
    await pilot.pause()


async def _run_to_confirm(pilot, app: SetupApp) -> None:
    """Fill the form, submit, and wait until the ConfirmModal is on screen."""
    _fill(app)
    await _submit_and_wait(pilot, app)
    assert isinstance(app.screen, ConfirmModal)


def _error_text(app: SetupApp) -> str:
    return str(app.query_one("#connectivity_error", Static).content)


async def test_success_writes_0600_with_four_keys_and_exits_zero(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    calls, transport = _transport(200)
    app = SetupApp(config_path=config_path, transport=transport)
    async with app.run_test(headless=True, size=(80, 24)) as pilot:
        await _run_to_confirm(pilot, app)
        await pilot.click("#write")
        data = json.loads(config_path.read_text(encoding="utf-8"))
        assert set(data) == {"jira_url", "jira_pat", "language", "read_only"}
        assert data["jira_url"] == _SUCCESS_URL
        assert data["jira_pat"] == _SUCCESS_PAT
        assert data["language"] == "en"
        assert data["read_only"] is False
        assert config_path.stat().st_mode & 0o777 == 0o600
        assert calls == ["/rest/api/2/myself"]
        await pilot.click("#ok")
    assert app.return_code == 0


async def test_es_and_read_only_true_are_persisted(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    _, transport = _transport(200)
    app = SetupApp(config_path=config_path, transport=transport)
    async with app.run_test(headless=True, size=(80, 24)) as pilot:
        app.query_one("#language", Select).value = "es"
        app.query_one("#read_only", Switch).value = True
        await _run_to_confirm(pilot, app)
        await pilot.click("#write")
        data = json.loads(config_path.read_text(encoding="utf-8"))
        assert data["language"] == "es"
        assert data["read_only"] is True
        await pilot.click("#ok")
    assert app.return_code == 0


async def test_defaults_english_and_read_only_false(tmp_path: Path) -> None:
    """Scenario 'Optional fields default when skipped': en/false without touching them."""
    config_path = tmp_path / "config.json"
    _, transport = _transport(200)
    app = SetupApp(config_path=config_path, transport=transport)
    async with app.run_test(headless=True, size=(80, 24)) as pilot:
        _fill(app)
        await _submit_and_wait(pilot, app)
        await pilot.click("#write")
        data = json.loads(config_path.read_text(encoding="utf-8"))
        assert data["language"] == "en"
        assert data["read_only"] is False
        await pilot.click("#ok")
    assert app.return_code == 0


async def test_invalid_url_rejected_without_calling_myself(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    calls, transport = _transport(200)
    app = SetupApp(config_path=config_path, transport=transport)
    async with app.run_test(headless=True, size=(80, 24)) as pilot:
        _fill(app, url="jira.example.com")
        await pilot.click("#continue")
        assert "Invalid URL" in _error_text(app)
        assert calls == []
        assert not config_path.exists()
        assert not isinstance(app.screen, ConfirmModal)


async def test_blank_required_field_shows_required_error(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    calls, transport = _transport(200)
    app = SetupApp(config_path=config_path, transport=transport)
    async with app.run_test(headless=True, size=(80, 24)) as pilot:
        _fill(app, url="", pat=_SUCCESS_PAT)
        await pilot.click("#continue")
        assert _REQUIRED_MSG in _error_text(app)
        assert calls == []
        assert not config_path.exists()
        assert not isinstance(app.screen, ConfirmModal)


async def test_connectivity_401_stays_on_form_with_styled_error(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    calls, transport = _transport(401)
    app = SetupApp(config_path=config_path, transport=transport)
    async with app.run_test(headless=True, size=(80, 24)) as pilot:
        _fill(app)
        await _submit_and_wait(pilot, app)
        assert "Connection failed" in _error_text(app)
        assert "AUTH_UNAUTHORIZED" in _error_text(app)
        assert calls == ["/rest/api/2/myself"]
        assert not config_path.exists()
        assert not isinstance(app.screen, ConfirmModal)
        assert app.query_one("#url", Input) is not None  # still on the form


async def test_confirm_declined_leaves_existing_file_untouched(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    original = json.dumps({"jira_url": "https://old.example.test"})
    config_path.write_text(original, encoding="utf-8")
    _, transport = _transport(200)
    app = SetupApp(config_path=config_path, transport=transport)
    async with app.run_test(headless=True, size=(80, 24)) as pilot:
        await _run_to_confirm(pilot, app)
        await pilot.click("#cancel")
    assert app.return_code == 1
    assert config_path.read_text(encoding="utf-8") == original


async def test_ctrl_c_on_form_exits_1_without_writing(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    _, transport = _transport(200)
    app = SetupApp(config_path=config_path, transport=transport)
    async with app.run_test(headless=True, size=(80, 24)) as pilot:
        await pilot.press("ctrl+c")
    assert app.return_code == 1
    assert not config_path.exists()


async def test_ctrl_c_on_confirm_modal_exits_1(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    _, transport = _transport(200)
    app = SetupApp(config_path=config_path, transport=transport)
    async with app.run_test(headless=True, size=(80, 24)) as pilot:
        await _run_to_confirm(pilot, app)
        await pilot.press("ctrl+c")
    assert app.return_code == 1
    assert not config_path.exists()


async def test_ctrl_q_exits_1(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    _, transport = _transport(200)
    app = SetupApp(config_path=config_path, transport=transport)
    async with app.run_test(headless=True, size=(80, 24)) as pilot:
        await pilot.press("ctrl+q")
    assert app.return_code == 1
    assert not config_path.exists()
