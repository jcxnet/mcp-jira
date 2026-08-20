# Tasks: Textual widget TUI for `mcp-jira setup` and `mcp-jira install`

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~1,975 authored (+~200 generated `uv.lock`) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | 5 chained PRs (below) |
| Delivery strategy | auto-chain (session preflight) |
| Chain strategy | pending — user must pick feature-branch-chain vs stacked-to-main |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: pending
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Deps + full `tui.py` (new module, unwired) | PR 1 | `uv run pytest` (existing suite green; module unreachable) + `uv run mypy -p mcp_jira` | N/A — no behavior change; `uv run python -c "from mcp_jira import tui"` import smoke | `git revert` PR 1; lock restores, module gone, wizard/installer untouched |
| 2 | Wizard wiring: wrapper + test_wizard rewrite + ui.py + test_rich_adapters.py delete | PR 2 | `uv run pytest tests/test_wizard.py` | Non-TTY: `uv run mcp-jira setup </dev/null` prints path, exits 1 | `git revert` PR 1–2 → rich baseline intact |
| 3 | Installer wiring: wrapper (+`_collect_pending`/`_resolve_targets`) + test_installer rewrite | PR 3 | `uv run pytest tests/test_installer.py` | Non-TTY: `uv run mcp-jira install </dev/null` prints guidance, exits 1 | `git revert` PR 1–3 |
| 4 | SetupApp Pilot suite | PR 4 | `uv run pytest tests/test_tui_setup.py` | Headless Pilot is the harness (`run_test`, no TTY); manual TTY smoke out-of-band | `git revert` PR 4 (tests only) |
| 5 | InstallApp Pilot suite | PR 5 | `uv run pytest tests/test_tui_install.py` | Same as unit 4 | `git revert` PR 5 (tests only) |

## Phase 1: Dependencies (PR 1)

- [x] **1.1** pyproject.toml: `dependencies` += `textual>=8.2,<9`; dev += `pytest-asyncio`; `[tool.pytest.ini_options]` += `asyncio_mode = "auto"`. **Deps**: none. **AC**: D-DEP; async Pilot tests runnable. **Lines**: ~3.
- [x] **1.2** `uv lock && uv sync`; verify exactly 5 net-new runtime entries (textual, mdit-py-plugins, platformdirs, linkify-it-py, uc-micro-py) + pytest-asyncio. **Deps**: 1.1. **AC**: D-DEP lock delta. **Lines**: ~0 (+~200 generated).

## Phase 2: tui.py module (PR 1)

- [x] **2.1** `_AbortMixin`: priority bindings `Binding("ctrl+c"|"ctrl+q", "abort", priority=True, show=False)`; `action_abort()` → `self.exit(1)` on every screen. **Deps**: 1.2. **AC**: tui-abort-binding both scenarios; §Ctrl-C aborts cleanly. **Lines**: ~30.
- [x] **2.2** Shared `ConfirmModal(Screen[bool])` (Write/Cancel → `dismiss(bool)`; never shows PAT/contents) + `ResultScreen` (OK → `app.exit(0|1)`). **Deps**: 2.1. **AC**: §Setup wizard summary; §install confirm-before-write. **Lines**: ~65.
- [x] **2.3** `SetupApp.compose` + validation: `Input#url`, `Input#pat(password=True)`, `Select#language` (en default), `Switch#read_only` (false), `Static#connectivity_error`, `LoadingIndicator`, `Button#continue`; blank → `_REQUIRED_MSG` stay; `!_valid_url` → Invalid URL stay; `/myself` never called on invalid. **Deps**: 2.1. **AC**: §Setup wizard; §Invalid URL rejected. **Lines**: ~130.
- [x] **2.4** Worker: `@work(thread=True) check_connectivity` — `JiraClient(url, pat, transport).request("GET", "/rest/api/2/myself")`; `call_from_thread` guarded by `get_current_worker().is_cancelled`; ok → confirm step enabled, fail → styled error, stay on form. **Deps**: 2.3. **AC**: connectivity-worker both scenarios (loading indicator, no UI freeze). **Lines**: ~70.
- [x] **2.5** SetupApp confirm→write: ConfirmModal (URL/language/read_only/path, never PAT) → `_write_config` 0600 → ResultScreen exit 0; decline/abort exit 1, nothing written. **Deps**: 2.4, 2.2. **AC**: §Interactive success; §Confirmation declined; §Optional defaults. **Lines**: ~90.
- [x] **2.6** `InstallApp.compose`: `SelectionList` (3 `_TARGETS`, `add_option((label, id, True))`), inline `Static` notices, `Button#continue`; `_resolve_targets(selected, _IDS)` empty→all, dedupe, order-preserving. **Deps**: 2.1. **AC**: §install SelectionList; §Default selection is all. **Lines**: ~90.
- [x] **2.7** InstallApp collect+write: `_collect_pending` (load_json/upsert_client; corrupt → notice, skip, untouched; already-registered → notice, skip) → ConfirmModal (paths only) → per-path `write_with_backup` → ResultScreen exit 0/1. **Deps**: 2.6, 2.2. **AC**: §Interactive install; write-safety/idempotency preserved; §Ctrl-C. **Lines**: ~90.

## Phase 3: Wrappers + dead-code removal (PR 2–3)

- [x] **3.1** wizard.py: drop rich/ui imports + 4 `_rich_*`; extract `_write_config()` (os.open 0600 + chmod, 4 keys); `run_wizard(*, config_path, interactive, transport)` → TTY-gated wrapper — non-TTY prints path+`_GUIDANCE`, returns 1 byte-identical; else `SetupApp(config_path, transport).run()`. **Deps**: 2.5. **AC**: §Non-interactive without config; §Wizard testability; cli.py zero diff. **Lines**: ~185.
- [x] **3.2** installer.py: drop rich/ui + `_select_targets`/`_selection_prompt` + 2 `_rich_*`; extract `_collect_pending()`; add `_resolve_targets()`; `run_installer(*, interactive, config_paths)` → wrapper, non-TTY guidance exit 1. **Deps**: 2.7. **AC**: §Non-TTY guidance; §Testability pure functions incl. `_resolve_targets`. **Lines**: ~215.
- [x] **3.3** Delete `ui.py` + `tests/test_rich_adapters.py`; grep proves no remaining `mcp_jira.ui`/`rich.prompt` imports in src or tests. **Deps**: 3.1, 3.2. **AC**: D-DEAD; suite green. **Lines**: ~164 deleted.

## Phase 4: Tests (PR 2–5)

- [x] **4.1** test_wizard.py rewrite: keep `test_non_interactive_prints_path_and_exits_nonzero` (byte-identical); delete 8 flow tests; add `_write_config` unit tests (0600 + 4 keys). **Deps**: 3.1. **AC**: §Wizard testability — non-TTY/write semantics covered by unit tests unchanged. **Lines**: ~233 diff.
- [x] **4.2** test_installer.py: keep non-TTY + 11 pure tests unchanged; delete 6 flow tests; add `_resolve_targets` unit tests (empty→all, dedupe, order). **Deps**: 3.2. **AC**: §Testability injectable temp-dir scenario; pure-function suite unaffected. **Lines**: ~130 diff.
- [x] **4.3** test_tui_setup.py (new, Pilot): success 0600+4 keys; defaults en/false; es+read_only true; invalid URL → error, `/myself` never called, no file; blank → required error; 401 → styled error, stays, no file; confirm declined → existing file untouched, exit 1; ctrl+c on input → exit 1, no file; ctrl+c on modal → exit 1; ctrl+q → exit 1. `run_test(headless=True, size=(80,24))`, injected transport/config_path. **Deps**: 2.5, 2.2. **AC**: all §Setup wizard + tui-abort-binding + connectivity-worker scenarios; §Wizard testability Pilot scenario. **Lines**: ~300.
- [x] **4.4** test_tui_install.py (new, Pilot): success merges all (modes, `.bak`); default all; subset only selected; already-registered notices, nothing rewritten; corrupt skipped+untouched; confirm declined → nothing written; ctrl+c → nothing written. **Deps**: 2.7, 2.2. **AC**: all §install subcommand + §Testability Pilot scenarios. **Lines**: ~180.

## Phase 5: Docs / archive readiness (PR 5)

- [x] **5.1** Docs/comments: drop Rich-prompt wording in wizard/installer module docstrings; confirm open questions — ctrl+q footer hidden (`show=False` from 2.1), `_resolve_targets` rename already synced into client-installer §Testability prose (no spec touch-up needed). **Deps**: 3.1, 3.2. **AC**: docs match delta specs; archive-ready. **Lines**: ~30.
- [x] **5.2** Final gate: `uv run ruff check && uv run ruff format --check && uv run mypy -p mcp_jira && uv run pytest` green (~191 existing + ~21 new); `test_cli.py` 6/6 unmodified; `git diff cli.py` empty; lock delta = 5 runtime + pytest-asyncio only. **Deps**: all. **AC**: proposal §Success Criteria. **Lines**: 0.
