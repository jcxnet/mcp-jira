# Archive Report: mcp-jira-textual-tui

**Archived**: 2026-08-20
**Source**: `openspec/changes/mcp-jira-textual-tui/` → `openspec/changes/archive/2026-08-20-mcp-jira-textual-tui/`
**Artifact store**: hybrid (OpenSpec change folder + baseline specs + Engram `sdd/mcp-jira-textual-tui/archive-report`)
**Mode**: Standard (Strict TDD OFF per orchestrator; `config.yaml` `strict_tdd: false`)

## Final State (at close)

- **Verify verdict**: PASS (`verify-report.md`, evidence_revision sha256:cd902667…, native `sdd-verify-validate` verdict pass). Blockers 0, CRITICAL findings 0. Requirements 6/6, delta-spec scenarios 20/20 compliant.
- **Tests**: 203 passed / 0 failed / 0 skipped (1 warning) — `uv run pytest -q` exit 0. Pilot suites: 17 passed (`tests/test_tui_setup.py` 10 + `tests/test_tui_install.py` 7).
- **Static checks**: `uv run ruff check` clean, `uv run ruff format --check` clean (31 files), `uv run mypy -p mcp_jira` "Success: no issues found in 13 source files". `cli.py` zero diff across the whole change (`git diff 22c9431 main -- src/mcp_jira/cli.py` = 0 bytes); `tests/test_cli.py` 6/6 unmodified.
- **Lock delta**: 91 insertions, exactly 5 net-new runtime packages (textual 8.2.8, mdit-py-plugins 0.6.1, platformdirs 4.11.3, linkify-it-py 2.1.0, uc-micro-py 2.0.0) + pytest-asyncio 1.4.0 (+ backports-asyncio-runner 1.2.0 dev-transitive).
- **Tasks**: all implementation tasks complete. The archived `tasks.md` shows **18/18 checked, 0 unchecked** (filesystem artifact is the completion-visibility source of truth). Note: `verify-report.md` and the launch prompt state 20/20 — a count discrepancy with the 18 checkboxes (1.1–5.2) in `tasks.md`; every source agrees all work is complete (0 `- [ ]` remaining), so the verdict and the Task Completion Gate are unaffected.
- **Commits on main**: 06de323 (merge #13, final PR of 5). PRs #9–#13 all merged: deps a7c3124, tui.py f395020, wizard wiring b141183, installer wiring 2bda0c7, SetupApp Pilot 632a6b1, InstallApp Pilot 08eb14f, docs 774dde0. No work happened after verify-report was persisted; no extra commits beyond 06de323.
- **Scope**: Textual widget TUI for `mcp-jira setup` and `mcp-jira install` (replacing Rich line prompts). Presentation-layer change only: all logic/write/merge/security lines preserved (non-TTY branches byte-identical, `cli.py` zero diff, 0600/`.bak`/atomic-replace/idempotency semantics untouched).

## Spec Sync

| Domain | Action | Details |
|--------|--------|---------|
| server-config | Updated (2 MODIFIED + 2 ADDED) | `openspec/specs/server-config/spec.md` — MODIFIED **Setup wizard** (Rich line prompts → Textual widget TUI: `Input` url, masked PAT `password=True`, `Select` language, `Switch` read_only, priority `ctrl+c` abort, non-TTY byte-identical; 7 scenarios) and **Wizard testability** (injectable lambdas → Textual Pilot `run_test(headless=True)`; 2 scenarios); ADDED **tui-abort-binding** (2 scenarios) and **connectivity-worker** (`@work(thread=True)` + loading indicator; 2 scenarios). 4 other requirements (Config file schema, Environment overrides, Startup validation, Config file permissions) preserved unchanged. Result: 8 requirements / 22 scenarios. |
| client-installer | Updated (2 MODIFIED) | `openspec/specs/client-installer/spec.md` — MODIFIED **install subcommand** (form-style Rich multi-select → Textual `SelectionList` default-all + inline notices + confirm modal + priority `ctrl+c`; 4 scenarios incl. new "Default selection is all clients") and **Testability** (`_resolve_targets` (previously `_select_targets`) + Pilot-driven flow; 3 scenarios). 5 other requirements (Registration command, OpenCode global, Claude CLI user-scope, Claude Desktop, Write safety) preserved unchanged. Result: 7 requirements / 18 scenarios. |

**Merge method**: delta application per the OpenSpec convention — MODIFIED replaces the full requirement block in the main spec (verbatim from the delta), ADDED appends, requirements not in the delta untouched. Every merged block was verified byte-verbatim against its delta source (scripted comparison; only the delta's section header `## ADDED Requirements` separates blocks — the block bodies are identical). No REMOVED/RENAMED sections in the deltas. Non-goals and the change's unadopted items (nothing) were not injected. `rules.archive` (warn on destructive deltas): not triggered — no requirement was deleted; the two MODIFIED blocks are in-place replacements of requirements that the delta explicitly updated.

## Archive Contents

- `proposal.md` ✅
- `explore.md` ✅ (optional artifact, preserved)
- `specs/server-config/spec.md` ✅ (delta spec)
- `specs/client-installer/spec.md` ✅ (delta spec)
- `design.md` ✅
- `tasks.md` ✅ (18/18 tasks checked, 0 unchecked)
- `verify-report.md` ✅
- `archive-report.md` — this file (additive; excluded from the byte-identity readback)

**Mechanical copy verification**: the change folder was moved with a native shell `mv` (fallback after `git mv` failed — folder is untracked per repo convention), compared against a pre-move recursive snapshot (`cp -R` to a temp dir taken before the move). Verbatim `diff -r` readback: **empty (byte-identical), exit 0**. Active `openspec/changes/` no longer contains this change (verified: `openspec/changes/mcp-jira-textual-tui/` absent).

## Gates

- **Native Review Receipt Gate**: `reviewGate` structurally absent — no structured status, no `state.yaml`, no review artifacts existed for this candidate. Archive proceeds under ordinary repository policy (no review was ever started; the post-verify review offer, if any, was an invitation, not a gate).
- **Task Completion Gate**: passed — archived `tasks.md` has 0 unchecked implementation tasks; no stale-checkbox reconciliation was needed or performed.
- **CRITICAL gate**: passed — verify report has `critical_findings: 0`, `blockers: 0`.
- **Action Context Guard**: no `actionContext`/`allowedEditRoots` constraints were supplied; operations stayed inside the repo.

## Traceability (Engram observation IDs read)

| Artifact | Observation ID | Persisted |
|----------|----------------|-----------|
| explore | #991 | 2026-08-20 10:41:18 |
| proposal | #992 | 2026-08-20 10:42:51 |
| spec | #993 | 2026-08-20 10:44:43 |
| design | #994 | 2026-08-20 10:48:27 |
| tasks | #995 | 2026-08-20 10:52:18 |
| apply-progress | #996 | 2026-08-20 11:20:31 |
| verify-report | #997 | 2026-08-20 12:02:48 |

**Traceability notes**:
- Engram observation #995 (tasks) was persisted at spec time with the original task structure; the filesystem `tasks.md` is the authoritative completion record (all `[x]`, 0 unchecked), corroborated by apply-progress #996 and verify-report #997.
- The change folder contained no `state.yaml` (an orchestrator artifact); everything present was archived. Not blocking.

## Open Follow-ups (recorded, NOT fixed by archive)

- **S1 (from verify)**: Add an explicit in-flight assertion that `LoadingIndicator#loading` is displayed (e.g. pause between submit and `wait_for_complete`) to fully pin the visible state of connectivity-worker scenario "Check runs without freezing the UI". Implementation and toggle paths are already runtime-exercised and green; test hardening only.
- **S2 (from verify)**: Add an assertion that the SetupApp ConfirmModal summary text does not contain the PAT value (privacy guard is currently static-evidence only; the install modal's paths-only summary is already asserted).
- **WARNING-1 / SUGGESTION-1 / SUGGESTION-2 (from rich-tui archive, still open)**: `config.yaml` `verify.build_command` path is a no-op under the src layout (should be `uv run python -m compileall src/mcp_jira`); `testing.coverage_command` errors (`pytest-cov` not installed, threshold 0 so never gates); load-bearing prompt strings should stay frozen on future styling changes.

## Verdict

The `mcp-jira-textual-tui` change — Textual widget TUI for `mcp-jira setup` and `mcp-jira install` — is fully planned, implemented, verified, and archived. SDD cycle complete. No intentional-with-warnings conditions apply (all 20/20-claimed tasks complete per all sources; archived tasks.md shows 18/18 checked, 0 unchecked).