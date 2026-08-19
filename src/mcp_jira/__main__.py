"""`python -m mcp_jira` entry point.

Runs the mcp-jira CLI server. The CLI module (``mcp_jira.cli``) lands with the
setup wizard in Phase 5; until then this module reports the package version.
Phase 5 rewires the body to ``from mcp_jira.cli import main``.
"""

from mcp_jira import __version__


def main() -> int:
    """Entry point; returns the process exit code."""
    print(f"mcp-jira {__version__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
