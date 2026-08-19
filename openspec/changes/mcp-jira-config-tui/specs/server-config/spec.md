# Delta for server-config

## MODIFIED Requirements

### Requirement: Setup wizard

`mcp-jira setup` MUST prompt for the Jira URL, a hidden PAT, and the optional `language` (`en`/`es`, default `en`) and `read_only` (`y`/`n`, default `false`) fields. It MUST validate that the URL is non-empty and uses `http(s)://` format before any connectivity check. It MUST NOT write until BOTH the `/myself` connectivity check succeeds AND the user explicitly confirms a summary of the collected values (URL, language, read_only). A `^C` at any prompt MUST abort cleanly with non-zero exit and nothing written. Non-interactive invocation with missing config MUST print the config path and guidance and exit non-zero. The hidden PAT prompt, `/myself` failure → nothing written, `0600` write, and non-TTY behavior MUST be preserved unchanged.
(Previously: prompted only URL + hidden PAT and wrote immediately after `/myself`, with no optional-field prompts, URL format validation, pre-write confirmation, or ^C abort.)

#### Scenario: Interactive success

- GIVEN an interactive terminal
- WHEN the user answers all four prompts, confirms the summary, and `/myself` succeeds
- THEN config.json is written with 0600 containing all four keys (`jira_url`, `jira_pat`, `language`, `read_only`) and success is reported

#### Scenario: Optional fields default when skipped

- GIVEN the language and read_only prompts show defaults
- WHEN the user accepts both defaults
- THEN the written config contains `language` `"en"` and `read_only` `false` and is valid

#### Scenario: Invalid URL format rejected

- GIVEN the user enters a blank or non-`http(s)://` URL
- WHEN the URL prompt is answered
- THEN the wizard reports a format error, never calls `/myself`, and writes no file

#### Scenario: Confirmation declined aborts

- GIVEN the summary is shown for a path with an existing config
- WHEN the user declines confirmation
- THEN the wizard exits non-zero and the existing file is left unmodified

#### Scenario: Ctrl-C aborts cleanly

- GIVEN the wizard is awaiting input at any prompt
- WHEN the user presses Ctrl-C
- THEN the wizard exits non-zero and no config file is written or truncated

#### Scenario: Connectivity failure

- GIVEN an unreachable URL
- WHEN the wizard tests connectivity
- THEN the failure is reported and nothing is written

#### Scenario: Non-interactive without config

- GIVEN no TTY and no existing config
- WHEN `mcp-jira setup` is invoked
- THEN it prints the config path and guidance and exits non-zero

## ADDED Requirements

### Requirement: Wizard testability

`run_wizard` MUST keep its existing `prompt`, `hidden_prompt`, and `transport` injectables and MUST expose new `select` and `confirm` injectables following the same pattern, so every prompt — including the optional fields and confirmation — is drivable in tests without a TTY. The existing four wizard tests MUST pass unmodified.

#### Scenario: Injectables drive the full flow

- GIVEN injected prompt/hidden_prompt/select/confirm lambdas and a mock transport
- WHEN run_wizard executes
- THEN all prompts are answered without a TTY and the run completes deterministically

#### Scenario: Existing suite unaffected

- GIVEN `tests/test_wizard.py` as it exists today
- WHEN the wizard change is applied
- THEN all four existing tests pass without modification

*Trace: AC-US-9, AC-US-11, AC-US-12, SC-2, SC-3, §4.4 CONFIG_* codes; proposal business rules (URL format, confirmation, ^C, defaults).*
