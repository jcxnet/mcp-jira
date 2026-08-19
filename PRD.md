# Product Requirements Document (PRD)
## mcp-jira — MCP Server for Self-Hosted Jira (Data Center)

| | |
|---|---|
| **Versión** | 1.0.0 |
| **Fecha** | 2026-08-19 |
| **Estado** | Draft |
| **Owner** | jcxnet |

---

## 1. Executive Summary

### 1.1 Problem Statement

AI agents (OpenCode, Claude Desktop, Claude CLI, Cursor, etc.) cannot natively interact with a self-hosted Jira Data Center instance. Today, any Jira operation from an agent requires manual steps or ad-hoc scripting, and there is no standard, reusable bridge between agent tools and Jira's REST API.

### 1.2 Proposed Solution

A **Model Context Protocol (MCP) server** (`mcp-jira`) that exposes a focused set of Jira issue operations as MCP tools. It authenticates against a self-hosted **Jira Data Center 9.0+** instance using the **user's Personal Access Token (PAT)**, configured via a local config file. Any MCP-capable agent connects over **stdio** and gains native Jira tool access.

### 1.3 Success Criteria

| # | KPI | Target |
|---|---|---|
| SC-1 | Tool coverage | 9 tools (search, get, create, update, transition, comment, comments, projects, list_fields) working against Jira DC |
| SC-2 | Integration ease | Agent connects with a single `mcpServers` JSON block + config file; no server code changes per agent; one-command `mcp-jira setup` wizard creates the config |
| SC-3 | Auth security | PAT never logged, never returned in tool output, stored only in the config file |
| SC-4 | Error clarity | Every Jira API error (401/403/404/429/validation) surfaces as a readable MCP tool error with a stable §4.4 error code, not a raw stack trace |
| SC-5 | Zero extra infra | Runs locally via stdio; no database, no web server, no cloud dependencies |

---

## 2. User Experience & Functionality

### 2.1 User Personas

| Persona | Description | Need |
|---|---|---|
| **Developer/Agent Operator** | Runs OpenCode, Claude Desktop, or another MCP client | Wants Jira tools available inside their agent without leaving the conversation |
| **Team Member** | Uses an agent to triage/track issues | Wants to search, comment, and update issues naturally in natural language |

### 2.2 User Stories

- **US-1**: As an agent user, I want to **search issues by JQL** so that I can find relevant work without visiting the Jira UI.
- **US-2**: As an agent user, I want to **get a single issue by key** so that I can inspect its current state, fields, and transitions.
- **US-3**: As an agent user, I want to **create an issue** so that I can capture work from within the agent conversation.
- **US-4**: As an agent user, I want to **update issue fields** so that I can adjust status metadata (summary, description, custom fields).
- **US-5**: As an agent user, I want to **transition an issue** (e.g., In Progress → Done) so that I can advance workflow state.
- **US-6**: As an agent user, I want to **add a comment** and **list comments** so that I can record and read discussion context.
- **US-7**: As an agent user, I want to **list projects** so that I can discover valid project keys/issue types before creating issues.
- **US-8**: As an agent operator, I want to configure the Jira URL + PAT in **one config file** so that I can set up the server once and reuse it across agents.
- **US-9**: As an agent operator, I want to run an **interactive setup wizard** (`mcp-jira setup`) so that I don't have to hand-edit JSON or remember the config path.
- **US-10**: As an agent user, I want to work with **all custom fields** (by name or `customfield_XXXXX` ID) in create/update/get so that project-specific data is usable.
- **US-11**: As an agent operator, I want **tool descriptions in my language** (English default, Spanish optional) so that agent-facing labels match the team.
- **US-12**: As an agent operator, I want an optional **read-only safety mode** so that shared setups cannot mutate issues by accident.

### 2.3 Acceptance Criteria

- **AC-US-1**: `search_issues` accepts a JQL string + optional `max_results` (default 50, cap 100); returns key, summary, status, assignee, priority, and issue type per issue.
- **AC-US-2**: `get_issue` returns all requested fields plus `transitions` available to the authenticated user.
- **AC-US-3**: `create_issue` accepts `project_key`, `issue_type`, `summary`, and optional `description`; returns the new issue key on success.
- **AC-US-4**: `update_issue` accepts `issue_key` and field name/value map; errors clearly if a field is not editable.
- **AC-US-5**: `transition_issue` accepts `issue_key` and target transition name or ID; errors clearly on invalid workflow transition.
- **AC-US-6**: `add_comment` returns the created comment; `get_comments` returns comment list (body, author, created).
- **AC-US-7**: `list_projects` returns project key, name, and issue type names.
- **AC-US-8**: Config file (`~/.config/mcp-jira/config.json`) holds `jira_url` and `jira_pat`; server refuses to start if either is missing or the URL is unreachable; startup validates credentials with a lightweight `GET /rest/api/2/myself` call.
- **AC-US-9**: `mcp-jira setup` prompts for URL and PAT (hidden input), tests connectivity via `/myself`, writes `config.json` with `0600` permissions, and reports success/failure clearly; non-interactive invocation prints the config path and exits non-zero with guidance if config is missing.
- **AC-US-10**: `list_fields` returns every field (id, name, custom flag, type, allowed values); `get_issue`/`create_issue`/`update_issue` accept custom fields by display name (resolved to ID via the cached field map) or raw `customfield_XXXXX` ID.
- **AC-US-11**: Config `language` key (`en` default, `es` optional) switches tool names/descriptions; unknown values fall back to `en`.
- **AC-US-12**: Config `read_only` key (default `false`) — when `true`, `create_issue`, `update_issue`, `transition_issue`, and `add_comment` are registered as present but immediately return a clear "read-only mode" error.
- **AC-ALL**: All tools return structured JSON; every Jira API error maps to a human-readable MCP error message including HTTP status and server-provided message.

### 2.4 Non-Goals

- **Not** building an admin/UI dashboard — configuration is file-based.
- **Not** supporting Jira Cloud (different auth: API tokens), Jira Server < 9.0, or OAuth2 flows.
- **Not** implementing sprint/board operations, agile metrics, attachments, watchers, or time tracking in the MVP.
- **Not** storing issue data locally or providing offline access — every call is live against Jira.
- **Not** shipping a multi-user authentication service (token is per-installation config).

---

## 3. AI System Requirements

### 3.1 Tool Requirements

| Tool | Inputs | Output |
|---|---|---|
| `search_issues` | jql, max_results | `{ issues: [{key, summary, status, assignee, priority, issue_type}] }` |
| `get_issue` | issue_key | `{ key, summary, description, status, assignee, priority, fields (incl. all custom fields), transitions }` |
| `create_issue` | project_key, issue_type, summary, description, fields (custom by name or ID) | `{ key }` |
| `update_issue` | issue_key, fields (custom by name or ID) | `{ updated: true }` |
| `transition_issue` | issue_key, transition | `{ transitioned: true }` |
| `add_comment` | issue_key, body | `{ id, created }` |
| `get_comments` | issue_key | `{ comments: [{id, author, created, body}] }` |
| `list_projects` | — | `{ projects: [{key, name, issue_types}] }` |
| `list_fields` | — | `{ fields: [{id, name, custom, type, allowed_values}] }` |

**Required API surface (Jira Data Center REST v2):**

- `GET /rest/api/2/search` (JQL)
- `GET /rest/api/2/issue/{key}` (+ `?expand=transitions`)
- `POST /rest/api/2/issue`
- `PUT /rest/api/2/issue/{key}`
- `POST /rest/api/2/issue/{key}/transitions`
- `POST /rest/api/2/issue/{key}/comment`
- `GET /rest/api/2/issue/{key}/comment`
- `GET /rest/api/2/project`
- `GET /rest/api/2/field` (field map for custom-field name resolution, cached at startup)
- `GET /rest/api/2/myself` (startup credential check)

### 3.2 Evaluation Strategy

- **Smoke test (manual):** configure against a real DC instance; run each of the 8 tools once; verify outputs and that a wrong/expired PAT produces a clear 401 message.
- **Mock test (automated):** unit tests against a mocked HTTP layer covering success + error paths (401, 403, 404, 429, invalid JQL, invalid transition) and asserting each maps to the §4.4 error code and message.
- **Security check:** scan logs/output for token leakage across all tools.

---

## 4. Technical Specifications

### 4.1 Architecture Overview

```
[OpenCode / Claude Desktop / any MCP client]
                    │  stdio (MCP protocol)
                    ▼
        ┌─────────────────────────┐
        │  mcp-jira (Python)      │
        │  FastMCP server         │
        │  8 tools                │
        │  config file loader     │
        └──────────┬──────────────┘
                   │ HTTPS (REST v2, Bearer PAT)
                   ▼
        ┌─────────────────────────┐
        │  Jira Data Center 9.0+  │
        │  (self-hosted)          │
        └─────────────────────────┘
```

- **Runtime:** Python 3.10+, official `mcp` Python SDK (FastMCP), `httpx` for HTTP.
- **Transport:** stdio only (no web server, no DB, no Docker requirement).
- **Config:** `~/.config/mcp-jira/config.json` → `{ "jira_url": "https://jira.example.com", "jira_pat": "<PAT>", "language": "en", "read_only": false }`; env vars `JIRA_URL` / `JIRA_PAT` override the file (12-factor friendly); `language` (`en`/`es`) and `read_only` are file-only settings.

### 4.2 Integration Points

- **Jira REST v2 API** — the stable, fully supported API surface on Data Center.
- **MCP stdio transport** — declared via the client's `mcpServers` config (examples in README for OpenCode, Claude Desktop, and Claude CLI).

### 4.3 Security & Privacy

- PAT is read at startup only; never echoed, logged, or included in tool responses.
- All HTTP via HTTPS; requests carry `Authorization: Bearer <PAT>`.
- Config file permissions: written with `0600` by the setup wizard; warn (not block) if an existing `config.json` is world-readable.
- Follow Jira's rate limiting (429 handling with Retry-After surfaced to the agent).
- No issue content is stored or transmitted anywhere except Jira and the requesting agent.

### 4.4 Error Handling & Error Model

Every tool error returns a structured MCP error message with a **stable error code**, a **human-readable message** (localized to `language`), and — where useful — the **Jira-provided detail verbatim**. No raw stack traces or HTTP dumps are ever surfaced to the agent.

| Error code | Source | Detection | Surfaced message (en) | Behavior |
|---|---|---|---|---|
| `CONFIG_MISSING` | Server startup | `config.json` absent or missing `jira_url`/`jira_pat` | "Configuration missing. Run `mcp-jira setup` or create `~/.config/mcp-jira/config.json`." | Fail fast; do not start tools |
| `CONFIG_INVALID` | Server startup | Malformed JSON, empty URL, non-bool `read_only`, unsupported `language` | "Invalid configuration: <detail>. Fix config or re-run `mcp-jira setup`." | Fail fast; do not start tools |
| `AUTH_UNAUTHORIZED` | Any call | HTTP 401 | "Authentication failed. Your PAT is invalid or expired. Generate a new one in Jira admin → PATs." | Readable error; suggest re-running `mcp-jira setup` |
| `AUTH_FORBIDDEN` | Any call | HTTP 403 | "You don't have permission for this operation on the target resource." | Readable error; no retry |
| `NOT_FOUND` | Any call | HTTP 404 (issue/project/field/comment) | "Resource not found: <resource type> <id>." | Readable error; no retry |
| `VALIDATION_ERROR` | Create/update/search | HTTP 400; Jira validation payload | "Invalid request: <Jira error messages, joined verbatim>." | Include all field-level errors from Jira's `errors` map |
| `JQL_INVALID` | `search_issues` | HTTP 400 with JQL error | "Invalid JQL: <Jira's errorMessages verbatim>." | Hint at common fixes (quote strings, correct field names) |
| `TRANSITION_INVALID` | `transition_issue` | Transition not in `expand=transitions` list | "Transition '<name>' is not available. Available: <list>." | List valid transitions so the agent can retry correctly |
| `FIELD_NOT_EDITABLE` | `update_issue` | Jira returns field as read-only in validation | "Field '<name>' is not editable in this issue/status." | No retry with same field |
| `RATE_LIMITED` | Any call | HTTP 429 + `Retry-After` header | "Jira rate limit hit. Retry after <seconds>s." | Surface Retry-After; do NOT auto-retry (avoids hammering) |
| `SERVER_ERROR` | Any call | HTTP 5xx | "Jira server error (<status>). Jira may be down or overloaded." | No retry loop; agent decides |
| `NETWORK_ERROR` | Any call | Connection refused, timeout, TLS failure, DNS | "Could not reach Jira at <url>: <detail>." | Check URL reachability; suggest `curl` of base URL |
| `READ_ONLY_MODE` | Mutating tools (`create_issue`, `update_issue`, `transition_issue`, `add_comment`) | `read_only: true` in config | "Read-only mode is enabled. This mutation is blocked." | Tool stays registered but always fails with this code |
| `INTERNAL` | Any call | Unexpected exception, schema mismatch | "Unexpected error: <safe detail>. This is a bug — report it." | Never expose stack trace or PAT; log locally |

**Error precedence** (when multiple apply): `CONFIG_*` > `AUTH_*` > `RATE_LIMITED` > `VALIDATION_*` > `NOT_FOUND` > `SERVER_ERROR` > `NETWORK_ERROR` > `INTERNAL`.

**Retry policy:**

- `AUTH_*`, `VALIDATION_*`, `NOT_FOUND`, `TRANSITION_INVALID`, `FIELD_NOT_EDITABLE`, `READ_ONLY_MODE`: **never retry** (deterministic; agent must change input or config).
- `RATE_LIMITED`: no automatic retry; surface `Retry-After` so the agent/operator decides.
- `SERVER_ERROR`, `NETWORK_ERROR`: at most **one** automatic retry after a short backoff (1s), then surface the error. No infinite loops.

**Local logging:** the server logs (to stderr, never stdout — stdout is the MCP transport) the full error with HTTP status and correlation request ID when Jira provides one; the PAT is redacted from all logs.

---

## 5. Risks & Roadmap

### 5.1 Technical Risks

| Risk | Mitigation |
|---|---|
| Jira DC REST v2 deprecation | v2 is fully supported on DC 9+; monitor Atlassian's v3 DC roadmap before a future migration |
| Custom fields / field name mapping complexity | Field map fetched from `GET /rest/api/2/field` at startup and cached; custom fields usable by display name or raw ID, so no per-project config is needed |
| PAT expiry / revocation | Errors surface clearly; README documents where to rotate tokens in Jira admin |
| Agents passing bad JQL | Validate response errors and surface Jira's JQL error message verbatim |
| Concurrent agent calls | stateless per-request; no shared state — safe for parallel tool calls |

### 5.2 Phased Rollout

| Phase | Scope |
|---|---|
| **MVP (v1.0)** | 9 tools, `mcp-jira setup` wizard + CLI, config file, stdio, PAT auth, README for OpenCode + Claude Desktop + Claude CLI |
| **v1.1** | Attachments, watchers, assignee helpers, issue links, verbose field output option |
| **v1.2** | HTTP/SSE transport option for remote agents; optional Docker image |

---

## 6. Decisions Log (resolved)

| Question | Decision |
|---|---|
| Custom fields in MVP | **Use all available custom fields** — `list_fields` tool + name/ID resolution for get/create/update |
| Tool description language | **User-defined** — `language: en` default, `es` optional in config |
| Read-only safety mode | **Add it** — `read_only` config flag (default `false`), when `true` mutating tools return a clear read-only error |
