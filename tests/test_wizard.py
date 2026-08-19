"""Unit tests for mcp_jira.wizard (0600 write, connectivity, confirmation, abort)."""

from __future__ import annotations

import json

import httpx
from conftest import AUTH_401, BASE_URL, REST

from mcp_jira import wizard


def _confirm_final_yes(prompt_text: str, default: bool) -> str:
    """Answer "y" only to the final write confirmation; default elsewhere.

    The read_only prompt and the final confirmation share the ``confirm``
    injectable, so tests distinguish them by prompt text. The write
    confirmation prompt contains "Write config".
    """
    return "y" if "Write config" in prompt_text else ""


def test_interactive_success_writes_0600_config(tmp_path, jira_mock, capsys) -> None:
    cfg = tmp_path / "config.json"
    code = wizard.run_wizard(
        config_path=cfg,
        interactive=True,
        prompt=lambda _: BASE_URL,
        hidden_prompt=lambda _: "tok",
        select=lambda *_: "",
        confirm=_confirm_final_yes,
        transport=jira_mock.transport,
    )
    assert code == 0
    assert (cfg.stat().st_mode & 0o777) == 0o600
    assert json.loads(cfg.read_text()) == {
        "jira_url": BASE_URL,
        "jira_pat": "tok",
        "language": "en",
        "read_only": False,
    }
    assert "Config written" in capsys.readouterr().out


def test_connectivity_failure_reports_and_writes_nothing(tmp_path, jira_mock, capsys) -> None:
    jira_mock.route("GET", f"{REST}/myself", status=401, payload=AUTH_401)
    cfg = tmp_path / "config.json"
    confirms: list[str] = []
    code = wizard.run_wizard(
        config_path=cfg,
        interactive=True,
        prompt=lambda _: BASE_URL,
        hidden_prompt=lambda _: "bad-pat",
        select=lambda *_: "",
        confirm=lambda p, _: confirms.append(p) or "",
        transport=jira_mock.transport,
    )
    assert code == 1
    assert not cfg.exists()
    # Only the read_only prompt is confirmed; the final write confirmation is
    # never shown because /myself runs first (design D5).
    assert confirms == ["Read-only mode? (y/N, default no): "]
    err = capsys.readouterr().err
    assert "Connection failed" in err
    assert "AUTH_UNAUTHORIZED" in err
    assert "bad-pat" not in err  # the PAT must never surface


def test_empty_prompt_writes_nothing(tmp_path, capsys) -> None:
    cfg = tmp_path / "config.json"
    code = wizard.run_wizard(
        config_path=cfg,
        interactive=True,
        prompt=lambda _: "   ",
        hidden_prompt=lambda _: "",
    )
    assert code == 1
    assert not cfg.exists()
    assert "required" in capsys.readouterr().err


def test_non_interactive_prints_path_and_exits_nonzero(tmp_path, capsys) -> None:
    cfg = tmp_path / "config.json"
    code = wizard.run_wizard(config_path=cfg, interactive=False)
    assert code == 1
    out = capsys.readouterr().out
    assert str(cfg) in out  # prints the config path
    assert "jira_url" in out  # guidance names the config keys
    assert not cfg.exists()


def test_invalid_url_reprompts_then_writes(tmp_path, jira_mock, capsys) -> None:
    cfg = tmp_path / "config.json"
    answers = iter(["not-a-url", BASE_URL])
    inner = jira_mock.transport
    myself_calls: list[str] = []
    counting = httpx.MockTransport(
        lambda req: myself_calls.append(req.url.path) or inner.handle_request(req)
    )
    code = wizard.run_wizard(
        config_path=cfg,
        interactive=True,
        prompt=lambda _: next(answers),
        hidden_prompt=lambda _: "tok",
        select=lambda *_: "",
        confirm=_confirm_final_yes,
        transport=counting,
    )
    assert code == 0
    assert myself_calls == ["/rest/api/2/myself"]  # /myself hit exactly once
    assert json.loads(cfg.read_text())["jira_url"] == BASE_URL
    assert "Invalid URL" in capsys.readouterr().err


def test_optional_fields_default_when_skipped(tmp_path, jira_mock) -> None:
    cfg = tmp_path / "config.json"
    code = wizard.run_wizard(
        config_path=cfg,
        interactive=True,
        prompt=lambda _: BASE_URL,
        hidden_prompt=lambda _: "tok",
        select=lambda *_: "",  # empty select → default "en"
        confirm=_confirm_final_yes,  # empty read_only confirm → default False
        transport=jira_mock.transport,
    )
    assert code == 0
    data = json.loads(cfg.read_text())
    assert data["language"] == "en"
    assert data["read_only"] is False


def test_read_only_confirmed_true(tmp_path, jira_mock) -> None:
    cfg = tmp_path / "config.json"
    code = wizard.run_wizard(
        config_path=cfg,
        interactive=True,
        prompt=lambda _: BASE_URL,
        hidden_prompt=lambda _: "tok",
        select=lambda *_: "",
        confirm=lambda *_: "y",  # "y" at read_only AND at the final confirmation
        transport=jira_mock.transport,
    )
    assert code == 0
    assert json.loads(cfg.read_text())["read_only"] is True


def test_decline_confirmation_leaves_existing_file(tmp_path, jira_mock) -> None:
    cfg = tmp_path / "config.json"
    cfg.write_text('{"existing": true}')
    before = cfg.read_bytes()
    code = wizard.run_wizard(
        config_path=cfg,
        interactive=True,
        prompt=lambda _: BASE_URL,
        hidden_prompt=lambda _: "tok",
        select=lambda *_: "",
        confirm=lambda *_: "",  # empty → declined (default no)
        transport=jira_mock.transport,
    )
    assert code == 1
    assert cfg.read_bytes() == before  # truncate guard: file untouched


def test_ctrl_c_aborts_without_writing(tmp_path, capsys) -> None:
    cfg = tmp_path / "config.json"

    def interrupt(_: str) -> str:
        raise KeyboardInterrupt

    code = wizard.run_wizard(
        config_path=cfg,
        interactive=True,
        prompt=interrupt,
        hidden_prompt=lambda _: "tok",
    )
    assert code == 1
    assert not cfg.exists()
    assert "Aborted" in capsys.readouterr().err
