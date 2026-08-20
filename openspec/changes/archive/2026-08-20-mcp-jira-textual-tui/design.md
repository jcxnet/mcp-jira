# Design: Textual widget TUI for `mcp-jira setup` and `mcp-jira install`

## Technical Approach

Exploration Approach 3: keep every logic/write/merge/security line in `wizard.py`/`installer.py`; replace the injectable-lambda prompting shell with two Textual Apps in a new `src/mcp_jira/tui.py` (`SetupApp`, `InstallApp`) plus shared helpers. `run_wizard()`/`run_installer()` become TTY-gated wrappers that instantiate the app and return its exit code — `cli.py` and both non-TTY branches stay byte-identical. Two verbatim extractions so the Apps can call the logic and unit tests keep covering it: the wizard's inline 0600 write → `_write_config()`, the installer's inline pending-collection loop → `_collect_pending()`. Satisfies `server-config` §Setup wizard + tui-abort-binding + connectivity-worker and `client-installer` §install subcommand + Testability.

## Architecture Decisions

| # | Option | Tradeoff | Decision |
|---|--------|----------|----------|
| D-^C | `^C` handling | Textual 8: `ctrl+c` = copy inside `Input`, "press ctrl+q to quit" notice elsewhere; base `quit` exits with `None`, breaking the int contract | Shared `_AbortMixin` with priority bindings `Binding("ctrl+c", "abort", priority=True)` and `Binding("ctrl+q", "abort", priority=True)`; `action_abort()` → `self.exit(1)`. Priority bindings are checked before focused-widget bindings, so Input's copy binding cannot shadow. Every exit path returns an int |
| D-TTY | Textual on non-TTY | `App.run()` needs a TTY; CI/pipes must never launch it | Keep `_is_interactive()` gate + `interactive` kwarg; wrapper prints guidance + returns 1 before app construction; non-TTY branch byte-identical |
| D-WORKER | `/myself` sync call | Sync httpx on the UI thread freezes the app | `@work(thread=True)`; result pushed back via `self.call_from_thread(...)`, guarded by `get_current_worker().is_cancelled`; `LoadingIndicator` while in flight |
| D-TEST | Async tests | `run_test` is an async context manager; repo pytest is sync | `pytest-asyncio` dev dep with `asyncio_mode = "auto"`; Pilot drives both apps headless |
| D-DEAD | `ui.py` + `_rich_*` | Rich consoles are dead inside the TUI | Delete `ui.py`, all `_rich_*` adapters, `_select_targets` parser + `test_rich_adapters.py` (9). Grep confirms only wizard/installer/tests import `ui`/`rich.prompt` |
| D-DEP | Dependencies | Textual pulls 5 pure-Python runtime packages | `textual>=8.2,<9` runtime; `pytest-asyncio` dev; `uv lock` → exactly 5 net-new runtime entries (textual, mdit-py-plugins, platformdirs, linkify-it-py, uc-micro-py) + pytest-asyncio |
| D-SEL | `_select_targets` | Prompt-driven comma parser dies with the lambda shell; client-installer §Testability prose lists it | Replace with pure `_resolve_targets(selected, _IDS)`: empty→all, dedupe, order-preserving (same semantics). No existing test covers `_select_targets` directly; add unit tests for `_resolve_targets`. Spec-prose name flagged in Open Questions |
| D-WRAP | Wrapper signatures | Surviving tests need `config_path`/`interactive`; Pilot injects on the App | `run_wizard(*, config_path, interactive, transport)` / `run_installer(*, interactive, config_paths)`; Apps take `transport`/`config_path`/`config_paths` via constructor |

## Data Flow

```
SetupApp                                  InstallApp
url/pat/lang/read_only form              SelectionList (all pre-checked)
  │ Continue → validate                    │ Continue
  │  blank → _REQUIRED_MSG (stay)          ├─ _resolve_targets (empty→all)
  │  !_valid_url → Invalid URL (stay)      ├─ _collect_pending: load_json/upsert_client
  │  /myself NEVER called                  │   corrupt → notice, skip, untouched
  ▼                                        │   already-registered → notice, skip
worker @work(thread=True): JiraClient      │   → (pending, notices) inline
  GET /rest/api/2/myself                   ▼
  ──call_from_thread──► ok: ConfirmModal   pending empty → exit(0) "Nothing to register"
        │                 (URL, lang,      ConfirmModal (paths only, never contents)
        │                  read_only,      │ Write → write_with_backup per path
        │                  config path)    ▼
        └─ fail: styled Static error,      ResultScreen per-path result → exit(0/1)
           stay on form, nothing written   decline/^C → exit(1)
  ConfirmModal → Write → _write_config
  (0600 os.open+chmod) → ResultScreen
  → exit(0)   decline/^C → exit(1)
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/mcp_jira/tui.py` | Create | `_AbortMixin`, `ConfirmModal`, `ResultScreen`, `SetupApp`, `InstallApp` |
| `src/mcp_jira/wizard.py` | Modify | Drop rich/ui imports + 4 `_rich_*`; extract `_write_config()`; `run_wizard` becomes wrapper returning `app.run()` |
| `src/mcp_jira/installer.py` | Modify | Drop rich/ui imports + 2 `_rich_*` + `_select_targets`/`_selection_prompt`; extract `_collect_pending()`; add `_resolve_targets()`; `run_installer` becomes wrapper |
| `src/mcp_jira/ui.py` | Delete | Dead Rich consoles |
| `pyproject.toml` | Modify | `dependencies` += `textual>=8.2,<9`; dev += `pytest-asyncio`; `[tool.pytest.ini_options]` += `asyncio_mode = "auto"` |
| `uv.lock` | Modify | `uv lock` (5 net-new runtime + pytest-asyncio) |
| `tests/test_rich_adapters.py` | Delete | 9 tests, adapters deleted |
| `tests/test_wizard.py` | Rewrite | Keep `test_non_interactive_prints_path_and_exits_nonzero`; 8 flow tests → Pilot tests in `test_tui_setup.py` |
| `tests/test_installer.py` | Rewrite | Keep non-TTY + 11 pure tests; 6 flow tests → Pilot tests in `test_tui_install.py` |
| `tests/test_tui_setup.py`, `test_tui_install.py` | Create | Pilot-driven (below) |

## Interfaces / Contracts

```python
# wrappers — cli.py wiring and non-TTY branches untouched
def run_wizard(*, config_path: Path | None = None, interactive: bool | None = None,
               transport: httpx.BaseTransport | None = None) -> int:
    # non-TTY: print(f"Config path: {path}"); print(_GUIDANCE); return 1
    return SetupApp(config_path=path, transport=transport).run()  # app.exit(0|1)

def run_installer(*, interactive: bool | None = None,
                  config_paths: Callable[[], dict[str, Path]] | None = None) -> int:
    # non-TTY: print(_GUIDANCE); return 1
    return InstallApp(config_paths=config_paths or default_config_paths).run()

# Apps
class SetupApp(_AbortMixin, App[int]):
    def __init__(self, *, config_path: Path, transport: httpx.BaseTransport | None = None) -> None: ...
class InstallApp(_AbortMixin, App[int]):
    def __init__(self, *, config_paths: Callable[[], dict[str, Path]]) -> None: ...

# abort binding (D-^C)
BINDINGS = [Binding("ctrl+c", "abort", show=False, priority=True),
            Binding("ctrl+q", "abort", show=False, priority=True)]
def action_abort(self) -> None: self.exit(1)

# worker (D-WORKER)
@work(thread=True)
def check_connectivity(self, url: str, pat: str) -> None:
    try: JiraClient(url, pat, transport=self._transport).request("GET", "/rest/api/2/myself")
    except JiraError as exc:
        self.call_from_thread(self._connectivity_failed, str(exc)); return
    self.call_from_thread(self._connectivity_ok)
```

Widgets: `Input#url`, `Input#pat(password=True)`, `Select#language` (`en` default), `Switch#read_only` (off), `Static#connectivity_error`, `LoadingIndicator`, `Button#continue`; `SelectionList` (3 `_TARGETS`, `add_option(("label", id, True))`), inline notices `Static`, `Button#continue`. Shared: `ConfirmModal(Screen[bool])` with `Write`/`Cancel` → `dismiss(bool)`; `ResultScreen` with OK → `self.app.exit(0|1)`.

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit (unchanged) | wizard non-TTY (1); installer non-TTY + 11 pure (`load_json`, `upsert_client`, `write_with_backup`×4, `probe_desktop_dir`×3); test_cli 6 | Zero modification |
| Unit (new) | `_resolve_targets` (empty→all, dedupe, order); `_write_config` (0600 + 4 keys) | Plain pytest, ~4 tests |
| Pilot | SetupApp/InstallApp headless via `app.run_test(headless=True, size=(80,24))`; inject transport/config_paths; drive `pilot.click("#url")`, set `input.value`, `await pilot.pause()` | ~17 tests |

Pilot tests (`test_tui_setup.py`): success writes 0600 + 4 keys; optional defaults (en/false); es + read_only true; invalid URL rejected — `/myself` never called, no file; blank fields required-error; connectivity 401 → styled error, stays on form, no file; confirm declined → existing file untouched, exit 1; `ctrl+c` on input → exit 1, no file; `ctrl+c` on confirm modal → exit 1; `ctrl+q` → exit 1. (`test_tui_install.py`): success merges all (modes, `.bak`); default selection is all; subset → only selected written; already-registered notices, nothing rewritten; corrupt config skipped + untouched; confirm declined → nothing written; `ctrl+c` → nothing written.

**Deleted**: `test_rich_adapters.py` (9); wizard flow 8 (`interactive_success…`, `connectivity_failure…`, `empty_prompt…`, `invalid_url_reprompts…`, `optional_fields_default…`, `read_only_confirmed_true`, `decline_confirmation…`, `ctrl_c_aborts…`); installer flow 6 (`merges_all…`, `idempotent_rerun…`, `select_subset…`, `ctrl_c_at_selection…`, `declined_confirm…`, `corrupt_config_skipped…`). Net: −23, +~21.

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary (installer writes JSON config files; registered command values are data, unchanged, never executed).

## Migration / Rollout

No migration — config format and write semantics untouched. `uv lock` in the apply commit. Rollback: revert the commit, restore `_rich_*` + `ui.py` from the archived rich-tui baseline; Textual removal restores the pre-change lock (rich 15 already present).

## Open Questions

- [ ] client-installer §Testability prose names `_select_targets`; design replaces it with `_resolve_targets` (prompt-free, same semantics, no direct test today). Confirm a sdd-spec touch-up before verify, or record the rename in tasks.
- [ ] `ctrl+q` now aborts (exit 1) instead of Textual's default quiet quit — acceptable per "MAY abort", but confirm the footer hides both bindings (`show=False`).