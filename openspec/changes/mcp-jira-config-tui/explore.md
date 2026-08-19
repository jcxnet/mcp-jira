# Exploration: TUI to create the initial mcp-jira config

Status: **success** — change `mcp-jira-config-tui`, artifact store `openspec`.

## Current State

"Initial config" today is one file: `~/.config/mcp-jira/config.json` with keys
`jira_url`, `jira_pat`, `language` (`en` default, `es` optional, unknown →
`en`), `read_only` (bool, default `false`). It is created in two ways:

1. **`mcp-jira setup`** → `mcp_jira/wizard.py:run_wizard()` — already an
   interactive form: prompts URL + hidden PAT (`input`/`getpass`, both
   injectable for tests), verifies connectivity with `GET /rest/api/2/myself`
   via `JiraClient`, writes the file with `0600` (via `os.open` + `os.chmod`),
   reports success/failure. Non-TTY invocation prints the path + guidance and
   exits 1 (AC-US-9).
2. **Hand-editing** the JSON.

Key gap: the wizard only writes `jira_url` + `jira_pat`. The schema's optional
keys `language` and `read_only` are never prompted — a user can only get them
by hand-editing. That is the real delta a "TUI" adds.

Dependency reality: **zero TUI/UI libs are installed** (no textual, no
prompt_toolkit, no questionary, no rich — only `mcp` + `httpx` runtime deps in
uv.lock; curses is stdlib but the venv is Python 3.14/Linux).

## Affected Areas

- `src/mcp_jira/wizard.py` — the change lives here: add optional-field prompts,
  input validation, and a pre-write confirmation. No rewrite of the write/check
  logic.
- `src/mcp_jira/config.py` — reuse only (`SUPPORTED_LANGUAGES`,
  `default_config_path`, unknown-language fallback stays as the load-time
  backstop). No change.
- `src/mcp_jira/client.py` — reuse only (`JiraClient` /myself check). No change.
- `src/mcp_jira/cli.py` — no change needed (`setup` subcommand remains the
  entry; optional help-text tweak only).
- `tests/test_wizard.py` — extend with the same injection pattern
  (`prompt`/`hidden_prompt`/`transport` + new `select`/`confirm` injectables).
  Existing 4 tests keep passing unmodified.
- `pyproject.toml` — **no new dependency** under the recommended approach.

## Approaches

1. **Textual full TUI** — real widget app (screens, form widgets, event loop).
   - Pros: polished look, rich widgets, keyboard nav; a genuine "TUI" aesthetic.
   - Cons: heavy new dep tree (textual + rich + click ~ +5 packages); an event
     loop and async for a **4-field form**; harder to test than plain
     functions; contradicts PRD §2.4 non-goal ("configuration is file-based, no
     UI dashboard") and the ponytail constraint.
   - Effort: High. **Excluded** unless the user explicitly wants the widget
     aesthetic.

2. **prompt_toolkit / questionary form** — form-style prompts with validation
   callbacks and arrow-key selection.
   - Pros: nicer than bare `input()` (inline validation, selectables); ~1-2
     packages; keeps a plain function signature.
   - Cons: still a new runtime dependency for what stdlib covers in this case
     (4 fields, no multiline, no completion).
   - Effort: Medium.

3. **Plain curses (stdlib)** — hand-drawn form, raw key events.
   - Pros: zero new deps.
   - Cons: the most code of all options (layout, resize, key handling,
     focus); more code than the 72-line wizard it would replace. Worst
     code-per-field ratio. 
   - Effort: High. **Excluded**.

4. **Guided form-style loop extending the existing wizard (stdlib only)** —
   keep `mcp-jira setup`, keep `run_wizard()`'s injectable design, add:
   - URL prompt with non-empty + `http(s)://` format validation (retry on
     invalid, empty URL/PAT rejects as today);
   - `language` prompt defaulting to `en`, accepting `en`/`es` only
     (`config.SUPPORTED_LANGUAGES`) — validation at input, so the load-time
     fallback never fires from this path;
   - `read_only` prompt `y/n` default `n` (`false`);
   - a summary + confirmation step (`Write this config to <path>?`) before the
     /myself check and 0600 write — abort writes nothing;
   - `^C` → clean abort, exit 1, nothing written;
   - existing behavior untouched: non-TTY guidance + exit 1, connectivity
     failure writes nothing, 0600 enforced via `os.open` + `os.chmod`.
   - Pros: zero new deps (ponytail rungs 1–2); every line of write/check
     security logic is reused, not re-implemented; the test pattern
     (injectables + httpx MockTransport) extends trivially; ~30–40 line diff on
     one file; it IS a terminal UI — the laziest one that fully covers a
     single-config form.
   - Cons: not a "fancy TUI" — no widgets, arrow keys, or themes; if the user
     wants that aesthetic specifically, this undershoots.
   - Effort: Low.

## Recommendation

**Approach 4 — extend the existing wizard as a guided form-style loop.** The
wizard already IS the interactive TUI for initial config; a Textual/prompt_toolkit
app adds a dependency tree to win back what a 4-field form never needed. The
substantive user-visible improvement — prompting the optional `language` /
`read_only` keys the schema already supports — is a small, stdlib-only delta in
`wizard.py`, with validation at input time and a confirmation step before
anything is written. All security-relevant logic (hidden PAT, /myself check,
0600 write, non-TTY behavior) is reused verbatim, and the existing test harness
covers it unchanged.

Frame it in the proposal as an enhancement of `mcp-jira setup` (US-9 / AC-US-9),
not a new surface — keeping within PRD §2.4's "file-based config" non-goal.

## Risks

- **Scope creep toward a real TUI**: the name invites Textual. Keep the spec
  bound to "creation form" — any widget/screen requirement pushes effort and
  deps up sharply.
- **PRD non-goal tension**: a "TUI" looks like a UI surface; the proposal must
  tie every requirement to the existing `setup` wizard scenarios to stay inside
  the file-based-config boundary.
- **Test drift**: the wizard's injectability is load-bearing (tests pass
  lambdas, not TTYs). New `select`/`confirm` injectables must follow the same
  default-to-stdlib pattern or the suite breaks.
- **Accidental overwrite**: today the wizard truncates an existing config with
  no warning. The confirmation step fixes this — make it a requirement, not a
  nice-to-have.

## Ready for Proposal

**Yes.** Recommendation: stdlib-only extension of `mcp-jira setup` in
`wizard.py` (optional `language`/`read_only` prompts, URL format validation,
pre-write confirmation, `^C` abort). Explicitly excluded unless the user asks:
a Textual/prompt_toolkit widget app, config *editing* (no `edit` subcommand),
themes, multi-profile, or any Jira data browsing (project/field pickers).

Tell the user: the existing `mcp-jira setup` wizard already covers 80% of
"create the initial config"; this change adds the missing optional-field
prompts + confirmation with **zero new dependencies**. If they specifically
want a widget-style TUI (arrow-key forms, themes), that is a separate, heavier
decision — say so and the proposal will go the Textual route instead.
