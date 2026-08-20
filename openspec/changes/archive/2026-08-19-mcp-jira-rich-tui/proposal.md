# Proposal: Rich styling for setup wizard and install installer

## Intent

`mcp-jira setup` and `mcp-jira install` render as bare plain-text loops: `input()`/`getpass` prompts, unformatted errors, no progress feedback on the `/myself` connectivity check. Users get no visual state cue and no structured confirmation summary. This change adds Rich-based styling to the interactive TTY path only, with zero change to the injectable-lambda test contract or non-TTY behavior.

## Scope

### In Scope
- One shared Rich `Console` for wizard and installer interactive paths (styled errors → stderr)
- Wizard: styled error output, `Panel` summary before write confirmation, `Spinner` around `/myself` connectivity check
- Installer: styled form-style multi-select
- Rich `Prompt.ask`/`Confirm.ask` as the DEFAULT lambdas behind unchanged signatures (`prompt`, `hidden_prompt`, `select`, `confirm` in `run_wizard`; `targets_selected`, `confirm` in `run_installer`)
- Non-TTY branch stays 100% plain `print()` (spec: "non-TTY behavior MUST be preserved unchanged")
- Add `rich>=13.7` to `pyproject.toml`; `uv.lock` grows ~3 net-new entries (markdown-it-py, mdurl; pygments promoted)
- Existing 184 tests pass unmodified

### Out of Scope
- Textual, widget TUI, themes, config *editing* subcommand
- Any behavioral change to config file format or write semantics
- Any change to the injectable test contract

## Capabilities

### New Capabilities
None — styled presentation introduces no new spec requirement.

### Modified Capabilities
None — `server-config` (Setup wizard, Wizard testability) and `client-installer` (install subcommand, Testability) requirements remain fully valid; no scenario asserts plain-text output strings, so styling is pure implementation. Design phase folds in Rich specifics: markup escaping of `[...]`, `Confirm.ask` bool→str adapter, load-bearing prompt strings (e.g. "Write config").

## Approach

Exploration recommendation B scoped with A's discipline: a single shared `Console` in `cli.py` wired into the `wizard.py`/`installer.py` interactive branches. Rich prompts replace plain defaults; prompt strings stay byte-identical (load-bearing in tests). Empirically verified: Rich output under pytest `capsys` carries no ANSI, so existing substring assertions pass unmodified.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/mcp_jira/wizard.py` | Modified | Rich default lambdas, styled errors, Panel summary, /myself spinner |
| `src/mcp_jira/installer.py` | Modified | Rich default lambdas, styled multi-select |
| `src/mcp_jira/cli.py` | Modified | Shared Console construction and wiring |
| `pyproject.toml`, `uv.lock` | Modified | Add `rich>=13.7` |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Rich markup mangles `[...]` in prompts | Med | Escape user-supplied values; design-phase tests |
| `Confirm.ask` bool vs str contract | Med | Thin adapter preserving the str contract |
| Test assertions drift | Low | Prompt strings unchanged; capsys no-ANSI verified |
| Rich pulls heavy dependency tree | Low | rich is pure-Python; ~3 net-new lock entries |

## Rollback Plan

Revert the single commit: remove `rich` from `pyproject.toml`, restore plain `input`/`getpass` defaults. No persisted state, config format, or write semantics change, so rollback is instant and safe; `.bak`/0600 safety untouched.

## Dependencies

- `rich>=13.7` (net-new runtime dependency; runtime deps otherwise stay mcp + httpx)

## Success Criteria

- [ ] `uv run pytest` green: 184 tests, zero modifications under `tests/`
- [ ] Interactive wizard/installer show styled output (Panel, spinner, colored errors) on a TTY
- [ ] Non-TTY invocation output byte-identical to pre-change
- [ ] Config writes, 0600 mode, `.bak` safety, and exit codes unchanged
