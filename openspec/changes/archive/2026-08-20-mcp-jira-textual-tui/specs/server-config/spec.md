# Delta for server-config

## MODIFIED Requirements

### Requirement: Setup wizard

`mcp-jira setup` MUST present a Textual widget TUI on interactive terminals: arrow-key navigation and form widgets — `Input` for the Jira URL, masked `Input` (`password=True`) for the PAT, `Select` for optional `language` (`en`/`es`, default `en`), `Switch` for optional `read_only` (default `false`). It MUST validate that the URL is non-empty and uses `http(s)://` format before any connectivity check. It MUST NOT write until BOTH the `/myself` connectivity check succeeds AND the user explicitly confirms a summary of the collected values (URL, language, read_only). A priority `ctrl+c` binding on any screen MUST abort cleanly with exit 1 and nothing written. Non-interactive invocation with missing config MUST print the config path and guidance via plain `print()` and exit non-zero, byte-identical to the previous Rich behavior. The hidden PAT input, URL format validation, `language`/`read_only` defaults, `0600` write, and nothing-written-unless-connectivity-plus-confirm MUST be preserved unchanged.
(Previously: Rich line prompts for each field; `^C` handled by the prompt library.)

#### Scenario: Interactive success

- GIVEN an interactive terminal
- WHEN the user fills the URL and masked PAT inputs, accepts the language/read_only defaults, `/myself` succeeds, and the summary is confirmed
- THEN config.json is written with 0600 containing all four keys (`jira_url`, `jira_pat`, `language`, `read_only`) and success is reported

#### Scenario: Optional fields default when skipped

- GIVEN the language Select and read_only Switch show defaults
- WHEN the user confirms without changing them
- THEN the written config contains `language` `"en"` and `read_only` `false` and is valid

#### Scenario: Invalid URL format rejected

- GIVEN the user enters a blank or non-`http(s)://` URL
- WHEN the URL input is submitted
- THEN the form shows a format error, `/myself` is never called, and no file is written

#### Scenario: Confirmation declined aborts

- GIVEN the summary modal is shown for a path with an existing config
- WHEN the user declines confirmation
- THEN the app exits non-zero and the existing file is left unmodified

#### Scenario: Ctrl-C aborts cleanly

- GIVEN the app is focused on any screen
- WHEN the user presses Ctrl-C
- THEN the app exits 1 and no config file is written or truncated

#### Scenario: Connectivity failure

- GIVEN an unreachable URL
- WHEN the `/myself` check runs
- THEN the failure is reported via a styled error, the app stays on the form, and nothing is written

#### Scenario: Non-interactive without config

- GIVEN no TTY and no existing config
- WHEN `mcp-jira setup` is invoked
- THEN it prints the config path and guidance and exits non-zero

### Requirement: Wizard testability

Wizard behavior MUST be drivable without a TTY or live Jira via Textual Pilot: `run_test(headless=True)` with the transport and config path injected on the app, driving widget input and the confirm modal like a user. The non-TTY gate and the write semantics (0600, nothing written unless connectivity + confirm) MUST remain covered by unit tests unchanged.
(Previously: injectable `prompt`/`hidden_prompt`/`select`/`confirm` lambdas; the existing four wizard tests MUST pass unmodified.)

#### Scenario: Pilot drives the full flow

- GIVEN SetupApp run headless with an injected mock transport and config path
- WHEN the pilot fills the URL and PAT, accepts the defaults, and confirms
- THEN the flow completes deterministically with the expected file written and no TTY required

#### Scenario: Non-TTY and write tests unaffected

- GIVEN the non-interactive gate and write-semantics tests as they exist today
- WHEN the TUI change is applied
- THEN they pass without modification

## ADDED Requirements

### Requirement: tui-abort-binding

`SetupApp` and `InstallApp` MUST register a priority `ctrl+c` binding (`action_abort`) on every screen, because Textual 8 no longer quits on `^C`. Pressing `ctrl+c` on any screen MUST abort with exit code 1 and MUST NOT write or truncate any file. `q` and `ctrl+q` MAY abort as well.

#### Scenario: Ctrl-C on a form input

- GIVEN SetupApp is focused on the URL input
- WHEN the user presses Ctrl-C
- THEN the app exits 1 and no config file is written

#### Scenario: Ctrl-C on the confirm modal

- GIVEN the confirm modal is shown
- WHEN the user presses Ctrl-C
- THEN the app exits 1 and nothing is written

### Requirement: connectivity-worker

The `/myself` connectivity check MUST run in a background Textual worker (`@work(thread=True)`) so the sync httpx call never blocks the UI thread; a loading indicator MUST be shown while in flight. On failure the app MUST stay on the form with a styled error and MUST NOT write. On success the app MUST enable the confirm step.

#### Scenario: Check runs without freezing the UI

- GIVEN a valid URL and a slow `/myself` response
- WHEN the user submits the form
- THEN a loading indicator is shown and the app stays responsive while the check runs in the worker

#### Scenario: Worker failure keeps the form open

- GIVEN `/myself` returns an error
- WHEN the worker completes
- THEN a styled error is shown, the app stays on the form, and nothing is written

*Trace: AC-US-9, AC-US-11, AC-US-12, SC-2, SC-3, §4.4 CONFIG_* codes; proposal Delta Spec Direction, D-^C, D-WORKER, D-TTY, D-TEST.*
