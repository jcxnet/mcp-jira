# Delta for Error Handling

## ADDED Requirements

### Requirement: Error taxonomy

All errors MUST map to the §4.4 codes and behaviors:

| Code | Detection | Behavior |
|---|---|---|
| CONFIG_MISSING | config absent or missing `jira_url`/`jira_pat` | fail fast, no tools |
| CONFIG_INVALID | malformed JSON, empty URL, bad types | fail fast, no tools |
| AUTH_UNAUTHORIZED | HTTP 401 | readable message; suggest re-running setup |
| AUTH_FORBIDDEN | HTTP 403 | readable message; no retry |
| NOT_FOUND | HTTP 404 | "Resource not found: `<type> <id>`" |
| VALIDATION_ERROR | HTTP 400 on create/update/search | include Jira field errors verbatim |
| JQL_INVALID | HTTP 400 with JQL error | Jira errorMessages verbatim + hints |
| TRANSITION_INVALID | transition not in available list | list valid transitions |
| FIELD_NOT_EDITABLE | read-only field in update | no retry with same field |
| RATE_LIMITED | HTTP 429 | surface Retry-After; no auto-retry |
| SERVER_ERROR | HTTP 5xx | readable; agent decides |
| NETWORK_ERROR | refused, timeout, TLS, DNS | suggest curl of base URL |
| READ_ONLY_MODE | `read_only: true` on mutating tool | tool registered, always fails |
| INTERNAL | unexpected exception | safe detail only; log locally |

#### Scenario: 401 maps to AUTH_UNAUTHORIZED

- GIVEN a tool call returns HTTP 401
- WHEN the error is surfaced
- THEN the code is AUTH_UNAUTHORIZED with the §4.4 message

#### Scenario: 429 surfaces Retry-After

- GIVEN HTTP 429 with `Retry-After: 30`
- WHEN the error is surfaced
- THEN the code is RATE_LIMITED and the message includes 30s

### Requirement: Error precedence

When multiple conditions apply, the server MUST report in order: `CONFIG_*` > `AUTH_*` > `RATE_LIMITED` > `VALIDATION_*` > `NOT_FOUND` > `SERVER_ERROR` > `NETWORK_ERROR` > `INTERNAL`.

#### Scenario: Auth wins over later codes

- GIVEN a call that both times out and yields HTTP 401
- WHEN the error is surfaced
- THEN AUTH_UNAUTHORIZED is reported

### Requirement: Retry policy

The server MUST NOT retry `AUTH_*`, `VALIDATION_*`, `NOT_FOUND`, `TRANSITION_INVALID`, `FIELD_NOT_EDITABLE`, or `READ_ONLY_MODE`; MUST NOT auto-retry `RATE_LIMITED`; MUST retry `SERVER_ERROR`/`NETWORK_ERROR` at most once after a 1s backoff.

#### Scenario: 5xx retried once

- GIVEN two consecutive HTTP 500 responses
- WHEN a tool call runs
- THEN one retry occurs and SERVER_ERROR is surfaced after the second failure

#### Scenario: 429 never auto-retried

- GIVEN an HTTP 429 response
- WHEN a tool call runs
- THEN no retry occurs and RATE_LIMITED is surfaced

### Requirement: Logging and redaction

The server MUST log to stderr only (never stdout, the MCP transport), MUST redact the PAT from all logs, MUST log HTTP status and the Jira correlation ID when provided, MUST localize surfaced messages to `language`, and MUST never surface stack traces or raw HTTP dumps to the agent.

#### Scenario: PAT never leaks

- GIVEN a failed authenticated call
- WHEN logs and the surfaced error are inspected
- THEN the PAT appears in neither

#### Scenario: INTERNAL keeps stack local

- GIVEN an unexpected exception
- WHEN it is surfaced
- THEN the agent sees only a safe detail while the full trace goes to local logs

*Trace: AC-ALL, SC-3, SC-4, §4.4 taxonomy/precedence/retry, US-11*