# Design: Extend `mcp-jira setup` wizard — optional fields, validation, confirmation

## Technical Approach

Stdlib-only delta to `run_wizard()` in `src/mcp_jira/wizard.py`: keep the existing injectable pattern and add `select`/`confirm` injectables; validate URL, language, and read_only at input time; run the `/myself` check BEFORE a pre-write confirmation summary; write all four config keys with the existing 0600 `os.open`/`os.chmod` step verbatim; wrap the interactive section in `except KeyboardInterrupt` → exit 1, nothing written. Maps 1:1 to the MODIFIED setup-wizard requirement and the ADDED testability requirement (`specs/server-config/spec.md`). Zero new dependencies.

## Architecture Decisions

### D1: Form-style loop, zero new dependencies (user decision, non-negotiable)
| Option | Tradeoff | Decision |
|---|---|---|
| Textual / prompt_toolkit widget TUI | polish vs dependency tree + event loop for a 4-field form; contradicts PRD §2.4 | ✗ |
| Plain curses | stdlib, but more code than the 72-line wizard it extends | ✗ |
| **Extend existing wizard** | zero deps; every line of security logic reused; ~40-line diff; test harness extends trivially | ✓ |

### D2: `select`/`confirm` injectables, same convention as `prompt`/`hidden_prompt`
Keyword injectables; defaults are one-line stdlib adapters because `input()` accepts only the prompt string: `select: Callable[[str, Sequence[str], str], str] = lambda p, o, d: input(p)` and `confirm: Callable[[str, bool], str] = lambda p, d: input(p)`. The wizard parses/normalizes the returned string (strip/lower; empty input → default). One code path — no `None`-default "headless" branch.

### D3: URL validation — `_valid_url()` helper; re-prompt on format error, reject on blank
| Input | Behavior | Why |
|---|---|---|
| blank | existing message ("Both a Jira URL and a PAT are required…"), exit 1 | proposal pins empty → reject; keeps test 3 passing |
| non-`http(s)://` or no host | format error to stderr, re-prompt (loop; ^C escapes) | proposal pins invalid → re-prompt; friendlier for a typo'd scheme |
| valid | proceed | — |

Helper uses stdlib `urllib.parse.urlsplit`: `scheme in {"http", "https"} and bool(netloc)`. Correct on edge cases: `http://` alone → empty netloc → reject; uppercase scheme normalizes; `jira.example.com` (no scheme) → reject.

### D4: Wizard messages stay hardcoded English; no i18n change
`EN_MESSAGES`/`i18n.MESSAGES` serve the §4.4 error model, not CLI prompts; the wizard's prompts and `_GUIDANCE` are already hardcoded English (wizard.py:25–28, 56, 71). Spec is silent on prompt localization. Adding i18n keys is unrequested scope.

### D5: `/myself` check BEFORE confirmation summary
| Order | Rationale |
|---|---|
| prompts → `/myself` → summary + confirm → write | the confirmation must be honest about a reachable server; avoids confirming "yes" then discovering failure. Spec allows either ("BOTH must pass") — pinned. |

### D6: Final confirmation defaults to NO
Decline (or bare Enter) → exit 1, file untouched. This is the silent-overwrite guard (proposal Risk 3) — a deliberate `y` is required to write. Summary shows URL, language, read_only; never the PAT.

### D7: `^C` → `except KeyboardInterrupt`
Wrap the interactive section; print "Aborted." to stderr, return 1. The write happens after all prompts, so no partial write is possible by construction.

### D8: Write step verbatim, extended to 4 keys
`path.parent.mkdir` → `os.open(path, O_WRONLY|O_CREAT|O_TRUNC, 0o600)` → `json.dump` → `os.chmod(path, 0o600)` → success print. Only the dict gains `language`/`read_only`.

## Data Flow

```
setup → non-TTY? → print path + guidance, exit 1
TTY → URL prompt → blank? exit 1 ── format bad? re-prompt
    → hidden PAT prompt → blank? exit 1
    → language select (en/es, default en) ── invalid? re-prompt
    → read_only confirm (y/n, default false) ── invalid? re-prompt
    → GET /myself (JiraClient, injectable transport)
         → JiraError → "Connection failed: …", exit 1, nothing written
    → summary (URL, language, read_only) + confirm (default n)
         → no → exit 1, file untouched
    → os.open 0600 + json.dump 4 keys + chmod 0600 → success, exit 0
KeyboardInterrupt at any prompt → "Aborted.", exit 1
```

## File Changes

| File | Action | Description |
|---|---|---|
| `src/mcp_jira/wizard.py` | Modify | `select`/`confirm` injectables, `_valid_url()`, re-prompt loops, summary + confirmation, KeyboardInterrupt guard; 4-key write (~40-line delta) |
| `tests/test_wizard.py` | Modify | tests 1–2 gain `select`/`confirm` lambdas; test 1 expected dict extends to 4 keys; new cases below |
| `config.py`, `client.py`, `i18n.py`, `pyproject.toml` | — | reuse only; no change, no new dependency |

## Interfaces / Contracts

```python
# wizard.py — extended signature (imports: SUPPORTED_LANGUAGES from mcp_jira.config,
# urlsplit from urllib.parse, Sequence from collections.abc)
def run_wizard(
    *,
    config_path: Path | None = None,
    interactive: bool | None = None,
    prompt: Callable[[str], str] = input,
    hidden_prompt: Callable[[str], str] = getpass.getpass,
    select: Callable[[str, Sequence[str], str], str] = lambda p, o, d: input(p),
    confirm: Callable[[str, bool], str] = lambda p, d: input(p),
    transport: httpx.BaseTransport | None = None,
) -> int:
```

- `select(prompt, options, default)`: options = `config.SUPPORTED_LANGUAGES`; empty → default.
- `confirm(prompt, default)`: "y"/"yes" → True, "n"/"no"/empty → default, else re-prompt.
- Written shape: `{"jira_url": url, "jira_pat": pat, "language": lang, "read_only": read_only}`.

## Testing Strategy

| Layer | What to Test | Approach |
|---|---|---|
| Unit | select/confirm drive full flow | inject lambdas + `jira_mock.transport`; assert 4-key file, 0600 |
| Unit | URL format re-prompt | prompt returns `"not-a-url"` then `BASE_URL`; assert /myself hit once, file written |
| Unit | empty URL rejected | existing test 3, unmodified |
| Unit | language/read_only defaults | empty select/confirm input → `"en"`/`false` in file |
| Unit | read_only y → true | confirm returns `"y"` at read_only prompt |
| Unit | confirmation declined | pre-existing file; decline → exit 1, bytes unchanged (truncate guard) |
| Unit | ^C at any prompt | prompt raises `KeyboardInterrupt` → exit 1, no file |
| Unit | /myself before confirm | connectivity failure → confirm never called, no file (extends test 2) |
| Integration | non-TTY | existing test 4, unmodified |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary. File-write security (0600, PAT never echoed, overwrite confirmation) is covered by the existing write step, reused verbatim.

## Migration / Rollout

No migration. Existing 2-key configs remain valid (load path unchanged). Rollback: `git revert` of the wizard/tests commit.

## Open Questions

- [ ] **Spec conflict — needs orchestrator/spec decision before verify**: the ADDED scenario "Existing suite unaffected" is unsatisfiable as literally stated. Writing 4 keys breaks test 1's exact-dict assertion (`== {"jira_url", "jira_pat"}`), and the stdlib-default injectables make tests 1–2 hit real stdin at the language prompt (EOFError under pytest). Recommended resolution: amend that scenario to "the four tests pass after adding `select`/`confirm` lambdas and extending test 1's expected dict to the 4 keys" — harness pattern unchanged, two mechanical edits. This design assumes the amended reading; the 4-key write (MODIFIED requirement) is the primary behavior.
