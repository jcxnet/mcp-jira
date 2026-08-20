# Proposal: Textual widget TUI for `mcp-jira setup` and `mcp-jira install`

## Intent

User reversed the config-tui decision ("form-style loop, NOT a widget TUI"). `setup` and `install` become real Textual widget TUIs — arrow keys, form widgets, masked input — replacing the Rich line prompts. Only the presentation layer changes: every logic/write/merge/security line stays untouched.

## Scope

### In Scope
- New `src/mcp_jira/tui.py`: `SetupApp` + `InstallApp` + shared abort binding, confirm modal, result screen
- `run_wizard()`/`run_installer()` become TTY-gated int-returning wrappers (cli.py wiring survives)
- `textual>=8.2,<9` runtime dep; `pytest-asyncio` dev dep
- ~23 tests rewritten/removed as Pilot-driven; ~15–20 new Pilot tests
- Delta specs MODIFY `server-config` §Setup wizard + §Wizard testability, `client-installer` §install subcommand + §Testability; ADD tui-abort-binding, connectivity-worker

### Out of Scope
- Config editing (`edit` subcommand) — prior non-goal stands
- Themes, multi-profile, Jira browsing, `[syntax]` extra
- Non-TTY plain `print()` branches stay byte-identical
- Server MCP tools, config format, write semantics — unchanged

## Capabilities

### New Capabilities
None — the TUI is presentation; new requirements attach to existing capabilities (delta requirements below).

### Modified Capabilities
- `server-config`: §Setup wizard (interactive path = widget TUI), §Wizard testability (Pilot-driven)
- `client-installer`: §install subcommand (widget multi-select), §Testability (Pilot-driven; pure functions unchanged)

## Approach (exploration Approach 3)

- `wizard.py`/`installer.py`: keep all pure logic (`_valid_url`, 0600 write, `load_json`, `upsert_client`, `write_with_backup`, `probe_desktop_dir`, `_select_targets`); delete `_rich_*` adapters; wrappers do `if not interactive: print(_GUIDANCE); return 1`, else run app and return its exit code.
- `tui.py`: `SetupApp` (Input#url, Input#pat `password=True`, Select#language, Switch#read_only, worker `/myself`, confirm modal, result); `InstallApp` (SelectionList default-all, inline already-registered/corrupt notices, confirm modal, per-path `write_with_backup`).
- `cli.py` untouched; `ui.py` deleted with `_rich_*` + their 9 tests.

## Design Decisions

| ID | Decision |
|----|----------|
| D-^C | Textual 8 changed ^C (copy/notice). Priority binding `ctrl+c → action_abort`, exit 1, nothing written — Pilot-tested. Keeps AC-US-9/§Ctrl-C |
| D-TTY | `_is_interactive()` gate kept; Textual only on TTY |
| D-TEST | Pilot `run_test(headless)` + pytest-asyncio; ~23 break, ~170 survive |
| D-WORKER | `/myself` in `@work(thread=True)`; sync httpx never blocks UI |
| D-DEAD | `ui.py` + `_rich_*` deleted with their tests |
| D-DEP | textual>=8.2,<9 + pytest-asyncio; exactly 5 net-new lock entries (textual, mdit-py-plugins, platformdirs, linkify-it-py, uc-micro-py) |

## Delta Spec Direction

**MODIFIED (mandatory — verify fails otherwise):** `server-config` §Wizard testability ("injectables; existing four tests MUST pass unmodified" → "wizard behavior driven via Pilot; non-TTY gate and write semantics unchanged"); `client-installer` §Testability ("existing suite MUST pass unmodified" → "pure functions unit-tested unchanged; interactive flow Pilot-driven"). Interactive-path wording in §Setup wizard and §install subcommand updated to widget TUI.

**ADDED:** `server-config` tui-abort-binding (priority `ctrl+c` on any screen → exit 1, nothing written); connectivity-worker (`/myself` in worker; failure → stay on form, nothing written).

**RESTATED unchanged:** non-TTY behavior, hidden PAT, `/myself`-gated writes, 0600, `.bak`/atomic/re-parse, idempotency.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/mcp_jira/tui.py` | New | SetupApp/InstallApp + shared helpers |
| `src/mcp_jira/wizard.py`, `installer.py` | Modified | Wrappers; `_rich_*` deleted |
| `src/mcp_jira/ui.py` | Removed | Dead code |
| `src/mcp_jira/cli.py` | None | Names + int-return kept |
| `pyproject.toml`, `uv.lock` | Modified | +textual, +pytest-asyncio, 5 lock entries |
| `tests/test_wizard.py` (8), `test_installer.py` (6), `test_rich_adapters.py` (9) | Modified/Removed | Pilot-driven |
| `openspec/specs/{server-config,client-installer}/spec.md` | Modified | Delta specs |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Textual 8 ^C = copy/notice breaks AC-US-9 | High | Priority binding + Pilot `ctrl+c` test |
| Sync `/myself` freezes UI | Med | `@work(thread=True)` worker |
| Testability reqs assert old suite | High | Delta spec MUST modify both (verify gate) |
| Async test style new to repo | Med | pytest-asyncio; `asyncio.run` wrappers where possible |
| Scope creep toward config editing | Med | Non-goal restated; change bound to setup/install |

## Rollback Plan

Revert the commit(s); restore `_rich_*` adapters + `ui.py` from the archived rich-tui baseline. No data migration — file format and write semantics untouched; removing Textual restores the pre-change lock (rich 15 already present).

## Dependencies

- `textual>=8.2,<9` (runtime); `pytest-asyncio` (dev); 5 net-new pure-Python lock entries

## Success Criteria

- [ ] `uv run pytest` green: ~170 existing + ~15–20 Pilot tests
- [ ] Pilot covers: interactive success, invalid URL re-prompt, decline-abort, `ctrl+c` abort, connectivity failure, non-TTY
- [ ] `ctrl+c` at any screen → exit 1, nothing written
- [ ] Non-TTY output byte-identical; 0600/`.bak`/atomic/idempotency unchanged
- [ ] `test_cli.py` 6/6 unmodified; `cli.py` zero diff