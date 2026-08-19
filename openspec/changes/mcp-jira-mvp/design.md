# Design: mcp-jira MVP

## Technical Approach

Greenfield Python MCP stdio server: FastMCP app + synchronous `httpx.Client` with `Authorization: Bearer <PAT>`. Config is loaded once and validated at startup (fail fast, no tools registered on `CONFIG_*` / `AUTH_UNAUTHORIZED`), the field map is fetched and cached at startup, every tool call funnels through a shared error mapper implementing §4.4 (codes, precedence, retry), and the `mcp-jira setup` wizard is a CLI subcommand. The whole HTTP surface is testable offline via `httpx.MockTransport`. Satisfies `toolchain-bootstrap`, `server-config`, `jira-tools`, `error-handling` specs; maps 1:1 to proposal approach.

## Architecture Decisions

### Decision: Package layout — flat `src/mcp_jira/` package

| Option | Tradeoff | Decision |
|---|---|---|
| Flat modules per concern | Every module thin; server.py stays a registrar | **Chosen** |
| `tools/` subpackage with one module per tool | 9 files for ~30-line wrappers | Rejected — ceremony, no shared code |
| All-in-one `main.py` | One file, but >400 lines, hard to test | Rejected |

Modules: `__init__.py` (version), `__main__.py` (`python -m mcp_jira`), `cli.py` (argparse: default `run`, `setup`), `server.py` (FastMCP app + startup validation), `tools.py` (9 handlers + read-only guard), `config.py` (Settings + loader), `wizard.py` (setup prompts/write), `client.py` (httpx wrapper + retry), `errors.py` (codes + mapper), `fields.py` (FieldMap), `i18n.py` (en/es tables).

### Decision: Synchronous client, synchronous tool handlers

| Option | Tradeoff | Decision |
|---|---|---|
| Sync `httpx.Client` + sync tools | FastMCP runs sync tools natively; no asyncio in handlers | **Chosen** |
| `AsyncClient` + async tools | Marginal benefit, no concurrency requirement (§5.1 "stateless per-request") | Rejected — complexity without payoff |

### Decision: Errors raised, not returned

Tool wrappers raise `JiraError`; FastMCP surfaces `str(JiraError)` as the MCP tool error. Alternative (result dicts with `error` field) rejected — MCP has native error reporting; spec requires code + message, never a stack.

### Decision: Startup field-map fetch failure fails fast

`GET /field` failure at startup stops the server with the mapped §4.4 code (like `/myself`). Rationale: without the map, the custom-field contract (§3.1, custom-field resolution) cannot be honored; lazy fallback would surface `INTERNAL` later.

### Decision (Risk 1): `allowed_values` normalized to `[]`

| Option | Tradeoff | Decision |
|---|---|---|
| Normalize null/absent → `[]` at list_fields mapping | Stable contract `allowed_values: list` | **Chosen** |
| Fetch options from create-meta | Needs project+issueType context, extra endpoint outside §3.1 | Rejected for MVP — document in tool description |

### Decision (Risk 2): HTTP 400 discrimination by payload shape

`map_http_error` uses payload shape, not just status: (1) non-empty `errors` dict → `VALIDATION_ERROR` (field errors verbatim); (2) else non-empty `errorMessages` list on the search endpoint → `JQL_INVALID` (messages + hints); (3) fallback by endpoint: search → `JQL_INVALID`, other → `VALIDATION_ERROR`. Precedence `VALIDATION_*` > `NOT_FOUND` when both appear.

### Decision (Risk 3): `es` localization scope — descriptions + surfaced messages only

`i18n.py` holds en/es tables: tool names/descriptions at registration, and error message templates keyed by code. Jira-provided verbatim details, config keys, log lines, and code identifiers stay untranslated. Unknown `language` falls back to `en` (spec).

### Decision: Retry policy lives in `client.py` only

One wrapper: retry at most once after 1s backoff on `5xx` or `httpx` transport errors; never on 4xx (incl. 429); 401 wins over a concurrent timeout (precedence). No retry decorator, no per-tool retry.

## Data Flow

```
MCP client ──stdio──► FastMCP (server.py)
                        │ tool call → handler (tools.py)
                        ▼
              read_only guard ──true──► READ_ONLY_MODE (no HTTP)
                        ▼
              FieldMap.resolve(fields) ──ambiguous──► VALIDATION_ERROR
                        ▼
              JiraClient.request() (Bearer PAT, retry once on 5xx/network)
                        ▼
              Jira DC REST v2 (HTTPS)
                        │ 200 → mapped structured JSON
                        │ 4xx/5xx/network → errors.py mapper → JiraError{code, message}
                        ▼
              tool result  |  tool error (localized, PAT-redacted, no stack)
```

Startup sequence: load config (file → env override → validate) → `CONFIG_MISSING`/`CONFIG_INVALID` exit non-zero, no tools; world-readable config → stderr warning, continue; `GET /myself` → 401 ⇒ `AUTH_UNAUTHORIZED`, no tools; `GET /field` → cache map (failure fails fast); register 9 tools; serve.

## File Changes

| File | Action | Description |
|---|---|---|
| `pyproject.toml` | Create | uv manifest, `requires-python >=3.10`, deps `mcp`+`httpx`, dev `pytest`/`ruff`/`mypy`, console script `mcp-jira` |
| `src/mcp_jira/__init__.py` | Create | `__version__` |
| `src/mcp_jira/__main__.py` | Create | `python -m mcp_jira` → run |
| `src/mcp_jira/cli.py` | Create | argparse: default run, `setup` subcommand |
| `src/mcp_jira/server.py` | Create | FastMCP app, startup validation, registration |
| `src/mcp_jira/tools.py` | Create | 9 handlers, read-only guard |
| `src/mcp_jira/config.py` | Create | Settings dataclass, loader (file+env), validation, perms warning |
| `src/mcp_jira/wizard.py` | Create | prompts (hidden PAT), `/myself` test, 0600 write, non-interactive guidance |
| `src/mcp_jira/client.py` | Create | httpx wrapper, retry-once, PAT redaction |
| `src/mcp_jira/errors.py` | Create | codes, `JiraError`, mapper incl. 400 discriminator |
| `src/mcp_jira/fields.py` | Create | FieldMap fetch/resolve/ambiguity |
| `src/mcp_jira/i18n.py` | Create | en/es description + message tables |
| `tests/` | Create | conftest + fixtures + per-module suites (below) |
| `README.md` | Create | setup + 3 `mcpServers` blocks |
| `.gitignore` | Create | venv, caches |

## Interfaces / Contracts

```python
# errors.py
@dataclass(frozen=True)
class JiraError(Exception):
    code: str          # §4.4 code, e.g. "RATE_LIMITED"
    message: str       # localized, PAT-redacted, no stack

# discriminator core (non-obvious, per Risk 2)
def _classify_400(body: dict, endpoint: str) -> str:
    if body.get("errors"):        return "VALIDATION_ERROR"
    if body.get("errorMessages") and endpoint == "search":
        return "JQL_INVALID"
    return "JQL_INVALID" if endpoint == "search" else "VALIDATION_ERROR"
```

```python
# config.py
@dataclass(frozen=True)
class Settings:
    jira_url: str
    jira_pat: str
    language: str = "en"      # es allowed; unknown → en
    read_only: bool = False
```

## Testing Strategy

| Layer | What to Test | Approach |
|---|---|---|
| Unit | config load/validate/env-override/perms; i18n fallback; FieldMap resolve/ambiguity; redaction | pure functions, no HTTP |
| Integration | every tool success + error path (401/403/404/429/400-JQL/400-validation/500); 400 discriminator; retry-once + 1s backoff; 429 never retried; read-only guard; precedence | `httpx.MockTransport` fixtures keyed by (method, url, payload) in `conftest.py`; assert `JiraError.code` |
| E2E | none automated | manual smoke against real DC (§3.2) |

## Threat Matrix

N/A — no routing, shell command, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary. (Setup writes a `0600` config file; permissions are a spec concern, not a process boundary.)

## Migration / Rollout

No migration required — greenfield; config is user-owned, outside the repo. Rollback = delete `src/`, `tests/`, `pyproject.toml` (proposal rollback plan).

## Open Questions

None blocking.
