# Delta for client-installer

## MODIFIED Requirements

### Requirement: install subcommand

`mcp-jira install` MUST exist as a CLI subcommand. Non-TTY invocation MUST print guidance via plain `print()` and exit 1, byte-identical to before. On a TTY it MUST present a Textual widget TUI: a `SelectionList` multi-select of the three clients (all selected by default), inline "already registered" and corrupt-skip notices, and a confirm modal before any write. A priority `ctrl+c` binding on any screen MUST abort with exit 1 and nothing written. Write safety (`.bak` once, atomic `os.replace`, post-write re-parse + restore), idempotent "already registered" handling, and the venv-absolute `[sys.executable, "-m", "mcp_jira"]` command MUST be preserved unchanged.
(Previously: form-style Rich multi-select with confirm-before-write; `^C` at any prompt.)

#### Scenario: Interactive install

- GIVEN an interactive terminal
- WHEN the user adjusts the SelectionList and confirms
- THEN each selected config is merged via `write_with_backup`

#### Scenario: Default selection is all clients

- GIVEN the SelectionList is shown
- WHEN the user confirms without changing the selection
- THEN all three clients are targeted (empty selection defaults to all)

#### Scenario: Non-TTY guidance

- GIVEN no TTY
- WHEN `mcp-jira install` is invoked
- THEN guidance is printed and the process exits 1

#### Scenario: Ctrl-C aborts cleanly

- GIVEN the app is focused on any screen
- WHEN the user presses Ctrl-C
- THEN it exits 1 with nothing written

### Requirement: Testability

The pure functions — `load_json`, `upsert_client`, `write_with_backup`, `probe_desktop_dir`, `_resolve_targets` (previously `_select_targets`) — MUST remain unit-tested unchanged with injected paths and fake configs in temp dirs (no real home writes). The interactive flow MUST be driven via Textual Pilot (`run_test(headless=True)`) with config paths injected on the app.
(Previously: merge/path-probing/target-selection logic injectable; the existing suite MUST pass unmodified.)

#### Scenario: Injectable temp-dir tests

- GIVEN injected paths and fake configs in a temp dir
- WHEN the pure functions run
- THEN registration merges with no real home writes

#### Scenario: Pilot drives the interactive flow

- GIVEN InstallApp run headless with injected config paths
- WHEN the pilot selects targets and confirms
- THEN the flow completes deterministically without a TTY

#### Scenario: Pure-function suite unaffected

- GIVEN the `load_json`/`upsert_client`/`write_with_backup`/`probe_desktop_dir` tests as they exist today
- WHEN the TUI change is applied
- THEN they pass without modification

*Trace: proposal Delta Spec Direction, D-^C, D-TTY, D-TEST, D-DEAD; explore decisions (a)–(d); config-tui D1/D2/D6/D7.*
