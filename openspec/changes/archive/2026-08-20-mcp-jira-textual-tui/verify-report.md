```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:cd90266710810178d6f12f25d09076557e3c3d93403b83ff2a6a21efccdc98e4
verdict: pass
blockers: 0
critical_findings: 0
requirements: 6/6
scenarios: 20/20
test_command: uv run pytest -q
test_exit_code: 0
test_output_hash: sha256:af97e27d2dfc29741b07cc15e57638fad8c03c8c34fbcadb9a7a2f4cbc776ef0
build_command: uv run mypy -p mcp_jira
build_exit_code: 0
build_output_hash: sha256:8f3f4c0ebcb835e848682f2c6610a1bf32c86a993bdb626d9ff36e3a49408398
```

## Verification Report

**Change**: mcp-jira-textual-tui
**Version**: delta specs (server-config, client-installer) at 06de323 (main)
**Mode**: Standard (Strict TDD OFF per orchestrator; no strict-tdd module loaded)
**Test runner**: `uv run pytest` (pytest-asyncio, `asyncio_mode = "auto"`)

### Completeness
| Metric | Value |
|--------|-------|
| Tasks total | 20 |
| Tasks complete | 20 |
| Tasks incomplete | 0 |

`openspec/changes/mcp-jira-textual-tui/tasks.md` shows 20/20 `[x]`. Engram apply-progress (#996, topic `sdd/mcp-jira-textual-tui/apply-progress`) confirms the cumulative apply record: PRs 9-13 merged to main at 06de323 (deps a7c3124, tui.py f395020, wizard wiring b141183, installer wiring 2bda0c7, SetupApp Pilot 632a6b1, InstallApp Pilot 08eb14f, docs 774dde0).

### Build & Tests Execution

**Build (type-check)**: ✅ Passed — `uv run mypy -p mcp_jira` exit 0, `Success: no issues found in 13 source files`.
**Lint**: ✅ Passed — `uv run ruff check` exit 0 (no findings); `uv run ruff format --check` exit 0 (31 files already formatted).
**Tests**: ✅ 203 passed / 0 failed / 0 skipped (1 warning) — `uv run pytest -q` exit 0.
**Pilot suites**: ✅ 17 passed — `uv run pytest tests/test_tui_setup.py tests/test_tui_install.py -q` (10 SetupApp + 7 InstallApp) exit 0.
**Coverage**: ➖ Not available — no coverage gate configured in this repo's verify tooling.

```text
$ uv run pytest -q
203 passed, 1 warning in 9.28s
$ uv run pytest tests/test_tui_setup.py tests/test_tui_install.py -q
17 passed in 5.85s
$ uv run ruff check
[] (exit 0)
$ uv run ruff format --check
31 files already formatted (exit 0)
$ uv run mypy -p mcp_jira
Success: no issues found in 13 source files (exit 0)
$ uv run mcp-jira setup </dev/null
Config path: /home/jcxnet/.config/mcp-jira/config.json
Run `mcp-jira setup` on a terminal to create it, or write it yourself with keys `jira_url` and `jira_pat` (optional: `language`, `read_only`).
(exit 1)
$ uv run mcp-jira install </dev/null
Run `mcp-jira install` on a terminal to register mcp-jira into MCP clients (OpenCode global, Claude CLI user scope, Claude Desktop).
(exit 1)
$ uv run python -c "from mcp_jira import tui; print(tui.__name__)"
mcp_jira.tui
```

Behavioral gates (task 5.2 / proposal Success Criteria):
- `git --no-pager diff 22c9431 main -- src/mcp_jira/cli.py` = **0 bytes** (cli.py zero diff across the whole change).
- `tests/test_cli.py`: **6/6 passed**, unmodified.
- Non-TTY branches byte-identical to base 22c9431: `_GUIDANCE` strings and `print(f"Config path: {path}")`/`print(_GUIDANCE); return 1` are source-identical AND runtime-verified (`setup`/`install </dev/null` → exit 1).
- `grep -rn "mcp_jira.ui\|rich.prompt\|from rich" src/ tests/` → **empty**; literal `Rich` grep in src/ + tests/ → **empty**; `ui.py` and `tests/test_rich_adapters.py` deleted (absent from tree).
- uv.lock delta vs 22c9431 = 91 insertions, exactly 5 net-new runtime packages (textual 8.2.8, mdit-py-plugins 0.6.1, platformdirs 4.11.3, linkify-it-py 2.1.0, uc-micro-py 2.0.0) + pytest-asyncio 1.4.0 (+ backports-asyncio-runner 1.2.0 dev-transitive). pyproject: `textual>=8.2,<9`, dev `pytest-asyncio`, `asyncio_mode = "auto"`.

### Spec Compliance Matrix (delta specs)

Requirement/scenario counts are the authoritative counts read from the two delta specs (6 requirements, 20 scenarios total).

**server-config/spec.md**

| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| Setup wizard | Interactive success | `tests/test_tui_setup.py > test_success_writes_0600_with_four_keys_and_exits_zero` | ✅ COMPLIANT |
| Setup wizard | Optional fields default when skipped | `test_tui_setup.py > test_defaults_english_and_read_only_false` (+ `test_es_and_read_only_true_are_persisted`) | ✅ COMPLIANT |
| Setup wizard | Invalid URL format rejected | `test_tui_setup.py > test_invalid_url_rejected_without_calling_myself` | ✅ COMPLIANT |
| Setup wizard | Confirmation declined aborts | `test_tui_setup.py > test_confirm_declined_leaves_existing_file_untouched` | ✅ COMPLIANT |
| Setup wizard | Ctrl-C aborts cleanly | `test_tui_setup.py > test_ctrl_c_on_form_exits_1_without_writing`, `test_ctrl_c_on_confirm_modal_exits_1` | ✅ COMPLIANT |
| Setup wizard | Connectivity failure | `test_tui_setup.py > test_connectivity_401_stays_on_form_with_styled_error` | ✅ COMPLIANT |
| Setup wizard | Non-interactive without config | `test_wizard.py > test_non_interactive_prints_path_and_exits_nonzero` (+ runtime smoke `setup </dev/null` exit 1) | ✅ COMPLIANT |
| Wizard testability | Pilot drives the full flow | `test_tui_setup.py > test_success_writes_0600_with_four_keys_and_exits_zero` (headless, injected transport/config_path) | ✅ COMPLIANT |
| Wizard testability | Non-TTY and write tests unaffected | `test_wizard.py` non-TTY + 4 `_write_config` tests (kept vs base 22c9431) | ✅ COMPLIANT |
| tui-abort-binding | Ctrl-C on a form input | `test_tui_setup.py > test_ctrl_c_on_form_exits_1_without_writing` | ✅ COMPLIANT |
| tui-abort-binding | Ctrl-C on the confirm modal | `test_tui_setup.py > test_ctrl_c_on_confirm_modal_exits_1` (+ `test_ctrl_q_exits_1`) | ✅ COMPLIANT |
| connectivity-worker | Check runs without freezing the UI | Worker path exercised in success/401 Pilot tests (`app.workers.wait_for_complete()` proves no UI freeze/deadlock); `#loading` widget existence + display toggle executed in every submit path (`query_one` raises if absent) — direct in-flight visible-state assertion not present (see S1) | ✅ COMPLIANT |
| connectivity-worker | Worker failure keeps the form open | `test_tui_setup.py > test_connectivity_401_stays_on_form_with_styled_error` | ✅ COMPLIANT |

**client-installer/spec.md**

| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| install subcommand | Interactive install | `test_tui_install.py > test_success_merges_all_three_targets_with_modes_and_backups` | ✅ COMPLIANT |
| install subcommand | Default selection is all clients | `test_tui_install.py > test_default_selection_is_all_three_clients` (+ `test_installer.py > test_resolve_targets_empty_selects_all`) | ✅ COMPLIANT |
| install subcommand | Non-TTY guidance | `test_installer.py > test_non_interactive_prints_guidance_exits_1` (+ runtime smoke `install </dev/null` exit 1) | ✅ COMPLIANT |
| install subcommand | Ctrl-C aborts cleanly | `test_tui_install.py > test_ctrl_c_on_selection_screen_writes_nothing_and_exits_1` (shared `_AbortMixin` also covers modal) | ✅ COMPLIANT |
| Testability | Injectable temp-dir tests | `test_installer.py` 11 pure tests (load_json×2, upsert_client×2, write_with_backup×4, probe_desktop_dir×3) + `test_tui_helpers.py` | ✅ COMPLIANT |
| Testability | Pilot drives the interactive flow | `test_tui_install.py` (7 Pilot tests, headless, injected config paths) | ✅ COMPLIANT |
| Testability | Pure-function suite unaffected | `git diff 22c9431 main -- tests/test_installer.py` shows only the 6 flow tests + helper deleted; pure tests unchanged and passing | ✅ COMPLIANT |

**Compliance summary**: 20/20 scenarios compliant (scenario 12's loading-indicator visible state is runtime-exercised but not directly asserted — see S1).

### Requirements Traceability Table

| Delta-spec requirement | Implementation evidence | Verdict |
|------------------------|-------------------------|---------|
| server-config: Setup wizard | `src/mcp_jira/tui.py` `SetupApp` (lines 131-242): `Input#url`, `Input#pat(password=True)`, `Select#language` (en default), `Switch#read_only`; blank → `_REQUIRED_MSG` stay, `!_valid_url` → error stay, `/myself` never called on invalid; confirm summary (URL/language/read_only/path, never PAT) → `_write_config` 0600 → ResultScreen; `src/mcp_jira/wizard.py` `_write_config` (43-67) os.open 0o600 + os.chmod, 4 keys; `run_wizard` (70-98) TTY-gated wrapper, non-TTY byte-identical | SATISFIED |
| server-config: Wizard testability | `SetupApp(config_path=..., transport=...)` constructor injection; `tests/test_tui_setup.py` 10 Pilot tests `run_test(headless=True, size=(80,24))`; `tests/test_wizard.py` non-TTY + `_write_config` unit tests unchanged vs base | SATISFIED |
| server-config: tui-abort-binding | `src/mcp_jira/tui.py` `_AbortMixin` (61-83): `Binding("ctrl+c", "abort", show=False, priority=True)` + `ctrl+q`, `action_abort` → `self.app.exit(return_code=1)`; mixed into SetupApp, InstallApp, ConfirmModal, ResultScreen; Pilot tests prove exit 1 + nothing written/truncated | SATISFIED |
| server-config: connectivity-worker | `src/mcp_jira/tui.py` `check_connectivity` (189-201) `@work(thread=True)`, `call_from_thread` guarded by `get_current_worker().is_cancelled`; `LoadingIndicator#loading` shown in flight, hidden on ok/fail; fail → styled error, stays on form; ok → ConfirmModal | SATISFIED |
| client-installer: install subcommand | `src/mcp_jira/tui.py` `InstallApp` (245-309): `SelectionList` 3 `_TARGETS` all pre-checked, `_resolve_targets(selected, _IDS)` empty→all/dedupe/order, inline `Static#notices`, ConfirmModal (paths only) → per-path `write_with_backup`; `src/mcp_jira/installer.py` `run_installer` (157-182) TTY-gated wrapper; `.bak` once + `os.replace` atomic + post-write re-parse restore + `[sys.executable, "-m", "mcp_jira"]` preserved | SATISFIED |
| client-installer: Testability | `load_json`/`upsert_client`/`write_with_backup`/`probe_desktop_dir`/`_resolve_targets` unit-tested with injected temp-dir paths (test_installer.py + test_tui_helpers.py); `InstallApp(config_paths=...)` injection + 7 Pilot tests | SATISFIED |

### Correctness (Static Evidence)

| Check | Status | Notes |
|-------|--------|-------|
| cli.py zero diff | ✅ | `git diff 22c9431 main -- src/mcp_jira/cli.py` = 0 bytes |
| Non-TTY byte-identical | ✅ | `_GUIDANCE` + print statements source-identical to 22c9431; runtime smokes match, exit 1 |
| 0600 write semantics | ✅ | os.open 0o600 + chmod enforcement; 4 keys; parent dirs created |
| .bak once + atomic replace + re-parse restore | ✅ | `write_with_backup` pinned by 4 unit tests + app-level Pilot assertions |
| Idempotent already-registered / corrupt-skip | ✅ | `_collect_pending` notices + untouched files; unit + Pilot tests |
| No dead Rich code | ✅ | `mcp_jira.ui`/`rich.prompt`/`from rich` grep empty; `ui.py`, `test_rich_adapters.py`, `_rich_*`, `_select_targets` removed |
| Exit-code int contract | ✅ | Every exit path returns int (abort/decline → 1, success → 0); wrappers return `app.return_code` |
| Lock delta | ✅ | Exactly 5 net-new runtime + pytest-asyncio (+ backports dev-transitive), 91 insertions |
| venv-absolute command preserved | ✅ | `[sys.executable, "-m", "mcp_jira"]` in all 3 `_TARGETS` entries, unchanged |

### Coherence (Design)

| Decision | Followed? | Notes |
|----------|-----------|-------|
| D-^C priority abort binding | ✅ Yes | Priority `ctrl+c`/`ctrl+q`, `show=False`, `action_abort` → exit 1; docstring documents the DOMNode-subclass requirement for BINDINGS merge |
| D-TTY non-TTY gate | ✅ Yes | `_is_interactive()` + `interactive` kwarg; wrapper returns 1 before app construction |
| D-WORKER threaded /myself | ✅ Yes | `@work(thread=True)` + `call_from_thread` + `is_cancelled` guard + LoadingIndicator |
| D-TEST pytest-asyncio Pilot | ✅ Yes | `asyncio_mode = "auto"`; 17 Pilot tests headless `size=(80,24)` |
| D-DEAD rich removal | ✅ Yes | `ui.py` + `_rich_*` + `test_rich_adapters.py` deleted; grep clean |
| D-DEP dependency delta | ✅ Yes | textual>=8.2,<9 + pytest-asyncio; 5 net-new runtime lock entries |
| D-SEL `_resolve_targets` rename | ✅ Yes | Pure function + 3 unit tests; client-installer §Testability prose already says "`_resolve_targets` (previously `_select_targets`)" — no spec touch-up needed (open question 1 resolved) |
| D-WRAP wrapper signatures | ✅ Yes | `run_wizard(*, config_path, interactive, transport)` / `run_installer(*, interactive, config_paths)`; constructor injection on both apps (open question 2 resolved: `show=False` confirmed) |

### Issues Found

**CRITICAL**: None.

**WARNING**: None.

**SUGGESTION**:
- S1: Add an explicit in-flight assertion that `LoadingIndicator#loading` is displayed (e.g. pause between submit and `wait_for_complete`) to fully pin the visible state of connectivity-worker scenario "Check runs without freezing the UI". Implementation and toggle paths are already runtime-exercised and green; this is test hardening only.
- S2: Add an assertion that the SetupApp ConfirmModal summary text does not contain the PAT value (privacy guard is currently static-evidence only; the install modal's paths-only summary is already asserted).

### Verdict

**PASS**
All 20 tasks complete, all 6 delta-spec requirements satisfied, 20/20 scenarios compliant with passing runtime tests, every gate green (203 tests, ruff check/format, mypy, cli.py zero diff, non-TTY byte-identical, no dead Rich code). Archive-ready.

*Verification was executed read-only: no source files modified. Working tree clean except untracked `openspec/changes/` (repo convention — openspec artifacts are never committed).*
