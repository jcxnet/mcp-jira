# Delta for Toolchain Bootstrap

## ADDED Requirements

### Requirement: uv-managed project manifest

The project MUST provide a `pyproject.toml` managed by uv declaring `requires-python = ">=3.10"`, and MUST run on the runtime target Python 3.14.7.

#### Scenario: Clean sync on runtime Python

- GIVEN a machine with uv and Python 3.14.7
- WHEN `uv sync` runs at the repo root
- THEN a venv is created and all declared dependencies install without error

#### Scenario: Minimum Python floor

- GIVEN a fresh environment with Python 3.10
- WHEN dependencies are installed and the package is imported
- THEN imports succeed without 3.11+ exclusive syntax

### Requirement: Runtime dependencies

The `pyproject.toml` MUST declare `mcp` (FastMCP) and `httpx` as runtime dependencies.

#### Scenario: Imports resolve

- GIVEN the venv created by `uv sync`
- WHEN `uv run python -c "from mcp.server.fastmcp import FastMCP; import httpx"` executes
- THEN both packages import successfully

### Requirement: Dev tooling

The project MUST declare `pytest`, `ruff`, and `mypy` as dev dependencies.

#### Scenario: Lint, type-check, and tests runnable

- GIVEN the venv
- WHEN `uv run ruff check`, `uv run mypy src`, and `uv run pytest` execute
- THEN all three exit 0 on a clean tree

### Requirement: Project layout and entry point

The project MUST place package code under `src/mcp_jira/` and tests under `tests/`, and MUST declare a `mcp-jira` console script entry point exposing the `setup` subcommand.

#### Scenario: Console script installed

- GIVEN the venv
- WHEN `uv run mcp-jira setup --help` executes
- THEN the CLI responds with setup usage and exits 0

#### Scenario: Mocked test suite runs

- GIVEN the test suite using httpx MockTransport
- WHEN `uv run pytest` executes
- THEN success and error-path tests pass without a live Jira instance

*Trace: SC-2, SC-5, proposal success criterion "uv run pytest green"*