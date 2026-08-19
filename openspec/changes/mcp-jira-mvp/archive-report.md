# Archive Report: mcp-jira MVP

- **Change**: mcp-jira-mvp
- **Archived**: 2026-08-19
- **Mode**: hybrid (OpenSpec baseline sync + Engram persistence)
- **Source of truth**: PRD.md v1.0.0 (2026-08-19)
- **Commit range**: 1a6c0bb..7b9819b (6 commits, PR 1 toolchain bootstrap → PR 6 error-path suite + README; stacked-to-main, NOT pushed — PR creation is orchestrator-owned)

## Change Summary

Built `mcp-jira`: a stdio MCP server for self-hosted Jira Data Center 9.0+ exposing 9 REST v2 tools (search/get/create/update/transition/comment/comments/projects/fields), PAT auth, config file `~/.config/mcp-jira/config.json` (en/es language, read_only flag), `mcp-jira setup` wizard, stable §4.4 error model, and an offline mocked-HTTP pytest suite. Greenfield: toolchain bootstrap (uv/pyproject), config layer, HTTP client with retry, field-map resolution, FastMCP server, CLI, README.

## Artifacts Synced to Baseline

Delta specs merged into `openspec/specs/` (all four were ADDED requirements; baseline `openspec/specs/` did not exist before this change, so each delta became the initial baseline spec, copied byte-identical via shell `cp` + verified with `diff -r`):

| Domain | Baseline path | Action | Requirements | Scenarios |
|--------|--------------|--------|--------------|-----------|
| toolchain-bootstrap | `openspec/specs/toolchain-bootstrap/spec.md` | Created (ADDED) | 4 | 6 |
| server-config | `openspec/specs/server-config/spec.md` | Created (ADDED) | 5 | 12 |
| jira-tools | `openspec/specs/jira-tools/spec.md` | Created (ADDED) | 4 | 10 |
| error-handling | `openspec/specs/error-handling/spec.md` | Created (ADDED) | 4 | 7 |

Totals: 17 requirements / 35 scenarios synced.

**Spec-wording fix applied (WARNING-1)**: in `openspec/specs/toolchain-bootstrap/spec.md`, the "Imports resolve" scenario command was amended from the literal `import fastmcp, httpx` to `from mcp.server.fastmcp import FastMCP; import httpx`. Under the pinned `mcp>=1.0,<2` layout, FastMCP lives at `mcp.server.fastmcp`; the top-level `fastmcp` module does not exist. The dependency pin and the requirement text (declare `mcp` (FastMCP) + `httpx`) are unchanged. This matches the runtime-verified import path (see verify-report WARNING-1).

## Final Verification Evidence

Per `verify-report` (sha256 evidence `5ade094b...`, verdict `pass`, 0 blockers, 0 CRITICAL findings) — confirmed current by the orchestrator; no work occurred after verify-report was persisted:

- **Tasks**: 16/16 complete (`[x]`), no stale unchecked implementation tasks.
- **Tests**: 161 passed, 0 failed, 0 skipped (`uv run pytest`, exit 0). Single warning is a third-party `pydantic_settings` warning from FastMCP internals — not project code.
- **Lint/type**: `uv run ruff check` clean; `uv run mypy src` — "Success: no issues found in 11 source files" (both exit 0). Ruff target py310 + mypy python_version 3.10 prove the 3.10 floor statically.
- **Runtime harness**: `uv run python -m mcp_jira --help` exit 0; `uv run mcp-jira setup --help` exit 0; non-TTY `mcp-jira setup` exits 1 with guidance (per spec); `uv sync --dry-run` no changes; FastMCP constructs at `mcp.server.fastmcp`.
- **Spec compliance**: 17/17 requirements, 35/35 scenarios compliant.
- **Coverage**: not measured — no coverage tooling declared; not a gate per specs/design.

## Out-of-Band Notes

- Manual smoke against a real Jira Data Center instance is DEFERRED to post-setup (design §3.2 / tasks 6.3): the offline suite uses `httpx.MockTransport`; real-DC smoke requires a live instance + PAT and is not automated.
- `FIELD_NOT_EDITABLE` is defined (precedence tuple, EN/ES templates) but never emitted — read-only-field updates surface as `VALIDATION_ERROR` (same precedence class). SUGGESTION-1 from verify-report; accepted as-is for MVP.
- Coverage metric and pytest-cov (SUGGESTION-2) deferred unless a coverage gate becomes a project requirement.
- `pydantic_settings IncompleteFieldDefinitionWarning` from FastMCP internals (SUGGESTION-3) — harmless; may be silenced via filterwarnings later.
- Commits 1a6c0bb..7b9819b are NOT pushed; PR creation is orchestrator-owned.

## Risks

| Risk | Status |
|------|--------|
| Jira DC REST v2 response variance in real environments | Open — mitigated by mocked tests from real payload shapes; manual smoke deferred to post-setup |
| PAT leak in logs/output | Closed — redaction helper + security sweep (8 tools × 6 statuses) in test suite |
| Custom-field name ambiguity | Closed — field-map cache with raw-ID fallback; ambiguous names fail with VALIDATION_ERROR |

## Change Directory

Per orchestrator instruction, the change folder `openspec/changes/mcp-jira-mvp/` is retained (OpenSpec conventions keep change artifacts as the audit trail; no move to `openspec/changes/archive/`). This report lives alongside `proposal.md`, `design.md`, `tasks.md`, `verify-report.md`, and `specs/`.
