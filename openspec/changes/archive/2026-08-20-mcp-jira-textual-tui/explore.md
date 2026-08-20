# Exploration: Convert `mcp-jira setup` / `mcp-jira install` to a Textual widget TUI

Status: **success** — change `mcp-jira-textual-tui`, artifact store `hybrid` (openspec file + engram).

## Current State

`mcp-jira setup` (`src/mcp_jira/wizard.py:run_wizard`) and `mcp-jira install`
(`src/mcp_jira/installer.py:run_installer`) are form-style loops styled with
Rich line prompts (`rich.prompt.Prompt/Confirm`). Both follow the same shape:

- `_is_interactive()` gate (stdin+stdout TTY); non-TTY → plain `print()` guidance + exit 1 (AC-US-9, client-installer §Non-TTY guidance).
- Injectable `prompt`/`hidden_prompt`/`select`/`confirm` (wizard) and `targets_selected`/`confirm` (installer) lambdas defaulting to Rich adapters (`_rich_*` in each module), plus `transport` (wizard) / `config_paths` (installer) — the load-bearing test seam: tests run without a TTY and without live Jira.
- Nothing is written unless connectivity succeeds (wizard `/myself` via `JiraClient`) AND the user confirms; `^C` → "Aborted." + exit 1, nothing written (AC-US-9, §Ctrl-C).
- Wizard writes `~/.config/mcp-jira/config.json` with 0600 (`os.open`+`os.chmod`). Installer merges `mcp-jira` into OpenCode global / Claude CLI user / Claude Desktop configs with `.bak` once, atomic `os.replace`, post-write JSON re-parse + restore (client-installer §Write safety).
- `src/mcp_jira/ui.py` holds shared Rich consoles; `src/mcp_jira/cli.py` dispatches via argparse, `main()` returns the exit code from `run_wizard()`/`run_installer()`.

The user has now reversed the earlier decision (config-tui proposal: "form-style loop, NOT a widget TUI; not re-negotiable") and explicitly wants a **real widget TUI built with Textual** for both flows. The prior rejection reasons (config-tui explore.md) were: heavy dep tree, event loop for a 4-field form, harder to test. Two of those three are now measurably weaker (below); the user's explicit preference overrides the rest.

## Dependency Cost (verified against PyPI, 2026-08-20)

Textual current: **8.2.8**, `requires-python = "<4.0,>=3.9"` — compatible with the project's `requires-python = ">=3.10"` and the 3.14.7 runtime venv. All deps pure-Python; compiled tree-sitter bindings only under the `[syntax]` extra, which we do NOT need.

Runtime deps of `textual`:
- `markdown-it-py[linkify]>=2.1.0` → pulls `linkify-it-py` + `uc-micro-py`
- `mdit-py-plugins` (**net-new**)
- `platformdirs<5,>=3.6.0` (**net-new**)
- `pygments<3,>=2.19.2` — already in lock (via rich)
- `rich>=14.2.0` — **already satisfied**: lock pins rich **15.0.0** today (rich became a runtime dep in the archived rich-tui change). No rich upgrade needed.
- `typing-extensions` — already in lock

Already-present transitive companions that the old exploration worried about: `click` is already in the lock (via `mcp`); `markdown-it-py`, `mdurl`, `pygments` already present.

**Net-new lock entries: exactly 5 — `textual`, `mdit-py-plugins`, `platformdirs`, `linkify-it-py`, `uc-micro-py`** (all pure-Python, no wheels with native code for the base install). This matches the old "+5 packages" count, but the "heavy" framing is stale: the largest pieces (rich, click, markdown-it-py) are already runtime deps today.

Pin recommendation for the proposal: `textual>=8.2,<9` in `pyproject.toml` `dependencies`; `pytest-asyncio` added to `[dependency-groups] dev` (Textual's `run_test` is async — see Testing below).

## Affected Areas

- `src/mcp_jira/wizard.py` — logic functions stay (URL/language/read_only parsing, 0600 write); the lambda-driven prompting shell is replaced by a Textual App. `run_wizard()` keeps its name + non-TTY gate + int-return contract (cli.py wiring survives).
- `src/mcp_jira/installer.py` — pure functions stay (`load_json`, `upsert_client`, `write_with_backup`, `probe_desktop_dir`, `_select_targets` parser); the prompting shell becomes a Textual App. `run_installer()` keeps name + non-TTY gate + int return.
- `src/mcp_jira/tui.py` — **NEW**: `SetupApp` + `InstallApp` (or one module per flow) plus shared bits (abort binding, confirm modal, result screen, footer).
- `src/mcp_jira/ui.py` — Rich consoles become unused inside the TUI (the app renders its own widgets); likely deleted along with the `_rich_*` adapters. Non-TTY branches stay plain `print()`.
- `src/mcp_jira/cli.py` — minimal or zero change (run_wizard/run_installer names and signatures kept).
- `pyproject.toml` / `uv.lock` — +`textual>=8.2,<9` (runtime), +`pytest-asyncio` (dev).
- `tests/` — see Testing; ~23 existing tests break/are removed, ~170 survive, new Pilot-driven tests added.
- `openspec/specs/server-config/spec.md` + `openspec/specs/client-installer/spec.md` — **MUST be MODIFIED** (see Scope).

## Approaches

1. **One Textual App per flow, in separate modules** (`setup_app.py`, `install_app.py`), logic functions folded in.
   - Pros: each flow fully self-contained; no cross-flow coupling.
   - Cons: duplicates the shared chrome (abort binding, confirm modal, result screen, footer) across two modules; the two flows genuinely share only that small set — the form/check/write and select/merge/write cores differ.
   - Effort: High (more boilerplate than needed).

2. **Shared form-widget library + two thin apps** — a reusable widget/module layer, apps composed from it.
   - Pros: maximally DRY.
   - Cons: premature abstraction: the shared surface is ~4 small pieces; a "library" abstraction for them is over-engineering, and the flows' actual form logic (URL validation vs client multi-select) shares nothing. Risk of a widget layer nobody else consumes.
   - Effort: Medium-High.

3. **Keep the logic functions in `wizard.py`/`installer.py`; wrap only the prompting in Textual** (recommended) — a single new `tui.py` with `SetupApp`/`InstallApp` + small shared helpers; `run_wizard()`/`run_installer()` become thin TTY-gated wrappers that instantiate and run the app and return its exit code.
   - Pros:
     - Every security-relevant line stays put: URL/pat validation, `/myself` check, 0600 write, `.bak`+atomic write+re-parse, non-TTY gate. The TUI is a new *presentation shell*, not a reimplementation — the same reasoning that drove the rich-tui change (style the interactive branch only).
     - `run_wizard`/`run_installer` names + int-return survive → `cli.py` untouched, `test_cli.py` dispatch tests pass unmodified.
     - Pure logic stays unit-testable without Textual (parser, write/merge helpers) — the lazy-correct split.
     - The injectable lambda contract dies (see Testing), but the *behavior* it drove is preserved as plain functions + widget events.
   - Cons: two layers (logic + app) — but that layering already exists today (logic + prompt lambdas); Textual simply replaces the lambda layer. The spec's "existing tests pass unmodified" scenario cannot survive in any of the three options.
   - Effort: Medium.

**Recommendation: Approach 3**, with Approach 2's shared bits taken lightly: one `tui.py` module holding both App classes and ~3 shared helpers (abort binding, confirm modal, result screen). The wizard keeps a `transport` and `config_path` injection point on the App; the installer keeps `config_paths` on the App, so headless tests keep the "no TTY, no live Jira, tmp paths" property.

## Textual Testing (App.run_test / Pilot) and Test Impact

- `App.run_test(headless=True, size=(80,24))` is an **async context manager** yielding a `Pilot` that drives the app like a user: `pilot.click("#id")`, `pilot.press("tab")`, `await pilot.pause()`, and direct widget value setting (`app.query_one("#url").value = ...`). Headless = no terminal output, so it runs in CI without a TTY.
- The project's pytest is sync → need `pytest-asyncio` (new dev dep) for `async def` tests, or wrap each driver in `asyncio.run(...)` from a sync test. Pilot tests + `httpx.MockTransport` (existing `conftest.MockRouter`) keep the "deterministic without live Jira" property.
- The `transport`/`config_path`/`config_paths` injection points move from function kwargs to App constructor kwargs — the test seam survives, its shape changes.

**Breaking tests (counted against the current 193):**

| File | Total | Break | Why |
|---|---|---|---|
| `tests/test_wizard.py` | 9 | 8 | `run_wizard(interactive=True, prompt=…, hidden_prompt=…, select=…, confirm=…)` — injectable lambdas replaced by Pilot-driven widgets. Survives: `test_non_interactive_prints_path_and_exits_nonzero` (non-TTY gate kept). |
| `tests/test_installer.py` | 18 | 6 | Flow tests injecting `targets_selected`/`confirm` (`merges_all`, `idempotent_rerun`, `select_subset`, `ctrl_c`, `declined`, `corrupt_skipped`). Survive: `non_interactive` + all 11 pure-function tests (`load_json`, `upsert_client`, `write_with_backup` ×4, `probe_desktop_dir` ×3). |
| `tests/test_rich_adapters.py` | 9 | 9 | Tests the `_rich_*` adapters directly; adapters are deleted with the Rich prompt layer. |
| `tests/test_cli.py` | 6 | 0 | `run_wizard`/`run_installer` names + int-return kept; monkeypatched dispatch tests unchanged. |

→ **~23 tests break/removed, ~170 survive unmodified** (the installer's merge/backup/validate unit tests are the safety net and stay green), plus **new Pilot-driven tests** for both apps (success path, invalid URL re-prompt, decline-abort, ^C-abort, connectivity failure, non-TTY). Rough new-test budget: 15–20.

## Scope Boundaries

- **In scope**: Textual TUI for `mcp-jira setup` and `mcp-jira install` only. Spec deltas are REQUIRED and must MODIFY:
  - `server-config` §Setup wizard (interactive path is now a widget TUI) and §Wizard testability — the "existing four wizard tests MUST pass unmodified" scenario cannot hold; it becomes "wizard behavior is driven via Pilot, non-TTY gate and write semantics unchanged". The behavioral scenarios (Interactive success, Invalid URL, Confirmation declined, Ctrl-C, Connectivity failure, Non-interactive) all remain valid — only the testability requirement changes.
  - `client-installer` §install subcommand ("form-style multi-select" → widget multi-select) and §Testability ("existing suite MUST pass unmodified" → Pilot-driven, pure-function unit tests unchanged).
  - Non-TTY behavior (both), hidden-PAT, `/myself`-failure → nothing written, 0600 write, `.bak`/atomic write/re-parse, "already registered" idempotency: **MUST be preserved unchanged** — these are the constraint anchors; the delta spec must restate them.
- **Out of scope (recommended keep)**: config *editing* (no `edit` subcommand) — the prior non-goal stands; nothing in the user's reversal suggests editing, and the server reads a file, not a DB. Also out: themes beyond defaults, multi-profile, Jira data browsing, the `[syntax]` extra. PRD §2.4's "no admin/UI dashboard — configuration is file-based" is NOT violated: this is a creation/registration form; the delta spec should state that the config remains file-based and the TUI only replaces the interactive prompt loop.

## Interaction Design Sketch (minimal, per flow)

Shared chrome (both apps): `Header` + `Footer`; default Textual focus traversal `Tab`/`Shift+Tab`; arrows work inside `Select` overlay and multi-select; **explicit abort binding** (`q` / `ctrl+q`, and a priority `ctrl+c` binding — see Risks) that exits 1 with nothing written, mirroring today's "Aborted."

**SetupApp** (4-field form, single screen + 2 overlays):
1. Form: `Input#url` (placeholder `https://jira.example.com`), `Input#pat(password=True)` — Textual's `Input` has a `password` param that masks content (verified in 8.x API docs), `Select#language` (en/es, default en), `Switch#read_only` (or `Checkbox`; default off), `Button#continue` ("Check connectivity").
2. Connectivity: `/myself` runs in a Textual worker (`@work(thread=True)` — httpx is sync; never block the UI thread); `LoadingIndicator` while in flight; error → red `Static` notice, stay on the form, nothing written.
3. Confirm: push a `ModalScreen` (summary: URL, language, read_only, target path; `Write`/`Cancel` buttons — matches the existing `Panel` summary + confirm step).
4. Write: reuse the existing 0600 `os.open`+`os.chmod` helper; result screen ("Config written … (mode 600)") → `exit(0)`; decline/abort → "Aborted; nothing was written." → `exit(1)`.

**InstallApp** (client selection + merge):
1. Selection: `SelectionList` (or `Checkbox`es) over the 3 `_TARGETS` with "default all" pre-checked (preserves the empty→all default); `Button#continue`.
2. Per-client load/upsert runs the existing pure functions (`load_json`/`upsert_client`); "already registered" and corrupt-skip notices shown inline (existing semantics).
3. Confirm: summary `ModalScreen` listing paths (never contents — secrets rule), `Write`/`Cancel`.
4. Write: existing `write_with_backup` per path; success/failure result screen; exit 0/1.

## Risks

1. **^C semantics change (HIGH — spec impact).** Textual 8.x: app-level `ctrl+c` no longer quits — it shows "Press ctrl+q to quit" (verified in `textual.app.action_help_quit` source); inside an `Input`, `ctrl+c` is bound to *copy*. AC-US-9 / §Ctrl-C ("^C at any prompt MUST abort cleanly with non-zero exit and nothing written") therefore needs a deliberate app-level **priority binding** `ctrl+c → action_abort` (exit 1, nothing written) plus `q`/`ctrl+q`. This is a design decision the proposal must state; test it via Pilot (`pilot.press("ctrl+c")`).
2. **Event loop / blocking I/O.** The `/myself` check must run in a worker (`@work(thread=True)`) — calling sync httpx on the UI thread freezes the app. Existing `JiraClient` is sync; keep it, wrap the call.
3. **~23 tests break + spec testability requirements must be MODIFIED.** Not cosmetic: `server-config` §Wizard testability and `client-installer` §Testability currently assert "existing suite passes unmodified" — the delta spec MUST change those scenarios (Pilot-driven) or verify fails. The installer's 11 pure-function safety tests and the non-TTY tests survive untouched.
4. **pytest-asyncio (new dev dep) + async tests** — new test style for this repo; keep sync wrappers (`asyncio.run`) where possible to minimize churn. Textual `run_test` is stable but version-locked to `>=8.2,<9`.
5. **Non-TTY / CI environment** — `App.run()` requires a TTY; the preserved `_is_interactive()` gate means Textual never launches in CI/pipes (existing non-TTY tests prove the branch). `run_test(headless=True)` is the CI path. `NO_COLOR`/`TERM=dumb`: Textual respects `NO_COLOR`; not a concern for headless tests.
6. **Rich console `ui.py` removal** — the Rich consoles become dead inside the TUI; delete `ui.py` + `_rich_*` adapters (and their 9 tests) in the same commit to avoid dead code, but keep plain `print()` in non-TTY branches byte-identical (existing tests assert on those strings).
7. **uv.lock churn** — 5 net-new pure-Python packages; no compiled wheels, no rich upgrade (already 15.0.0 ≥ 14.2). Low.
8. **Scope creep toward config editing** — the change name invites it; keep `edit` a non-goal in the proposal.

## Ready for Proposal

**Yes.** Recommendation: Approach 3 — keep the logic/write/merge functions in `wizard.py`/`installer.py` untouched, add `tui.py` with `SetupApp`/`InstallApp` + shared abort/confirm/result helpers, keep `run_wizard()`/`run_installer()` as TTY-gated wrappers returning int (cli.py unchanged), add `textual>=8.2,<9` + `pytest-asyncio`, rewrite ~23 tests as Pilot-driven, and MODIFY the two testability requirements in the delta spec. Non-TTY behavior, hidden PAT, `/myself`-gated writes, 0600, `.bak`/atomic writes, and idempotency MUST be restated unchanged. Config editing stays a non-goal.

Tell the user: the "heavy dependency tree" objection is mostly stale — rich 15 and click are already runtime deps, so Textual adds exactly 5 pure-Python packages; the real costs are (a) ~23 test rewrites to Pilot-style and (b) a spec change to the two "existing tests pass unmodified" requirements, plus (c) a deliberate ^C handling decision because Textual 8 changed ^C from quit to copy/notice.