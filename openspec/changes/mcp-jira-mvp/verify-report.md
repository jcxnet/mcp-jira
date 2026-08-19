```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:5ade094b5332323fc78be011a88908e344e02e6f08fe5741af372cb933382f31
verdict: pass
blockers: 0
critical_findings: 0
requirements: 17/17
scenarios: 35/35
test_command: uv run pytest
test_exit_code: 0
test_output_hash: sha256:5230cdeb8688760cea2c4439cbcfd58a50587aa7a68000eb12da5d38e559815b
build_command: uv run mypy src
build_exit_code: 0
build_output_hash: sha256:049f51b850512be193c74d3fbb731e25fbc6374a66560d8ec0d6569d79c88ea6
```

## Verification Report

**Change**: mcp-jira-mvp
**Version**: PRD v1.0.0 (2026-08-19)
**Mode**: Standard (Strict TDD disabled)
**Commit range**: 1a6c0bb..7b9819b (6 commits: PR 1 toolchain bootstrap through PR 6 error-path suite + README)

### Completeness
| Metric | Value |
|--------|-------|
| Tasks total | 16 |
| Tasks complete | 16 |
| Tasks incomplete | 0 |

All 16 task checkboxes in `tasks.md` are `[x]` (Phase 1: 1.1–1.4, Phase 2: 2.1–2.3, Phase 3: 3.1–3.2, Phase 4: 4.1–4.2, Phase 5: 5.1–5.2, Phase 6: 6.1–6.3).

### Build & Tests Execution
**Build/type-check**: ✅ Passed — `uv run mypy src` → "Success: no issues found in 11 source files" (exit 0). `uv run ruff check` → "All checks passed!" (exit 0). Ruff target py310 + mypy python_version 3.10 (static proof of the 3.10 floor; runtime 3.10 interpreter not available in this environment).

**Tests**: ✅ 161 passed, 0 failed, 0 skipped (exit 0)
```text
uv run pytest
collected 161 items
161 passed, 1 warning in 3.49s   (Python 3.14.7, pytest-9.1.1)
```
The single warning is a third-party `pydantic_settings IncompleteFieldDefinitionWarning` emitted inside FastMCP internals — harmless, not from project code.

**Coverage**: ➖ Not available — no coverage tooling declared in `pyproject.toml`; the suite is behavior-focused (161 tests incl. an 8-tool × 6-status security sweep). No coverage threshold is specified anywhere in the specs/design, so this is not a gate.

### Runtime Harness Evidence
| Command | Exit | Result |
|---------|------|--------|
| `uv run pytest` | 0 | 161 passed |
| `uv run ruff check` | 0 | All checks passed |
| `uv run mypy src` | 0 | No issues in 11 source files |
| `uv run python -m mcp_jira --help` | 0 | CLI usage printed (run default + setup subcommand) |
| `uv run mcp-jira --help` | 0 | Console script works |
| `uv run mcp-jira setup --help` | 0 | Setup usage printed |
| `uv run mcp-jira setup` (no TTY) | 1 | Prints config path + guidance, exits non-zero (spec scenario) |
| `uv run python -c "from mcp.server.fastmcp import FastMCP; import httpx"` | 0 | FastMCP app constructs; httpx 0.28.1 |
| `uv sync --dry-run` | 0 | Lockfile up to date, 41 packages, "Would make no changes" |
| `uv run python -c "import fastmcp"` | 1 | Top-level `fastmcp` module absent (mcp 1.x layout — see WARNING-1) |

### Spec Compliance Matrix
Specs: `toolchain-bootstrap` (4 req / 6 scenarios), `server-config` (5 req / 12 scenarios), `jira-tools` (4 req / 10 scenarios), `error-handling` (4 req / 7 scenarios) — total 17 requirements / 35 scenarios.

| Requirement | Scenario | Test / Evidence | Result |
|-------------|----------|-----------------|--------|
| toolchain/uv-managed-project-manifest | Clean sync on runtime Python | `pyproject.toml` requires-python `>=3.10`; `uv sync --dry-run` no changes; Python 3.14.7 in pytest header | ✅ COMPLIANT |
| toolchain/uv-managed-project-manifest | Minimum Python floor | ruff `target-version = "py310"` + mypy `python_version = "3.10"` both clean; `from __future__ import annotations` throughout (static proof; no 3.10 runtime here) | ✅ COMPLIANT |
| toolchain/runtime-dependencies | Imports resolve | `from mcp.server.fastmcp import FastMCP; import httpx` exit 0; mcp+httpx declared in pyproject; literal top-level `import fastmcp` fails (mcp 1.x layout) — see WARNING-1 | ✅ COMPLIANT |
| toolchain/dev-tooling | Lint, type-check, and tests runnable | `uv run ruff check` 0; `uv run mypy src` 0; `uv run pytest` 161 passed | ✅ COMPLIANT |
| toolchain/project-layout-and-entry-point | Console script installed | `uv run mcp-jira --help` 0; `uv run mcp-jira setup --help` 0; `[project.scripts] mcp-jira = mcp_jira.cli:main` | ✅ COMPLIANT |
| toolchain/project-layout-and-entry-point | Mocked test suite runs | 161 passed offline via `httpx.MockTransport` (tests/conftest.py) | ✅ COMPLIANT |
| server-config/config-file-schema | Valid config loads | `tests/test_config.py::test_valid_config_loads`, `test_defaults_language_en_read_only_false`; server registers 9 tools | ✅ COMPLIANT |
| server-config/config-file-schema | Unknown language falls back to en | `test_config.py::test_unknown_language_falls_back_to_en`; `tests/test_server.py::test_unknown_language_falls_back_to_en` | ✅ COMPLIANT |
| server-config/config-file-schema | read_only defaults to false | `test_config.py::test_defaults_language_en_read_only_false` | ✅ COMPLIANT |
| server-config/environment-overrides | Env value wins | `test_config.py::test_env_overrides_file_values` | ✅ COMPLIANT |
| server-config/environment-overrides | File-only settings unchanged | `test_config.py::test_language_and_read_only_are_file_only` | ✅ COMPLIANT |
| server-config/startup-validation | Missing config | `test_config.py::test_missing_file_raises_config_missing`; `test_server.py::test_bad_config_fails_fast[absent/no_pat]` | ✅ COMPLIANT |
| server-config/startup-validation | Malformed JSON | `test_config.py::test_malformed_json_raises_config_invalid`, `test_non_object_json_raises_config_invalid`; `test_server.py::test_bad_config_fails_fast[malformed]` | ✅ COMPLIANT |
| server-config/startup-validation | Credential check fails | `test_server.py::test_myself_401_raises_auth_unauthorized` (raise occurs before any tool registers) | ✅ COMPLIANT |
| server-config/config-file-permissions | World-readable warning | `test_config.py::test_world_readable_warns_on_stderr` (+ `test_0600_no_warning`) | ✅ COMPLIANT |
| server-config/setup-wizard | Interactive success | `tests/test_wizard.py::test_interactive_success_writes_0600_config` (mode 0600 asserted) | ✅ COMPLIANT |
| server-config/setup-wizard | Connectivity failure | `test_wizard.py::test_connectivity_failure_reports_and_writes_nothing` (no file written, PAT not surfaced) | ✅ COMPLIANT |
| server-config/setup-wizard | Non-interactive without config | `test_wizard.py::test_non_interactive_prints_path_and_exits_nonzero`; runtime `uv run mcp-jira setup` exits 1 | ✅ COMPLIANT |
| jira-tools/tool-registration | All tools listed | `test_server.py::test_registers_all_nine_tools_with_en_names`; `test_read_only_still_registers_all_tools`; i18n `TOOL_IDS` = 9 | ✅ COMPLIANT |
| jira-tools/tool-contracts | Search caps max_results | `test_tools.py::test_search_defaults_and_caps_max_results` (500 → 100; default 50) | ✅ COMPLIANT |
| jira-tools/tool-contracts | get_issue includes transitions | `test_tools.py::test_get_issue_expands_transitions_and_selects_fields` (`expand=transitions` asserted) | ✅ COMPLIANT |
| jira-tools/tool-contracts | create_issue returns new key | `test_tools.py::test_create_issue_returns_key_and_resolves_fields` (`{key: "PROJ-2"}`) | ✅ COMPLIANT |
| jira-tools/tool-contracts | Transition by name | `test_tools.py::test_transition_by_name_and_by_id` (name "In Progress" → id 31; id "41" passthrough) | ✅ COMPLIANT |
| jira-tools/custom-field-resolution | Display name resolves to ID | `test_fields.py::test_resolve_display_name_to_id`; create payload uses customfield_10001 | ✅ COMPLIANT |
| jira-tools/custom-field-resolution | Raw ID passes through | `test_fields.py::test_resolve_raw_id_passes_through` (incl. id absent from map); `test_update_issue_raw_id_passes_through` | ✅ COMPLIANT |
| jira-tools/custom-field-resolution | Ambiguous name fails | `test_fields.py::test_resolve_ambiguous_name_fails`; `test_tools.py::test_get_issue_ambiguous_field_name_fails` (VALIDATION_ERROR) | ✅ COMPLIANT |
| jira-tools/read-only-mode | Mutation blocked | `test_tools.py::test_read_only_blocks_mutations_without_http`; `test_error_paths.py::test_read_only_guard_blocks_without_http_and_redacts` (no HTTP; READ_ONLY_MODE) | ✅ COMPLIANT |
| jira-tools/read-only-mode | Reads unaffected | `test_tools.py::test_read_only_reads_unaffected` | ✅ COMPLIANT |
| error-handling/error-taxonomy | 401 maps to AUTH_UNAUTHORIZED | `test_errors.py::test_map_401_auth_unauthorized`; `test_tools.py::test_get_issue_maps_http_errors[PROJ-401]`; sweep ×8 tools | ✅ COMPLIANT |
| error-handling/error-taxonomy | 429 surfaces Retry-After | `test_errors.py::test_map_429_surfaces_retry_after`; `test_client.py::test_429_never_retried` ("30s" in message) | ✅ COMPLIANT |
| error-handling/error-precedence | Auth wins over later codes | `test_client.py::test_401_wins_over_preceding_timeout`; `test_error_paths.py::test_401_wins_over_transport_timeout_through_tool` | ✅ COMPLIANT |
| error-handling/retry-policy | 5xx retried once | `test_client.py::test_5xx_retried_once_with_1s_backoff_then_server_error`; `test_error_paths.py::test_5xx_retried_once_through_tool` (2 calls, 1×1s sleep) | ✅ COMPLIANT |
| error-handling/retry-policy | 429 never auto-retried | `test_client.py::test_429_never_retried`; `test_error_paths.py::test_429_never_retried_through_tool` (1 call, 0 sleeps) | ✅ COMPLIANT |
| error-handling/logging-and-redaction | PAT never leaks | `test_client.py::test_logs_status_correlation_id_and_redacts_pat`, `test_never_logs_to_stdout`; sweep (8 tools × 6 statuses, PAT echoed by mock server in every payload — never in message or logs) | ✅ COMPLIANT |
| error-handling/logging-and-redaction | INTERNAL keeps stack local | `test_errors.py::test_map_unhandled_status_internal` (418 → INTERNAL, safe detail); `JiraError.__str__` = `code: message` only, no traceback surface | ✅ COMPLIANT |

**Compliance summary**: 35/35 scenarios compliant (see WARNING-1 for one caveated row).

### Correctness (Static Evidence)
| Requirement | Status | Notes |
|------------|--------|-------|
| §4.4 CONFIG_MISSING / CONFIG_INVALID fail fast, no tools | ✅ Implemented | config.py raises before client/tools exist; server raises before registration; CLI exits 1 (test_main_run_reports_startup_error_exit_nonzero) |
| §4.4 AUTH_UNAUTHORIZED (401, suggests re-setup) | ✅ Implemented | map_http_error branch 0; startup /myself check |
| §4.4 AUTH_FORBIDDEN (403, no retry) | ✅ Implemented | 403 branch; no retry path for 4xx |
| §4.4 NOT_FOUND (404, verbatim detail) | ✅ Implemented | errorMessages verbatim, "Resource not found" template |
| §4.4 VALIDATION_ERROR (400 errors dict verbatim) | ✅ Implemented | `_classify_400` errors-first; field errors joined verbatim |
| §4.4 JQL_INVALID (search 400, verbatim + endpoint fallback) | ✅ Implemented | errorMessages verbatim + search-endpoint fallback |
| §4.4 TRANSITION_INVALID (lists available) | ✅ Implemented | tools.transition_issue compares name/ID against fetched list; message lists names |
| §4.4 FIELD_NOT_EDITABLE | ⚠️ Partial | Code + template defined (i18n, precedence tuple), but mapper never emits it — read-only-field updates surface as VALIDATION_ERROR (same precedence class). See SUGGESTION-1. |
| §4.4 RATE_LIMITED (Retry-After surfaced, no auto-retry) | ✅ Implemented | `_retry_after` header parse; client never retries 4xx |
| §4.4 SERVER_ERROR (5xx, retried once then surfaced) | ✅ Implemented | client `_attempt` retry-once + 1s backoff |
| §4.4 NETWORK_ERROR (suggest curl) | ✅ Implemented | network_error() with URL + detail; transport errors mapped |
| §4.4 READ_ONLY_MODE (registered, always fails) | ✅ Implemented | `_guard()` raises before any HTTP; 9 tools still registered |
| §4.4 INTERNAL (safe detail only) | ✅ Implemented | fallback branch + FieldMap shape guard |
| §4.4 precedence order | ✅ Implemented | `ERROR_PRECEDENCE` tuple + branch order; test_error_precedence_matches_spec |
| Retry policy (never on AUTH/VALIDATION/NOT_FOUND/TRANSITION/READ_ONLY; no auto 429; once on 5xx/network) | ✅ Implemented | client.py `_attempt`; proven by call-count tests |
| Logging: stderr-only, PAT redacted, HTTP status + correlation id | ✅ Implemented | `_ensure_stderr_handler` → sys.stderr; `redact_pat`; `x-arequestid`/`x-request-id` logged; stdout assert-empty test |
| No stack traces / raw HTTP dumps surfaced | ✅ Implemented | JiraError message only; INTERNAL template "This is a bug — report it" |
| i18n en/es: names/descriptions + error templates; verbatim untranslated | ✅ Implemented | i18n.py tables; test_verbatim_detail_not_translated; es covers all codes |

### Coherence (Design)
| Decision | Followed? | Notes |
|----------|-----------|-------|
| Flat `src/mcp_jira/` package, 11 modules | ✅ Yes | Module set matches design file-change table exactly |
| Synchronous httpx.Client + sync tool handlers | ✅ Yes | FastMCP runs sync tools natively; no asyncio in handlers |
| Errors raised, not returned | ✅ Yes | Tools raise `JiraError`; FastMCP surfaces `str(JiraError)` |
| Field-map fetch failure fails fast at startup | ✅ Yes | server.py after `/myself`; test_field_cache_failure_fails_fast |
| `allowed_values` normalized to `[]` | ✅ Yes | fields.py `_add`; test_allowed_values_normalized_to_list |
| HTTP 400 discrimination by payload shape (errors dict → VALIDATION; search errorMessages → JQL; endpoint fallback) | ✅ Yes | `_classify_400` matches design pseudocode; discriminator tests |
| `es` scope: descriptions + surfaced messages only | ✅ Yes | i18n tables; Jira detail untranslated |
| Retry policy lives in client.py only | ✅ Yes | `_attempt` loop; no retry decorators elsewhere |
| Console script `mcp-jira` → `cli:main`, default `run` + `setup` | ✅ Yes | pyproject scripts + cli.py; `python -m` mirrors it |

### Issues Found
**CRITICAL**: None

**WARNING**:
- WARNING-1 (spec wording, non-blocking): toolchain-bootstrap §runtime-dependencies scenario "Imports resolve" literally executes `import fastmcp, httpx`. The project pins `mcp>=1.0,<2` (design decision documented in pyproject comment: "mcp 2.x dropped FastMCP (breaking SDK rewrite); design targets FastMCP"), and in that layout FastMCP imports from `mcp.server.fastmcp` — which I verified at runtime (exit 0; FastMCP app constructs; httpx 0.28.1) and which the entire 161-test suite exercises. The literal top-level `import fastmcp` fails (`ModuleNotFoundError`). The requirement intent (declare `mcp` (FastMCP) + `httpx`; they resolve) is fully met; recommend amending the scenario/test wording to `from mcp.server.fastmcp import FastMCP` rather than changing the dependency.

**SUGGESTION**:
- SUGGESTION-1: `FIELD_NOT_EDITABLE` is defined (precedence tuple, EN/ES templates) but never emitted — `map_http_error` has no branch producing it; a read-only-field update surfaces as `VALIDATION_ERROR` with the field errors verbatim, which satisfies §4.4 precedence (`VALIDATION_*` class) and the "no retry with same field" behavior. If the specific code is wanted, add a payload discriminator on the update endpoint.
- SUGGESTION-2: No coverage metric or gate configured; the suite is deliberately behavior-focused. Add `pytest-cov` with a threshold only if a coverage gate becomes a project requirement.
- SUGGESTION-3: The suite emits one `pydantic_settings IncompleteFieldDefinitionWarning` from FastMCP internals (third-party `lifespan` field). Harmless; can be silenced via filterwarnings if desired.

### Verdict
**PASS** — 16/16 tasks complete, 17/17 requirements and 35/35 scenarios verified against passing runtime tests, lint/type/build/CLI gates all green (exit 0), zero blockers, zero critical findings. One non-blocking spec-wording warning (WARNING-1) and three suggestions. Archive-ready.
