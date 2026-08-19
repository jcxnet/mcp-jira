"""Unit tests for mcp_jira.cli (argparse parsing + subcommand dispatch)."""

from __future__ import annotations

import pytest

from mcp_jira import cli
from mcp_jira.errors import JiraError


def test_no_command_defaults_to_run() -> None:
    args = cli.build_parser().parse_args([])
    assert args.command is None  # default action: start the server


def test_setup_subcommand_parses() -> None:
    args = cli.build_parser().parse_args(["setup"])
    assert args.command == "setup"


def test_setup_help_exits_zero(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.build_parser().parse_args(["setup", "--help"])
    assert exc.value.code == 0
    assert "setup" in capsys.readouterr().out


def test_main_run_starts_server(monkeypatch) -> None:
    calls: list[str] = []

    class FakeApp:
        def run(self) -> None:
            calls.append("run")

    monkeypatch.setattr(cli, "create_server", lambda: FakeApp())
    assert cli.main([]) == 0
    assert calls == ["run"]


def test_main_run_reports_startup_error_exit_nonzero(monkeypatch, capsys) -> None:
    def _fail() -> None:
        raise JiraError("CONFIG_MISSING", "Configuration missing.")

    monkeypatch.setattr(cli, "create_server", _fail)
    assert cli.main([]) == 1
    assert "CONFIG_MISSING" in capsys.readouterr().err


def test_main_setup_dispatches_wizard(monkeypatch) -> None:
    monkeypatch.setattr(cli, "run_wizard", lambda: 7)
    assert cli.main(["setup"]) == 7
