# Proposal: mcp-jira MVP

## Intent

AI agents cannot natively talk to self-hosted Jira Data Center. Every Jira operation requires manual steps or ad-hoc scripts. This change builds `mcp-jira`: a stdio MCP server exposing 9 Jira REST v2 tools (search/get/create/update/transition/comment/comments/projects/fields), authenticated with a user PAT, configured via `~/.config/mcp-jira/config.json` and an interactive `mcp-jira setup` wizard. Source of truth: `PRD.md` v1.0.0.

## Scope

### In Scope
- Toolchain bootstrap: `pyproject.toml` via uv, venv, deps (`mcp`/FastMCP, `httpx`), pytest + ruff + mypy (prerequisite task of this change).
- Config layer: file loader with env overrides (`JIRA_URL`/`JIRA_PAT`), `language` (en/es) and `read_only` flags, startup validation (missing/invalid config, `/myself` credential check).
- `mcp-jira setup` wizard CLI: prompts URL + hidden PAT, connectivity test, writes `0600` config.
- 9 MCP tools per PRD §3.1: `search_issues`, `get_issue`, `create_issue`, `update_issue`, `transition_issue`, `add_comment`, `get_comments`, `list_projects`, `list_fields`.
- Custom-field support: field map from `GET /rest/api/2/field` cached at startup; name or raw `customfield_XXXXX` ID in get/create/update.
- Error model §4.4: stable error codes, precedence, retry policy (no auto-retry on 429), PAT redacted from logs, no stack traces surfaced.
- README: `mcpServers` blocks for OpenCode, Claude Desktop, Claude CLI.
- Mocked-HTTP pytest suite covering success + error paths (401/403/404/429/invalid JQL/invalid transition).

### Out of Scope
- Jira Cloud, Server < 9.0, OAuth2 — PAT only.
- Sprints/boards, attachments, watchers, time tracking (v1.1).
- HTTP/SSE transport, Docker image (v1.2).
- Multi-user auth service; local/offline storage.

## Capabilities

### New Capabilities
- `toolchain-bootstrap`: uv/pyproject/venv, pytest + httpx + mcp deps, ruff/mypy config.
- `server-config`: config load/validate (file + env override), `language`, `read_only`, startup credential check, `mcp-jira setup` wizard.
- `jira-tools`: 9 MCP tools over REST v2 with structured JSON outputs and custom-field name resolution.
- `error-handling`: §4.4 error model — stable codes, precedence, retry policy, redacted logging.

### Modified Capabilities
None — greenfield repo, no existing specs.

## Approach

FastMCP stdio server; `httpx.Client` with `Authorization: Bearer <PAT>`; config loaded once at startup (fail fast on `CONFIG_*`); field map fetched and cached at startup; every tool wraps HTTP calls through a shared error mapper implementing §4.4 codes/precedence; `setup` is a CLI entrypoint writing the config file. Tests use `httpx.MockTransport` to simulate Jira responses.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `pyproject.toml` | New | uv-managed deps + dev deps |
| `src/mcp_jira/` | New | server, config, client, error mapping, tools, setup CLI |
| `tests/` | New | mocked-HTTP pytest suite |
| `README.md` | New | setup + `mcpServers` examples |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Jira DC REST v2 response variance | Med | Mocked tests from real DC payload shapes; smoke test against real instance |
| PAT leak in logs/output | Med | Redaction helper + security check in test suite |
| Custom field name ambiguity | Low | Field map cache; accept raw IDs as fallback |

## Rollback Plan

Greenfield: no production code exists. Worst case, delete `src/`, `pyproject.toml`, `tests/` and revert to empty repo (nothing to migrate). Config file is user-owned and outside the repo.

## Dependencies

- Python 3.10+ (runtime 3.14.7), uv, official `mcp` SDK, `httpx`.
- Reachable Jira Data Center 9.0+ instance + PAT for smoke tests (mock tests do not require it).

## Success Criteria

- [ ] All 9 tools registered and returning structured JSON per PRD §3.1.
- [ ] Config missing/invalid fails fast with `CONFIG_MISSING`/`CONFIG_INVALID`; `/myself` check at startup.
- [ ] `mcp-jira setup` writes `0600` config after connectivity test; non-interactive run prints path and exits non-zero.
- [ ] `language: es` switches tool names/descriptions; `read_only: true` blocks the 4 mutating tools with `READ_ONLY_MODE`.
- [ ] Mocked suite covers success + 401/403/404/429/invalid JQL/invalid transition mapped to §4.4 codes; no stack trace or PAT in any surfaced error.
- [ ] `uv run pytest` green; README includes working `mcpServers` blocks for the 3 agents.