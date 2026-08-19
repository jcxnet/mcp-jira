# Archive Report: `mcp-jira install` client installer

**Change**: mcp-jira-installer
**Archived**: 2026-08-19
**Mode**: openspec (files under `openspec/`); archive-report also persisted to Engram (`sdd/mcp-jira-installer/archive-report`)
**Commit**: e376c41 `feat(mcp_jira): add interactive installer for MCP client registration` (verified present)

## Summary

`mcp-jira install` registers the server into three MCP clients — OpenCode global (`~/.config/opencode/opencode.json`), Claude CLI user scope (top-level `mcpServers` of `~/.claude.json`), and Claude Desktop (`claude_desktop_config.json`, probing `~/.config/Claude/` then `~/.config/claude/`) — with merge-safe, idempotent writes: `.bak` before first write to an existing file, temp-file + `os.replace` (chmod preserves existing mode, 0644 new), post-write re-parse with `.bak` restore + loud failure on corruption, unparseable configs skipped untouched, existing `mcp-jira` entries reported "already registered" and never overwritten, config contents never logged. Registered command is `[sys.executable, "-m", "mcp_jira"]` (absolute, cwd-independent, no `uv` dependency, no `env`). Non-TTY invocation prints guidance and exits 1; `^C` aborts with exit 1, nothing written; confirm-before-write defaults to NO. Stdlib only — no new dependency.

## Final Verification Evidence

Per commit e376c41 + `verify-report.md` (verdict **PASS**, 2026-08-19):

| Metric | Value |
|--------|-------|
| Tests | **184 passed** / 0 failed / 0 skipped (`uv run pytest`, exit 0) |
| Scenarios | **15/15** compliant |
| Requirements | **7/7** compliant |
| Build | `uv run mypy src` — no issues in 12 source files (exit 0) |
| Lint | `uv run ruff check` — no findings (exit 0) |
| Runtime harness | `install --help` exit 0; `install </dev/null` exit 1 + guidance; `setup --help` exit 0 (no regression) |
| Tasks | 12/12 complete (persisted `tasks.md` all `[x]`) |
| CRITICAL / WARNING issues | None (2 SUGGESTIONs, see verify-report) |

Final-state facts forwarded by the orchestrator at launch corroborate the report: 12/12 tasks, commit e376c41, verdict PASS (184 tests, 15/15 scenarios, 7/7 requirements). No contradictions between sources; no stale snapshot claims superseded.

## Spec Sync

| Domain | Action | Details |
|--------|--------|---------|
| client-installer | Created (full spec, mechanical copy) | `openspec/specs/client-installer/spec.md` — 7 requirements / 15 scenarios, byte-identical to the delta (`diff -r` empty, exit 0) |

No baseline existed for `client-installer`; the delta spec IS a full spec and was copied mechanically via shell (`cp` → `diff -r` readback → `mv`), never routed through model Read/Write. No destructive merge; `rules.archive` (warn on destructive deltas) not triggered. The repo's project-level `opencode.json` is NOT a target of the installer and was not touched.

## Artifacts

Archive report: `openspec/changes/mcp-jira-installer/archive-report.md` (this file)
Synced spec: `openspec/specs/client-installer/spec.md`
Engram: topic key `sdd/mcp-jira-installer/archive-report` (project `mcp-jira`)
Change folder: **not moved** — orchestrator explicitly instructed to keep `openspec/changes/mcp-jira-installer/` in place. Active change directory retains proposal.md, explore.md, design.md, tasks.md, verify-report.md, specs/client-installer/spec.md.

## Notes

- **size:exception granted** (user-approved): single PR at ~510 authored lines exceeds the 400-line review budget. Recorded per Review Workload Guard; delivery was a deliberate single-PR exception.
- **`merge_write` injectable dropped during apply** (accepted deviation, orchestrator-amended; behavior verified instead of interface sketch — see verify-report coherence table). No blocking issue.

## Risks

1. **Claude Desktop path untestable on this machine** — `probe_desktop_dir` branch (capital vs lowercase `Claude/`/`claude/`, default) is covered by unit tests only; no live Desktop install exists here to exercise the real write path.
2. **Live `~/.claude.json` merge risk** — merging into a stateful user file can corrupt it if the write goes wrong. Mitigated: `.bak` before first write, temp + `os.replace`, post-write re-parse, `.bak` restore + loud failure on corruption, unparseable source skipped untouched. Residual risk is low but nonzero for the first real-machine run.

## Rollback

Per-file: restore the `.bak` backup or delete the `mcp-jira` key; `git revert` of e376c41 removes the feature. No server/config changes shipped.

## Traceability

Artifacts read: `openspec/changes/mcp-jira-installer/{proposal,design,tasks,verify-report}.md`, `specs/client-installer/spec.md`, `openspec/config.yaml`, `skills/_shared/{sdd-phase-common,openspec-convention}.md`, `sdd-archive/SKILL.md`. Observation IDs: N/A (openspec mode — file paths serve as the audit trail; Engram copy is the only observation).
