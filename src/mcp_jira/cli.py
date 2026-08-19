"""argparse CLI for mcp-jira (design: default `run`, `setup` subcommand).

Both the ``mcp-jira`` console script (``[project.scripts]`` in pyproject.toml)
and ``python -m mcp_jira`` land here. Running without a subcommand starts the
MCP stdio server via :func:`mcp_jira.server.create_server`; ``mcp-jira setup``
runs the interactive config wizard (:func:`mcp_jira.wizard.run_wizard`).
Startup failures (``CONFIG_*``/``AUTH_UNAUTHORIZED``) fail fast: the error is
printed to stderr and the process exits non-zero with no tools exposed.
"""

from __future__ import annotations

import argparse
import sys

from mcp_jira.errors import JiraError
from mcp_jira.installer import run_installer
from mcp_jira.server import create_server
from mcp_jira.wizard import run_wizard


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser; no I/O, so it is trivially testable."""
    parser = argparse.ArgumentParser(
        prog="mcp-jira",
        description="MCP stdio server for self-hosted Jira Data Center.",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    subparsers.add_parser("setup", help="interactively write ~/.config/mcp-jira/config.json")
    subparsers.add_parser("install", help="register mcp-jira into OpenCode/Claude configs")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point; returns the process exit code."""
    args = build_parser().parse_args(argv)
    if args.command == "setup":
        return run_wizard()
    if args.command == "install":
        return run_installer()
    try:
        create_server().run()
    except JiraError as exc:
        print(f"mcp-jira: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
