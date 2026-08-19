# mcp-jira

MCP stdio server exposing **Jira Data Center REST v2** tools to AI agents
(OpenCode, Claude Desktop, Claude CLI). Authenticates with a user **Personal
Access Token (PAT)**. Runs locally over stdio — no database, no web server, no
cloud dependency.

Source of truth: `PRD.md` (v1.0.0).

## Requirements

- Python 3.10+ and [uv](https://docs.astral.sh/uv/)
- Jira Data Center 9.0+
- A user PAT (Jira admin → **PATs**)

## Install

```bash
uv sync
```

This creates the virtualenv and installs the `mcp-jira` console script.

## Setup

```bash
uv run mcp-jira setup
```

The wizard prompts for the Jira URL and a hidden PAT, verifies connectivity
with `GET /rest/api/2/myself`, and writes `~/.config/mcp-jira/config.json` with
`0600` permissions. Nothing is written when connectivity fails. Without a
terminal it prints the config path plus guidance and exits non-zero.

### Config schema

```json
{
  "jira_url": "https://jira.example.com",
  "jira_pat": "<PAT>",
  "language": "en",
  "read_only": false
}
```

- `jira_url` / `jira_pat` — required; missing either fails fast with
  `CONFIG_MISSING`.
- `language` — `en` (default) or `es`; unknown values fall back to `en`.
- `read_only` — `true` blocks the four mutating tools
  (`create_issue`, `update_issue`, `transition_issue`, `add_comment`) with
  `READ_ONLY_MODE`.
- Environment overrides: `JIRA_URL` and `JIRA_PAT` override the file values;
  `language` and `read_only` are file-only settings.

## Tools

`search_issues`, `get_issue`, `create_issue`, `update_issue`,
`transition_issue`, `add_comment`, `get_comments`, `list_projects`,
`list_fields` — contracts in PRD §3.1. Custom fields are accepted by display
name or raw `customfield_XXXXX` id in get/create/update.

## Error codes

Every tool error surfaces with a stable code and a readable message — never a
stack trace or PAT. Precedence when multiple apply:
`CONFIG_*` > `AUTH_*` > `RATE_LIMITED` > `VALIDATION_*` > `NOT_FOUND` >
`SERVER_ERROR` > `NETWORK_ERROR` > `INTERNAL`.

| Code | Meaning |
|---|---|
| `CONFIG_MISSING` | Config file absent or missing `jira_url`/`jira_pat`; run `mcp-jira setup` |
| `CONFIG_INVALID` | Malformed JSON, empty URL, bad types |
| `AUTH_UNAUTHORIZED` | HTTP 401 — PAT invalid or expired; re-run `mcp-jira setup` |
| `AUTH_FORBIDDEN` | HTTP 403 — no permission for the operation |
| `NOT_FOUND` | HTTP 404 — issue/project/field/comment not found |
| `VALIDATION_ERROR` | HTTP 400 with Jira field errors (create/update/search) |
| `JQL_INVALID` | HTTP 400 on search — Jira's JQL error message verbatim |
| `TRANSITION_INVALID` | Transition not in the issue's available list |
| `FIELD_NOT_EDITABLE` | Field read-only in this issue/status |
| `RATE_LIMITED` | HTTP 429 — `Retry-After` surfaced, never auto-retried |
| `SERVER_ERROR` | HTTP 5xx — retried at most once after 1s, then surfaced |
| `NETWORK_ERROR` | Connection refused, timeout, TLS, DNS |
| `READ_ONLY_MODE` | Mutation attempted with `read_only: true` |
| `INTERNAL` | Unexpected exception — safe detail only, stack stays in local logs |

## Agent configuration

### OpenCode (`opencode.json`)

OpenCode uses the `mcp` key (equivalent of `mcpServers` elsewhere):

```json
{
  "mcp": {
    "mcp-jira": {
      "type": "local",
      "command": ["uv", "run", "mcp-jira"],
      "enabled": true
    }
  }
}
```

### Claude Desktop (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "mcp-jira": {
      "command": "uv",
      "args": ["run", "mcp-jira"]
    }
  }
}
```

### Claude CLI

```bash
claude mcp add mcp-jira -- uv run mcp-jira
```

Or in a project `.mcp.json`:

```json
{
  "mcpServers": {
    "mcp-jira": {
      "command": "uv",
      "args": ["run", "mcp-jira"]
    }
  }
}
```

## Token rotation

Generate a new PAT in Jira admin → PATs, then update the config (or re-run
`mcp-jira setup`). The PAT is read at startup only, so restart the server after
rotating.

## Manual smoke test

Per PRD §3.2: against a real Data Center instance, run each tool once, verify
outputs, and confirm a wrong/expired PAT produces a clear 401
(`AUTH_UNAUTHORIZED`). Not automated — the test suite runs offline against a
mocked HTTP layer.