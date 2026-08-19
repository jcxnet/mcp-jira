# Delta for Jira Tools

## ADDED Requirements

### Requirement: Tool registration

The server MUST register all nine tools: `search_issues`, `get_issue`, `create_issue`, `update_issue`, `transition_issue`, `add_comment`, `get_comments`, `list_projects`, `list_fields`.

#### Scenario: All tools listed

- GIVEN a started server with valid config
- WHEN a client lists available tools
- THEN all nine tools are present

### Requirement: Tool contracts

Each tool MUST implement its §3.1 contract against the listed REST v2 endpoint and return structured JSON:

| Tool | Endpoint | Inputs | Output |
|---|---|---|---|
| search_issues | GET /rest/api/2/search | jql, max_results (default 50, cap 100) | `{issues:[{key,summary,status,assignee,priority,issue_type}]}` |
| get_issue | GET /rest/api/2/issue/{key}?expand=transitions | issue_key | `{key,summary,description,status,assignee,priority,fields,transitions}` |
| create_issue | POST /rest/api/2/issue | project_key, issue_type, summary, description, fields | `{key}` |
| update_issue | PUT /rest/api/2/issue/{key} | issue_key, fields | `{updated:true}` |
| transition_issue | POST /rest/api/2/issue/{key}/transitions | issue_key, transition (name or ID) | `{transitioned:true}` |
| add_comment | POST /rest/api/2/issue/{key}/comment | issue_key, body | `{id,created}` |
| get_comments | GET /rest/api/2/issue/{key}/comment | issue_key | `{comments:[{id,author,created,body}]}` |
| list_projects | GET /rest/api/2/project | — | `{projects:[{key,name,issue_types}]}` |
| list_fields | GET /rest/api/2/field | — | `{fields:[{id,name,custom,type,allowed_values}]}` |

#### Scenario: Search caps max_results

- GIVEN `max_results = 500`
- WHEN search_issues runs
- THEN the request is capped at 100

#### Scenario: get_issue includes transitions

- GIVEN an existing issue key
- WHEN get_issue runs
- THEN the response includes the fields and transitions available to the authenticated user

#### Scenario: create_issue returns new key

- GIVEN project_key, issue_type, and summary
- WHEN create_issue runs successfully
- THEN the response is `{key: "<new-key>"}`

#### Scenario: Transition by name

- GIVEN a transition name in the issue's available transitions
- WHEN transition_issue is called with that name
- THEN the issue transitions and `{transitioned:true}` is returned

### Requirement: Custom-field resolution

The server MUST fetch the field map from `GET /rest/api/2/field` at startup and cache it. `get_issue`/`create_issue`/`update_issue` MUST accept custom fields by display name (resolved to ID via the cache) or raw `customfield_XXXXX` ID. Ambiguous names MUST fail with `VALIDATION_ERROR`.

#### Scenario: Display name resolves to ID

- GIVEN a cached map with "Story Points" → customfield_10001
- WHEN create_issue passes `fields: {"Story Points": 5}`
- THEN the payload uses customfield_10001

#### Scenario: Raw ID passes through

- GIVEN a cached field map
- WHEN update_issue passes `fields: {"customfield_10001": 3}`
- THEN the ID is sent unchanged

#### Scenario: Ambiguous name fails

- GIVEN two cached fields sharing a display name
- WHEN get_issue requests the ambiguous name
- THEN it fails with VALIDATION_ERROR

### Requirement: Read-only mode

When `read_only: true`, `create_issue`, `update_issue`, `transition_issue`, and `add_comment` MUST remain registered but immediately return a `READ_ONLY_MODE` error; read tools MUST be unaffected.

#### Scenario: Mutation blocked

- GIVEN `read_only: true`
- WHEN create_issue is invoked
- THEN READ_ONLY_MODE is returned and no HTTP request is made

#### Scenario: Reads unaffected

- GIVEN `read_only: true`
- WHEN search_issues is invoked
- THEN it executes normally

*Trace: AC-US-1..7, AC-US-10, AC-US-12, SC-1, SC-3, §3.1 endpoint table*