# Tasks: mcp-jira MVP

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~1,800 (16 files: ~950 src + ~550 tests + ~280 config/README/gitignore) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 → PR 2 → PR 3 → PR 4 → PR 5 → PR 6 |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Toolchain bootstrap + package skeleton | PR 1 | `uv run ruff check && uv run mypy src && uv run pytest` | `uv sync` then `uv run mcp-jira setup --help` exits 0 | delete `pyproject.toml`, `.gitignore`, `src/mcp_jira/__init__.py`, `__main__.py`, `tests/conftest.py` |
| 2 | Error model + config + i18n | PR 2 | `uv run pytest tests/test_errors.py tests/test_config.py tests/test_i18n.py` | N/A — pure functions, no HTTP boundary | remove `errors.py`, `config.py`, `i18n.py` + their tests |
| 3 | HTTP client + field map | PR 3 | `uv run pytest tests/test_client.py tests/test_fields.py` | N/A — MockTransport only; real DC smoke deferred to post-setup manual | remove `client.py`, `fields.py` + their tests |
| 4 | 9 tools + server + error-path suite | PR 4 | `uv run pytest tests/test_tools.py tests/test_server.py` | N/A — MockTransport; manual smoke needs live DC (§3.2, not automated) | remove `tools.py`, `server.py` + tool/server tests |
| 5 | CLI + setup wizard | PR 5 | `uv run pytest tests/test_cli.py tests/test_wizard.py` | `uv run mcp-jira setup --help`; non-interactive run prints path, exits non-zero | remove `cli.py`, `wizard.py` + their tests |
| 6 | Error-path coverage + README + final gate | PR 6 | `uv run ruff check && uv run mypy src && uv run pytest` | `uv run python -m mcp_jira --help` | revert README/`.gitignore`/test additions |

## Phase 1: Foundation — Toolchain Bootstrap

- [x] **1.1** Create `pyproject.toml` — uv manifest: `requires-python = ">=3.10"`, runtime deps `mcp` + `httpx`, dev deps `pytest`/`ruff`/`mypy`, `[project.scripts] mcp-jira = mcp_jira.cli:main`, ruff/mypy config.
  **Deps**: none. **AC**: toolchain-bootstrap §uv-managed manifest, §runtime deps, §dev tooling, §entry point (all scenarios). **Tests**: `uv sync` clean; `uv run ruff check`/`uv run mypy src`/`uv run pytest` exit 0 on clean tree.
- [x] **1.2** Create `.gitignore` — venv, `__pycache__`, `.ruff_cache`, `.mypy_cache`, `.pytest_cache`.
  **Deps**: 1.1. **AC**: repo hygiene. **Tests**: none (trivial).
- [x] **1.3** Create `src/mcp_jira/__init__.py` (`__version__`) and `src/mcp_jira/__main__.py` (`python -m mcp_jira` → cli run).
  **Deps**: 1.1. **AC**: package importable; `__main__` entry present. **Tests**: import smoke in conftest.
- [x] **1.4** Create `tests/conftest.py` — `httpx.MockTransport` fixture keyed by (method, url, payload) serving §3.1 endpoints + error payloads (401/403/404/429/400-JQL/400-validation/500).
  **Deps**: 1.1. **AC**: toolchain §mocked suite scenario — offline tests runnable. **Tests**: fixture used by every later suite.

## Phase 2: Config & Error Foundation

- [x] **2.1** Create `src/mcp_jira/errors.py` — §4.4 code constants, frozen `JiraError(code, message)`, `_classify_400` discriminator (errors dict → VALIDATION_ERROR; errorMessages+search → JQL_INVALID; endpoint fallback), `map_http_error` with precedence CONFIG > AUTH > RATE_LIMITED > VALIDATION > NOT_FOUND > SERVER > NETWORK > INTERNAL, `redact_pat` helper.
  **Deps**: none. **AC**: error-handling §taxonomy (401→AUTH_UNAUTHORIZED, 429 surfaces Retry-After), §precedence (auth wins over timeout), §retry table. **Tests**: unit — discriminator branches, precedence ordering, redaction.
- [x] **2.2** Create `src/mcp_jira/config.py` — frozen `Settings(jira_url, jira_pat, language="en", read_only=False)`, loader (file `~/.config/mcp-jira/config.json` → env override `JIRA_URL`/`JIRA_PAT` → validate), fail-fast `CONFIG_MISSING`/`CONFIG_INVALID`, unknown language → en, world-readable perms warning to stderr.
  **Deps**: 2.1. **AC**: server-config §schema, §env overrides, §startup validation, §permissions (all scenarios). **Tests**: unit — valid/missing/malformed, env wins, file-only settings, perms warning.
- [x] **2.3** Create `src/mcp_jira/i18n.py` — en/es tables: tool names/descriptions + error message templates keyed by code; unknown language falls back to en; Jira verbatim detail/codes/keys untranslated.
  **Deps**: 2.1. **AC**: server-config §unknown language → en; design Risk 3 scope. **Tests**: unit — fallback, both locales render.

## Phase 3: Client & Field Map

- [x] **3.1** Create `src/mcp_jira/client.py` — `httpx.Client` with `Authorization: Bearer <PAT>`, retry-at-most-once after 1s on 5xx/network, never on 4xx incl. 429, 401 wins over concurrent timeout, stderr-only logging with PAT redaction + HTTP status + correlation ID.
  **Deps**: 2.1. **AC**: error-handling §retry (5xx retried once then SERVER_ERROR; 429 never auto-retried), §logging (PAT never leaks, stderr only). **Tests**: integration — retry count, 1s backoff, 429 no-retry, redaction in logs.
- [x] **3.2** Create `src/mcp_jira/fields.py` — `FieldMap`: fetch `GET /rest/api/2/field` at startup, cache; `resolve()` by display name or raw `customfield_XXXXX`; ambiguous name → `VALIDATION_ERROR`.
  **Deps**: 2.1. **AC**: jira-tools §custom-field resolution (name→ID, raw ID passthrough, ambiguous fails). **Tests**: unit — resolve both paths + ambiguity.

## Phase 4: Tools & Server

- [ ] **4.1** Create `src/mcp_jira/tools.py` — 9 handlers per §3.1 contract table (search caps max_results at 100, get_issue `expand=transitions`, create returns `{key}`, transition by name or ID, list_fields `allowed_values` normalized to `[]`); read-only guard raising `READ_ONLY_MODE` (no HTTP) on the 4 mutating tools; FieldMap resolution in get/create/update.
  **Deps**: 2.1, 2.3, 3.1, 3.2. **AC**: jira-tools §tool contracts scenarios + §read-only mode scenarios (mutation blocked no HTTP, reads unaffected). **Tests**: integration — success path per tool via MockTransport.
- [ ] **4.2** Create `src/mcp_jira/server.py` — FastMCP app; startup sequence: load config (fail fast `CONFIG_*`, no tools) → `GET /myself` (401 ⇒ `AUTH_UNAUTHORIZED`, no tools) → `GET /field` cache (failure fails fast) → register 9 tools with `i18n` names/descriptions per `language`.
  **Deps**: 2.2, 2.3, 3.1, 3.2, 4.1. **AC**: server-config §startup validation scenarios; jira-tools §all tools listed. **Tests**: integration — tool list contains 9; CONFIG_MISSING/AUTH_UNAUTHORIZED expose zero tools.

## Phase 5: CLI & Wizard

- [ ] **5.1** Create `src/mcp_jira/cli.py` — argparse: default `run` (start server), `setup` subcommand; wired to console script.
  **Deps**: 4.2, 5.2. **AC**: toolchain §console script — `uv run mcp-jira setup --help` exits 0. **Tests**: CLI parsing via subprocess or argparse capture.
- [ ] **5.2** Create `src/mcp_jira/wizard.py` — prompt URL + hidden PAT (`getpass`), `/myself` connectivity test, write config with `0600` (`os.chmod`), report success/failure; non-interactive (no TTY, no config) prints config path + guidance and exits non-zero; nothing written on connectivity failure.
  **Deps**: 2.1, 2.2. **AC**: server-config §setup wizard scenarios (interactive 0600 + success report; connectivity failure nothing written; non-interactive path + non-zero exit). **Tests**: unit — 0600 mode asserted, non-interactive exit code, no write on failure.

## Phase 6: Testing & Docs

- [ ] **6.1** Mocked error-path suite — every tool error path: 401/403/404/429/400-JQL/400-validation/500 map to §4.4 codes; 400 discriminator; precedence; retry-once; 429 never retried; read-only guard; PAT-leak security check across logs and surfaced errors.
  **Deps**: 4.1, 4.2. **AC**: error-handling scenarios + proposal §success criteria (mocked suite covers all, no stack/PAT surfaced). **Tests**: `uv run pytest` — assert `JiraError.code` per path.
- [ ] **6.2** Create `README.md` — install (`uv sync`), `mcp-jira setup`, config schema, error codes table, `mcpServers` blocks for OpenCode, Claude Desktop, Claude CLI, token rotation note.
  **Deps**: 1.1, 5.2. **AC**: proposal §success criteria — working mcpServers blocks for 3 agents; toolchain §console script scenario. **Tests**: none — doc artifact.
- [ ] **6.3** Final gate — `uv run ruff check && uv run mypy src && uv run pytest` all green; confirm `uv run python -m mcp_jira --help` works; record manual smoke checklist (real DC, §3.2) as out-of-band.
  **Deps**: all. **AC**: toolchain §dev tooling scenario; proposal success criteria. **Tests**: full suite green.
