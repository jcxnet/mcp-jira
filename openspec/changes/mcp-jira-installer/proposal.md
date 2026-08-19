# Proposal: `mcp-jira install` — register the server into MCP clients

## Intent

Client registration is manual: README §"Agent configuration" documents three JSON blocks users copy by hand into OpenCode, Claude Desktop, and Claude CLI configs. `setup` handles server config; nothing automates client wiring. This adds an `install` subcommand that merges mcp-jira into the three real user-config files — same spirit as `setup` (AC-US-9), anchored to PRD SC-2 (integration ease), additive beyond PRD v1.0.0.

## Scope

### In Scope
- `install` subcommand in `cli.py` (mirrors `setup` wiring)
- `src/mcp_jira/installer.py` — form-style multi-select loop, stdlib, zero deps, wizard's injectable pattern
- Merge writes: OpenCode global `~/.config/opencode/opencode.json` (`mcp` key), Claude CLI user scope `~/.claude.json` (top-level `mcpServers`), Claude Desktop config
- Registered command: `[sys.executable, "-m", "mcp_jira"]` — absolute, cwd-independent, no `uv` dependency
- Backup + pre/post JSON validation + confirm-before-write + `^C` abort + idempotency
- `tests/test_installer.py`; README §Agent configuration replaced by install guidance
- Non-TTY → print guidance + exit 1 (mirror `setup`)

### Out of Scope
- Uninstall/update flows, systemd, Windows/macOS, auto-detecting other clients, env injection
- Committed project `opencode.json`, the server, and `setup`/wizard — untouched
- Any new dependency

## Capabilities

### New Capabilities
- `client-installer`: `mcp-jira install` registers the server into OpenCode global, Claude CLI user-scope, and Claude Desktop configs via merge-safe writes.

### Modified Capabilities
None.

## Approach

New `installer.py` reusing `wizard.py`'s form-style injectable loop (`prompt`/`confirm` injectables; `_is_interactive` non-TTY path). One `run_installer()`, one client-discovery step, one `merge_write(path, upsert)` helper: load → upsert `mcp-jira` key → `json.dump(indent=2)`; `.bak` copy before first write to an existing file; re-parse to confirm. Shapes: OpenCode `{"type":"local","command":[py,"-m","mcp_jira"],"enabled":true}`; Claude `{"command":py,"args":["-m","mcp_jira"]}`. No `env` — PAT stays in mcp-jira's own 0600 file.

## Business Rules

| Rule | Anchored |
|------|----------|
| Register into the 3 named clients only | README §Agent configuration |
| Merge, never clobber; unknown keys preserved | Risk 3 (Figma key) |
| Existing functionally-equivalent entry → "already registered", skip, no overwrite | Decision (a) |
| Desktop path: probe `~/.config/Claude/` then `~/.config/claude/`; first existing wins; default `Claude/` if neither | Decision (b) |
| Claude CLI user scope on by default (`~/.claude.json` holds user-scope servers) | Decision (c) |
| Non-TTY → guidance + exit 1 | Decision (d) / setup pattern |
| Backup + strict JSON validation before/after write; broken config → skip client, file untouched | Safety |
| Confirm-before-write, `^C` abort, exit 1, nothing written | setup pattern (D6/D7) |
| Never log/print config contents; preserve modes (0600 `~/.claude.json`, 0644 new) | Safety |

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/mcp_jira/cli.py` | Modified | `install` subcommand wiring |
| `src/mcp_jira/installer.py` | New | TUI + merge/backup/validate (~150 lines) |
| `tests/test_installer.py` | New | injectable/tmp-path; no real home writes |
| `README.md` | Modified | install docs replace manual blocks |
| `~/.config/opencode/opencode.json`, `~/.claude.json` | Modified (user machines) | merged, backed up |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| `~/.claude.json` merge corrupts stateful file | Low | backup + pre/post validation; failure aborts client untouched |
| Desktop path case (`Claude/` vs `claude/`) | Med | probe both, first existing wins |
| Clobber configs holding secrets (Figma key) | Low | merge-only upsert; never log contents |

## Rollback Plan

Per-file: restore the `.bak` backup (one per touched file) or delete the `mcp-jira` key. No server/config changes; `git revert` of the installer commit removes the feature.

## Dependencies

- None (stdlib only; `mcp`, `httpx` unchanged)

## Success Criteria

- [ ] TTY run registers into all 3 clients with correct shapes; re-run reports "already registered", configs unchanged
- [ ] Existing keys (incl. Figma) byte-identical apart from the `mcp-jira` upsert
- [ ] Broken JSON config → that client skipped, file untouched
- [ ] `^C` / declined confirm → exit 1, nothing written; `.bak` created on first write
- [ ] `uv run pytest` green; no new dep in `uv.lock`
