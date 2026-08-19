# Exploration: `mcp-jira install` — register mcp-jira into MCP clients via a TUI

## Current State

`mcp-jira` is a stdio MCP server. Its CLI (`src/mcp_jira/cli.py`) has two paths: no subcommand → run the FastMCP stdio server; `setup` → the interactive config wizard (`src/mcp_jira/wizard.py`) that writes `~/.config/mcp-jira/config.json` (URL + hidden PAT, `/myself` check, confirm-before-write, `^C` abort, 0600 write, injectable `prompt`/`hidden_prompt`/`select`/`confirm`/`transport` for TTY-less tests).

**Client registration today is manual** — README §"Agent configuration" documents three JSON blocks the user must copy by hand (OpenCode `mcp` key, Claude Desktop `mcpServers`, Claude CLI via `claude mcp add` or `.mcp.json`). There is no `install` subcommand and PRD v1.0.0 has no installer story; SC-2 ("integration ease", "single mcpServers block") is the closest anchor — this change is an additive dev-tool beyond the PRD, in the same spirit as the `setup` wizard (AC-US-9).

**Real machine state (verified, not speculative):**

| Target | File | Exists? | Current mcp-jira entry |
|---|---|---|---|
| OpenCode (global) | `~/.config/opencode/opencode.json` | Yes | `{"type":"local","command":["uv","run","/home/jcxnet/projects/mcp-jira/.venv/bin/mcp-jira"],"enabled":true}` — added by hand. File also holds 6 other servers incl. a Figma API key. |
| OpenCode (project) | `<repo>/opencode.json` (committed) | Yes | `["uv","run","mcp-jira"]` (cwd-dependent; project-scoped) |
| Claude Desktop | `~/.config/claude/claude_desktop_config.json` | **No** (no Claude Desktop install) | — |
| Claude CLI (user) | `~/.claude.json` (0600) | Yes | top-level `mcpServers` holds codegraph/context7/engram; no mcp-jira |
| Claude CLI (project) | `<repo>/.mcp.json` | **No** | — |

Facts: `claude mcp add` defaults to `--scope local` (writes project `.mcp.json`); `-s user` writes `~/.claude.json` top-level `mcpServers` (where the 3 existing servers live). The repo venv console script exists at `.venv/bin/mcp-jira`. `claude` binary is installed; Claude Desktop is not.

## Affected Areas

- `src/mcp_jira/cli.py` — add `install` subcommand (mirrors `setup` wiring)
- `src/mcp_jira/installer.py` — **NEW**: form-style multi-select loop + merge/backup/validate writes, following the wizard's injectable pattern
- `tests/test_installer.py` — **NEW**: injectable-driven, tmp-path tests (no real home writes)
- `README.md` — document `mcp-jira install`
- `pyproject.toml` — no change needed (entry point exists; zero new deps)

## Approaches

1. **New `mcp-jira install` subcommand + `installer.py` (recommended)**
   - Pros: separate concern from `setup` (server config vs client registration); reuses the established form-style injectable pattern verbatim (config-tui D1/D2); stdlib-only; ~150 lines total; idempotent by design.
   - Cons: second interactive flow to maintain; per-client shapes differ slightly (OpenCode `command` array + `type`/`enabled`; Claude `command` string + `args`).
   - Effort: Low

2. **Extend `setup` wizard with a client-registration step**
   - Pros: one entry point.
   - Cons: conflates two concerns; `setup` is anchored to AC-US-9/PRD behavior (non-TTY guidance, `/myself` check) — bolting client writes on breaks that contract; harder to test in isolation; rejected.
   - Effort: Medium

3. **Widget TUI (Textual/prompt_toolkit)** — rejected by the user's established, non-negotiable decision (config-tui D1: form-style loop, zero deps). No new reason found to revisit.

4. **Shell script (bash + jq)** — rejected: jq dependency, no unit-testable harness, breaks the Python packaging story (`mcp-jira` console script is the entry point).

## Per-client targets (recommended defaults)

- **OpenCode → global `~/.config/opencode/opencode.json`**: upsert `mcp["mcp-jira"]`, preserve every other key verbatim (the file holds a Figma API key). The committed project `opencode.json` is a repo file, not user config — leave it alone.
- **Claude CLI → user scope `~/.claude.json`** top-level `mcpServers` (matches the 3 existing user-scope servers; works from any project — the "install once, use everywhere" semantic). Note: the README's `claude mcp add` example targets local scope; the installer picks user scope deliberately.
- **Claude Desktop → `~/.config/claude/claude_desktop_config.json`** (per session context), created if absent; see Risk 2 for the `Claude/` vs `claude/` case discrepancy.

## Command to register

`[sys.executable, "-m", "mcp_jira"]` — absolute, cwd-independent, no dependence on `uv` being on the client's PATH, no shell. `sys.executable` is correct because the installer always runs from the same venv it registers. Shapes written:

- OpenCode: `{"type": "local", "command": [py, "-m", "mcp_jira"], "enabled": true}`
- Claude (Desktop + CLI): `{"command": py, "args": ["-m", "mcp_jira"]}`

No `env` block — the PAT lives in `~/.config/mcp-jira/config.json` read at startup (`JIRA_URL`/`JIRA_PAT` are optional overrides, not needed here).

## Safety (lazy but not careless)

- **Merge, never clobber**: load existing JSON, upsert only the `mcp-jira` key, write back with `json.dump(indent=2)`. Unknown keys preserved.
- **Backup**: one `.bak` copy (`shutil.copy2`) before the first write to an existing file — one line, prevents data loss. New files: no backup needed.
- **Idempotent**: dict upsert by key; re-running updates, never duplicates. Entry already present with identical command → report "already registered", skip.
- **Validation**: existing file must parse as JSON or that client is skipped (never clobber a broken config); re-parse after write to confirm.
- **`^C` abort, confirm-before-write, non-TTY → guidance + exit 1**: all mirror the wizard (D6/D7 pattern).
- **Permissions**: preserve existing modes (`~/.claude.json` is 0600); new files 0644 (client configs contain no secrets — the PAT stays in mcp-jira's own 0600 file).
- **Never log config contents** (global opencode.json holds an API key).

## Scope boundaries (excluded)

No uninstall/update flows (delete-key is trivial but unrequested; `claude mcp remove` exists but keep it out), no systemd, Linux-only paths (error politely on other OS), no auto-detection beyond the 3 named clients, no env injection, no changes to the committed project `opencode.json`.

## Recommendation

Approach 1: a new `install` subcommand backed by a new `installer.py` that reuses the wizard's form-style injectable loop — stdlib only, ~150 lines, one small test file. It automates exactly what README documents by hand, into the three real user-config locations, with merge/backup/validate so it never destroys existing client config.

## Risks

1. **`~/.claude.json` merge**: a large stateful file (machineID, onboarding state). Mitigated by backup + strict JSON pre/post validation; any failure aborts that client with the file untouched.
2. **Claude Desktop Linux path case**: session context says `~/.config/claude/` (lowercase); official docs historically say `~/.config/Claude/` (capital C). No Claude Desktop on this machine to test. Design should probe both and use whichever exists (or the documented default when neither does).
3. **Global opencode.json contains a Figma API key** — installer must never log or print file contents; only the diff of the `mcp-jira` key.
4. **Existing manual registrations differ in command form** (`uv run <venv bin>` in global opencode.json vs the canonical `python -m mcp_jira`). Decide: treat functionally-equivalent existing entries as "already registered" (skip) or update-after-confirm.
5. **PRD v1.0.0 has no installer story** — proposal must frame this as an additive extension anchored to SC-2/AC-US-9, not a PRD requirement.

## Ready for Proposal

**Yes** — carry these open decisions into proposal/design: (a) existing-registration handling (skip vs update-on-confirm), (b) Claude Desktop path probing, (c) Claude CLI user-scope default, (d) non-TTY behavior (guidance + exit 1, mirroring `setup`).
