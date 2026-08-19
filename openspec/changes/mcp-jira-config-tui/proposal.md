# Proposal: Extend `mcp-jira setup` — optional fields, validation, confirmation

## Intent

`mcp-jira setup` (wizard.py) only writes `jira_url` + `jira_pat`, but the config schema supports `language` (en/es, default en) and `read_only` (default false). Those optional keys are unreachable from the supported creation flow — users must hand-edit JSON. This change extends the existing wizard in place (US-9 / AC-US-9): prompt the optional fields, validate input before write, confirm before overwriting, abort cleanly on ^C. Zero new dependencies. Stays inside PRD §2.4's file-based-config boundary — this is the creation form, not a UI dashboard.

## Scope

### In Scope
- Extend `run_wizard()`: `language` prompt (en/es, default `en`), `read_only` prompt (y/n, default `n`/false)
- URL `http(s)://` format validation before the /myself check (invalid → re-prompt, empty → reject)
- Pre-write summary + confirmation step (fixes silent-overwrite of an existing config)
- `^C` → clean abort, exit 1, nothing written
- Tests extended with the same injectable pattern; existing 4 tests keep passing unmodified

### Out of Scope
- Widget TUI (Textual/prompt_toolkit/curses), themes, arrow-key navigation — **user decision: form-style loop, NOT a widget TUI; not re-negotiable**
- Config editing beyond creation (no `edit` subcommand)
- Multi-profile management; Jira data browsing (project/field pickers)
- Any new dependency

## Capabilities

### New Capabilities
None — reuses the existing setup wizard surface; no new spec surface.

### Modified Capabilities
- `server-config`: §setup-wizard requirement gains optional-field prompts, URL format validation, pre-write confirmation, and ^C abort (delta spec in this change).

## Approach

Stdlib-only edit to `src/mcp_jira/wizard.py`. Keep `run_wizard()`'s injectable signature (`prompt`/`hidden_prompt`/`transport`); add `select`/`confirm` injectables defaulting to `input`. Reuse `config.SUPPORTED_LANGUAGES`, `default_config_path`, `JiraClient` /myself check, and the 0600 `os.open`+`os.chmod` write verbatim. Validate at input time so the load-time `language` fallback never fires from this path. Write still happens only after /myself succeeds and the user confirms.

## Business Rules (trace → server-config §setup-wizard scenarios)

| Rule | Anchored scenario |
|------|-------------------|
| URL + PAT required; empty → error, nothing written | Interactive success / existing |
| URL must be `http(s)://` → re-prompt on format error | New |
| `language` ∈ {en, es}, default `en` | schema §config-file-schema |
| `read_only` y/n, default `n` (false) | schema §read_only defaults |
| Confirm summary before write; overwrite only on yes | New (prevents silent truncate) |
| `^C` any time → abort, exit 1, no file | New |
| Connectivity failure → nothing written | Connectivity failure |
| Non-TTY → print path + guidance, exit 1 | Non-interactive without config |
| File written 0600 | §config-file-permissions |

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/mcp_jira/wizard.py` | Modified | prompts, validation, confirmation, ^C handling (~30–40 line delta) |
| `tests/test_wizard.py` | Modified | new `select`/`confirm` injectables + new cases; existing 4 untouched |
| `src/mcp_jira/config.py`, `client.py`, `cli.py`, `pyproject.toml` | None | reuse only; no changes, no new dep |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Scope creep toward widget TUI | Med | Proposal binds every req to setup-wizard scenarios; user decision recorded |
| Injectable pattern drift breaks suite | Low | New `select`/`confirm` follow same default-to-stdlib signature |
| Confirmation skipped as "nice-to-have" | Med | Make it a MUST requirement — it is the overwrite fix |

## Rollback Plan

Single-file revert: `git revert` of the wizard.py/tests commit. No data migration; existing configs (2-key or 4-key) are unaffected — load path unchanged.

## Dependencies

- None (stdlib only; `mcp`, `httpx` unchanged)

## Success Criteria

- [ ] `uv run mcp-jira setup` on a TTY writes a config containing all 4 keys with 0600
- [ ] Invalid URL format and empty input never reach /myself or write
- [ ] Confirmation declined or `^C` → exit 1, no file created/truncated
- [ ] Existing 4 wizard tests pass unmodified; new cases cover select/confirm/^C
- [ ] `uv run pytest` green; no new dependency in `uv.lock`
