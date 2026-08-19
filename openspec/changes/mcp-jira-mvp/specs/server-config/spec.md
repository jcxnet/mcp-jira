# Delta for Server Configuration

## ADDED Requirements

### Requirement: Config file schema

The server MUST load `~/.config/mcp-jira/config.json` with keys `jira_url`, `jira_pat`, `language` (`en` default, `es` optional; unknown values fall back to `en`), and `read_only` (boolean, default `false`).

#### Scenario: Valid config loads

- GIVEN a well-formed config with `jira_url` and `jira_pat`
- WHEN the server starts
- THEN settings are applied and tools register

#### Scenario: Unknown language falls back to en

- GIVEN config with `language: "fr"`
- WHEN the server starts
- THEN tool names/descriptions render in English

#### Scenario: read_only defaults to false

- GIVEN config without a `read_only` key
- WHEN the server starts
- THEN read_only is false and mutating tools are active

### Requirement: Environment overrides

`JIRA_URL` and `JIRA_PAT` env vars MUST override the corresponding file values; `language` and `read_only` MUST be file-only settings.

#### Scenario: Env value wins

- GIVEN file `jira_url = A` and env `JIRA_URL = B`
- WHEN the server starts
- THEN jira_url resolves to B

#### Scenario: File-only settings unchanged

- GIVEN `language` set only in the file
- WHEN the server starts
- THEN the file value is used and no env override applies

### Requirement: Startup validation

The server MUST fail fast (no tools exposed) with `CONFIG_MISSING` when the file is absent or `jira_url`/`jira_pat` are missing, and with `CONFIG_INVALID` on malformed JSON, empty URL, non-boolean `read_only`, or unsupported `language`. Startup MUST verify credentials via `GET /rest/api/2/myself`.

#### Scenario: Missing config

- GIVEN no config file exists
- WHEN the server starts
- THEN it fails with CONFIG_MISSING and exposes no tools

#### Scenario: Malformed JSON

- GIVEN a config.json containing invalid JSON
- WHEN the server starts
- THEN it fails with CONFIG_INVALID and a readable detail

#### Scenario: Credential check fails

- GIVEN a valid config but `/myself` returns 401
- WHEN the server starts
- THEN startup fails with AUTH_UNAUTHORIZED and exposes no tools

### Requirement: Config file permissions

The setup wizard MUST write `config.json` with `0600` permissions, and the server MUST warn (not block) when an existing config is world-readable.

#### Scenario: World-readable warning

- GIVEN an existing config.json with mode 0644
- WHEN the server starts
- THEN a warning is logged and startup continues

### Requirement: Setup wizard

`mcp-jira setup` MUST prompt for URL and PAT (hidden input), test connectivity via `/myself`, write the config with `0600`, and report success/failure. Non-interactive invocation with missing config MUST print the config path and guidance and exit non-zero.

#### Scenario: Interactive success

- GIVEN an interactive terminal
- WHEN the user answers prompts and `/myself` succeeds
- THEN config.json is written with 0600 and success is reported

#### Scenario: Connectivity failure

- GIVEN an unreachable URL
- WHEN the wizard tests connectivity
- THEN the failure is reported and nothing is written

#### Scenario: Non-interactive without config

- GIVEN no TTY and no existing config
- WHEN `mcp-jira setup` is invoked
- THEN it prints the config path and guidance and exits non-zero

*Trace: AC-US-8, AC-US-9, AC-US-11, AC-US-12, SC-2, SC-3, §4.4 CONFIG_* codes*