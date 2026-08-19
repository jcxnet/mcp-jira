# Client Installer Specification

## Purpose

`mcp-jira install` registers the server into three MCP clients (OpenCode global, Claude CLI user scope, Claude Desktop) with merge-safe, idempotent writes mirroring `setup`.

## Requirements

### Requirement: install subcommand

`mcp-jira install` MUST exist as a CLI subcommand; non-TTY invocation MUST print guidance and exit 1. `^C` at any prompt MUST abort with exit 1 and nothing written. On a TTY it MUST present a form-style multi-select of clients with confirm-before-write.

#### Scenario: Interactive install

- GIVEN an interactive terminal
- WHEN the user selects clients and confirms
- THEN each selected config is merged

#### Scenario: Non-TTY guidance

- GIVEN no TTY
- WHEN `mcp-jira install` is invoked
- THEN guidance is printed and the process exits 1

#### Scenario: Ctrl-C aborts cleanly

- GIVEN awaiting input
- WHEN the user presses Ctrl-C
- THEN it exits 1 with nothing written

### Requirement: Registration command

The installer MUST register `[sys.executable, "-m", "mcp_jira"]` (absolute, cwd-independent), as an OpenCode local command-array entry (`"enabled": true`) and a Claude `command`+`args` entry. No `env` SHALL be written.

#### Scenario: Correct shapes written

- GIVEN a selected client
- WHEN the entry is written
- THEN the entry is `[sys.executable, "-m", "mcp_jira"]` in the client's shape

### Requirement: OpenCode global registration

The installer MUST target `~/.config/opencode/opencode.json`, upserting `mcp["mcp-jira"]` and preserving all other keys and servers.

#### Scenario: Merge preserves existing servers

- GIVEN opencode.json holding other servers and a Figma API key
- WHEN install registers mcp-jira
- THEN existing servers remain and the mcp-jira key is added

#### Scenario: Idempotent re-run

- GIVEN mcp-jira already registered in opencode.json
- WHEN install runs again
- THEN "already registered" is reported

### Requirement: Claude CLI user-scope registration

The installer MUST target the top-level `mcpServers` of `~/.claude.json` (user scope), merging without touching other entries.

#### Scenario: Merge into existing mcpServers

- GIVEN `~/.claude.json` with other user-scope servers
- WHEN install registers mcp-jira
- THEN those servers remain and mcp-jira is added

#### Scenario: Idempotent re-run

- GIVEN mcp-jira already present in `mcpServers`
- WHEN install runs again
- THEN "already registered" is reported

### Requirement: Claude Desktop registration

The installer MUST probe `~/.config/Claude/` then `~/.config/claude/`, use the first that exists (else `~/.config/Claude/`), merging `mcpServers` with preserve semantics.

#### Scenario: Capital-C directory wins

- GIVEN only `~/.config/Claude/` exists
- WHEN install runs
- THEN the entry is written to `~/.config/Claude/claude_desktop_config.json`

#### Scenario: Lowercase directory used

- GIVEN only `~/.config/claude/` exists
- WHEN install runs
- THEN the entry is written to `~/.config/claude/claude_desktop_config.json`

### Requirement: Write safety

The installer MUST create a `<file>.bak` before the first write to an existing file and re-parse the result, failing loudly (client untouched) on corruption. Unparseable configs MUST be skipped unmodified with no backup. Existing equivalent entries MUST be reported "already registered" and skipped, never overwritten. Config contents MUST NOT be logged or printed. Existing modes MUST be preserved; new files 0644.

#### Scenario: Backup created on first write

- GIVEN an existing config file
- WHEN it is first modified
- THEN a `.bak` copy exists

#### Scenario: Broken config skipped

- GIVEN an unparseable config
- WHEN install targets that client
- THEN the client is skipped, file untouched

#### Scenario: Post-write corruption detected

- GIVEN a write producing invalid JSON
- WHEN the re-parse runs
- THEN the installer reports failure loudly

#### Scenario: Secrets never logged

- GIVEN a config with a Figma API key
- WHEN install runs
- THEN no contents appear in output

### Requirement: Testability

The merge, path-probing, and target-selection logic MUST be injectable (temp dirs, fake configs, no real home writes). The existing suite MUST pass unmodified.

#### Scenario: Injectable temp-dir tests

- GIVEN injected paths and fake configs in a temp dir
- WHEN the installer runs
- THEN registration runs with no real home writes

*Trace: proposal rules; explore decisions (a)–(d); config-tui D1/D2/D6/D7.*
