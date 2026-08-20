# Design: Rich styling for setup wizard and install installer

## Technical Approach

Style only the interactive (TTY) branches of `run_wizard`/`run_installer`: a shared Rich `Console` pair in new `src/mcp_jira/ui.py`, Rich `Prompt`/`Confirm` defaults behind the **byte-identical** injectable signatures, styled errors on stderr, `Panel` summary, `/myself` spinner, installer summary. Non-TTY branch and write semantics untouched. Pure implementation: no delta specs (no scenario asserts output text).

## Architecture Decisions

| # | Option | Tradeoff | Decision |
|---|--------|----------|----------|
| D1 | Shared Console location | `cli.py` module-level → import cycle (cli imports `run_wizard`/`run_installer`; they'd import back). Per-run factory → signature change (forbidden). New `ui.py` → tiny, cycle-free | **New `src/mcp_jira/ui.py`**: `console = Console(highlight=False)`, `error_console = Console(stderr=True, highlight=False)` |
| D2 | One vs two consoles | `Console(stderr=True)` would route summaries/success to stderr, breaking `capsys.out` assertions (`"Config written"`); `Console.print` has no per-call stream switch | **Two module-level consoles**; errors → `error_console`, everything else → `console` |
| D3 | Prompt adapter placement | Inline lambdas in signatures (unreadable, untestable); shared helper module (two near-identical shapes, low value) | **Module-level private `_rich_*` functions in each file**, used as signature defaults; each file keeps its own contract shape |
| D4 | `Confirm` bool→str | Raw bool breaks `(str,bool)->str` / `(str)->str` contracts | Adapter returns `"y"`/`"n"` only; loops treat `"n"` ≡ `""` (verified). Installer forces `default=False` so Enter still = decline |
| D5 | Installer multi-select | Rich has no non-Textual multi-select; `choices=` would reject `"1,3"` | Free-text `Prompt.ask` default; `_select_targets` loop stays authoritative (empty→all, dedupe, invalid→styled re-prompt) |
| D6 | Markup safety | `markup=False`-console + `escape()` double-processes backslashes; Panel content ignores per-call flags | Consoles keep `markup=True`; **`escape()` every interpolated value** (url/path/repr/exc) at prompt adapters, error prints, Panel content. Static text needs nothing |
| D7 | Delta specs | Styling changes no behavior; `server-config`/`client-installer` requirements and scenarios stay fully satisfied | **No delta specs**; main specs untouched |
| D8 | Non-TTY branch | Console on non-interactive path could leak ANSI into piped output (tests assert on it directly) | No Console call before the `interactive` branch; non-TTY output byte-identical |

## Data Flow

```
run_wizard(interactive)                         run_installer(interactive)
  prompt → hidden_prompt → select → confirm      targets_selected → _select_targets (parse)
  console.status: GET /myself ──JiraClient──►    load/upsert → Panel summary → confirm
  Panel summary → confirm → write 0600           write_with_backup per path (green per-path success)
  green "Config written"                         ^C / decline → error_console "Aborted" (exit 1)
  ^C → error_console "Aborted" (exit 1)
```

Styled errors (`Invalid URL`, `Connection failed`, `Invalid language`, `required`, `Aborted`, `not valid JSON`, `Failed to write`, `Invalid selection`) → `error_console`, `style="bold red"`.

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/mcp_jira/ui.py` | Create | `console` + `error_console` singletons (D1/D2) |
| `src/mcp_jira/wizard.py` | Modify | 4 `_rich_*` defaults; style 9 output sites; `/myself` spinner; Panel summary; `escape()` interpolations |
| `src/mcp_jira/installer.py` | Modify | 2 `_rich_*` defaults; style 9 output sites; Panel summary |
| `pyproject.toml` | Modify | `dependencies` += `rich>=13.7` |
| `uv.lock` | Modify | `uv lock` (rich, markdown-it-py, mdurl; pygments 2.21.0 promoted from dev) |
| `tests/test_rich_adapters.py` | Create | Adapter + markup-safety tests (below) |
| `src/mcp_jira/cli.py` | Unchanged | Console moved to `ui.py` to avoid D1 cycle; cli has no interactive output |

## Interfaces / Contracts

Signatures stay byte-identical; only defaults change:

```python
# wizard.py — defaults only
prompt:       Callable[[str], str] = _rich_prompt        # Prompt.ask(escape(p))
hidden_prompt:Callable[[str], str] = _rich_hidden        # Prompt.ask(escape(p), password=True)
select:       Callable[[str, Sequence[str], str], str] = _rich_select   # Prompt.ask(escape(p), choices=list(o), default=d, show_choices=True)
confirm:      Callable[[str, bool], str] = _rich_confirm # "y" if Confirm.ask(escape(p), default=d) else "n"
# installer.py
targets_selected: Callable[[str, Sequence[str], str], str] | None = None  # → Prompt.ask(escape(p), default=d)
confirm:          Callable[[str], str] = _rich_confirm   # "y" if Confirm.ask(escape(p), default=False) else "n"
```

Wizard loops (URL, language, read_only) and `_select_targets` remain fallback validators for injected callables; Rich's inline re-prompt supersedes them only for defaults. Prompt strings unchanged — `"Write config"`, `"Read-only mode?…"` are load-bearing and escape-transparent (bracket-free).

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `_rich_confirm` bool→str (wizard + installer) | monkeypatch `Confirm.ask` → True/False; assert `"y"`/`"n"` + `default` forwarded |
| Unit | escape() keeps load-bearing prompts | prompt passed to `Confirm.ask` retains `"Write config"`; `[` input → `\[` |
| Unit | Output markup safety | invalid URL containing `[` → bracket preserved in stderr |
| Regression | Existing 184 tests | Unmodified; capsys no-ANSI verified empirically (exploration) |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary (installer writes JSON config files; registered command values are data, unchanged, never executed).

## Migration / Rollout

No migration. `uv lock` regenerates `uv.lock` in the apply commit. Rollback: revert the commit and drop `rich` from `pyproject.toml`.

## Open Questions

- None.
