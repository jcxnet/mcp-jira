# Tasks: Rich styling for `mcp-jira setup` and `mcp-jira install`

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~320 authored (+~200 generated `uv.lock`) |
| 400-line budget risk | Medium |
| 800-line session budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | auto-chain |
| Chain strategy | pending |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: pending
400-line budget risk: Medium

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | All phases: dep, ui.py, wizard, installer, tests | Single PR | `uv run pytest tests/test_rich_adapters.py` | Manual full-TTY smoke `uv run mcp-jira setup` and `install` (out-of-band; no pexpect) | `git revert` + drop `rich` from `pyproject.toml`; no persisted state |

## Phase 1: Foundation

- [x] 1.1 Add `"rich>=13.7"` to `[project] dependencies` in `pyproject.toml`.
- [x] 1.2 Run `uv lock`; commit regenerated `uv.lock` (rich, markdown-it-py, mdurl; pygments 2.21.0 promoted from dev).
- [x] 1.3 Create `src/mcp_jira/ui.py`: `console = Console(highlight=False)` and `error_console = Console(stderr=True, highlight=False)` (D1/D2). `src/mcp_jira/cli.py` stays unchanged.

## Phase 2: Wizard wiring (`src/mcp_jira/wizard.py`)

- [x] 2.1 Add `_rich_prompt`, `_rich_hidden`, `_rich_select`, `_rich_confirm` per design signatures: `escape()` every interpolated value; `Confirm.ask` adapted to `"y"`/`"n"` (D4/D6).
- [x] 2.2 Swap `run_wizard` defaults to the `_rich_*` adapters; injectable signatures stay byte-identical (D3).
- [x] 2.3 Route errors to `error_console` `style="bold red"`: required, Invalid URL, Invalid language, Invalid answer, Connection failed, Aborted (D6).
- [x] 2.4 Wrap the `/myself` request in `console.status(...)` spinner; replace summary `print` with `console.print(Panel(...))` before write confirmation.
- [x] 2.5 Green `Config written to {path}` success and styled `Aborted; nothing was written.`; `escape()` the path.
- [x] 2.6 Keep non-TTY branch byte-identical plain `print()`; no Console call before the interactive branch (D8).

## Phase 3: Installer wiring (`src/mcp_jira/installer.py`)

- [x] 3.1 Add `_rich_targets_selected` (`Prompt.ask`, no `choices=`, default `""` — D5) and `_rich_confirm` (`Confirm.ask(default=False)` → `"y"`/`"n"`).
- [x] 3.2 Swap `run_installer` defaults; `targets_selected` keeps `| None` default; `_select_targets` loop stays authoritative (empty→all, dedupe, invalid→re-prompt).
- [x] 3.3 Route errors to `error_console` bold red: Invalid selection, not valid JSON skip, Failed to write, Aborted.
- [x] 3.4 `Panel` summary of pending configs; `Nothing to register.` and `already registered` skips to `console`; green per-path `Registered mcp-jira in {path}` (escape).
- [x] 3.5 Keep non-TTY branch byte-identical plain `print()`.

## Phase 4: Tests & verification

- [x] 4.1 Create `tests/test_rich_adapters.py`: monkeypatch `Confirm.ask` → True/False; assert `"y"`/`"n"` returned and `default` forwarded (wizard + installer adapters).
- [x] 4.2 Assert `escape()` keeps load-bearing prompt `"Write config"` intact and renders `[` as `\[`.
- [x] 4.3 Assert markup safety: invalid URL containing `[` keeps the bracket in stderr output.
- [x] 4.4 `uv run pytest` — existing 184 tests pass unmodified; load-bearing substrings intact.
- [x] 4.5 `uv run ruff check`, `uv run ruff format --check`, `uv run mypy mcp_jira` — all clean.

> **Apply note (mypy)**: the documented bare-module form `uv run mypy mcp_jira` is not runnable on the
> resolved mypy (module names as bare CLI args are no longer accepted; they resolve as file paths and
> fail with "Cannot read file"). The equivalent `uv run mypy -p mcp_jira` is clean (verified).
> `[tool.mypy] mypy_path = "src"` was added so module resolution is deterministic.
> **Apply note (ruff format)**: ruff 0.16 formats fenced Python in `openspec/**/*.md`; the design docs
> were flagged as unformatted before this change (pre-existing tool drift). `[tool.ruff] exclude =
> ["openspec"]` scopes both check and format to code.
