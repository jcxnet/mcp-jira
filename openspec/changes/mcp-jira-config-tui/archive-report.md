# Archive Report: mcp-jira-config-tui

**Archived**: 2026-08-19
**Mode**: openspec (repo-local filesystem)
**Strict TDD**: disabled (config.yaml `strict_tdd: false`)

## Change Summary

Extended the `mcp-jira setup` wizard in place (src/mcp_jira/wizard.py) from a 2-key prompt (URL + hidden PAT) to a form-style flow: optional `language` (en/es, default en) and `read_only` (y/n, default false) prompts, `http(s)://` URL format validation before connectivity, a pre-write summary + confirmation step (default NO — fixes silent overwrite), and clean `^C` abort. Zero new dependencies (stdlib only). Kept inside PRD §2.4's file-based-config boundary — this is the creation form, not a widget TUI (user decision, non-negotiable).

## Specs Synced

| Domain | Action | Details |
|--------|--------|---------|
| server-config | Updated | 1 MODIFIED (Setup wizard — full new form, 7 scenarios) + 1 ADDED (Wizard testability — 2 scenarios); 4 other requirements preserved unchanged |

- **Merged into**: `openspec/specs/server-config/spec.md`
- **Delta source**: `openspec/changes/mcp-jira-config-tui/specs/server-config/spec.md`
- Merge followed the OpenSpec convention: MODIFIED replaces the full requirement block; ADDED appends; requirements not in the delta untouched.

## Artifacts

Change folder retained in place (see Deviation note below):

- `openspec/changes/mcp-jira-config-tui/proposal.md` ✅
- `openspec/changes/mcp-jira-config-tui/specs/server-config/spec.md` ✅ (delta spec — merged into main spec)
- `openspec/changes/mcp-jira-config-tui/design.md` ✅
- `openspec/changes/mcp-jira-config-tui/tasks.md` ✅ (11/11 tasks complete)
- `openspec/changes/mcp-jira-config-tui/verify-report.md` ✅
- `openspec/changes/mcp-jira-config-tui/archive-report.md` ✅ (this file, additive)

## Final Verification Evidence (at close)

| Metric | Value | Source |
|--------|-------|--------|
| Tasks | 11/11 complete (`- [x]` in tasks.md) | tasks.md (persisted artifact — Task Completion Gate passed) |
| Verdict | PASS | verify-report.md (verdict: pass) |
| Tests | 166 passed / 0 failed / 0 skipped, exit 0 | verify-report.md + orchestrator final-state facts |
| Scenarios | 9/9 compliant (7 Setup wizard + 2 Wizard testability) | verify-report.md compliance matrix |
| Requirements | 2/2 | verify-report.md |
| Build | ruff + mypy clean (exit 0) | verify-report.md |
| CRITICAL findings | 0 | verify-report.md |
| uv.lock | unchanged (no new dependency) | verify-report.md (commits 9e462b3 / 37e3781; last change: bootstrap 8055bec) |
| Commits | 9e462b3 (implementation), 37e3781 (tasks.md checkbox syntax fix) | git log |

### tasks.md checkbox syntax fix (format-only)

Commit 37e3781 corrected tasks.md checkbox syntax (stray `^` prefix removed) to meet the dispatcher's standard `- [x]` requirement. This is a format-only correction — no behavior change; all 11 tasks were already complete. Recorded for audit-trail accuracy.

### Design open question — resolution

design.md's Open Question (existing-suite-unaffected scenario amended reading) was resolved at verify: the four wizard tests pass after adding `select`/`confirm` lambdas to tests 1–2 and extending test 1's expected dict to the 4-key write; tests 3–4 byte-identical. Per verify-report §Spec Compliance Matrix, "Existing suite unaffected" is compliant under the amended reading (9/9 scenarios). No unresolved contradiction at close.

## Risks / Open Items

- **Manual full-TTY smoke recommended**: the automated suite drives the wizard via injected lambdas; an end-to-end `uv run mcp-jira setup` on a real TTY (4-key write, 0600 perms, confirmation flow) is still a recommended manual check — no pexpect dependency exists to automate it.
- **Real-DC smoke out-of-band**: connectivity path is verified against a mock transport only; a real Jira Data Center `/myself` check remains out-of-band.

## Deviation Note (intentional, orchestrator-instructed)

The standard archive flow moves the change folder to `openspec/changes/archive/YYYY-MM-DD-{change-name}/`. For this change the orchestrator explicitly instructed: **do NOT delete the change directory** — archive in place. Therefore no folder move and no move `diff -r` readback applies (nothing was copied or moved; no bytes passed through the model). The change folder remains at `openspec/changes/mcp-jira-config-tui/` with this archive-report as the terminal record. The main-spec merge (MODIFIED + ADDED) is a delta application per the OpenSpec convention, not a byte-copy operation; the merged content was read back and verified against the delta source (all 7 + 2 scenarios present verbatim, 4 preserved requirements intact).

PR creation is orchestrator-owned (single PR — low risk forecast, no chain needed).
