# Tasks: Extend `mcp-jira setup` wizard — optional fields, validation, confirmation

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~160 (wizard.py ~45 + test_wizard.py ~115) |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | auto-chain |
| Chain strategy | pending (no chain needed; stacked-to-main cached unused) |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: pending
400-line budget risk: Low

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Extend wizard (select/confirm, URL validation, language/read_only, confirm+abort, 4-key write) + tests | PR 1 (single) | `uv run pytest tests/test_wizard.py` | `uv run mcp-jira setup --help` exits 0; non-interactive run prints path, exits 1 (full TTY flow manual — no pexpect dep) | revert `wizard.py` + `test_wizard.py`; config load path untouched |

## Phase 1: Foundation — injectables & validation

- [x] **1.1** wizard.py: extend `run_wizard()` signature with `select: Callable[[str, Sequence[str], str], str] = lambda p, o, d: input(p)` and `confirm: Callable[[str, bool], str] = lambda p, d: input(p)`; import `Sequence` (collections.abc) and `SUPPORTED_LANGUAGES` (mcp_jira.config).
  **Deps**: none. **AC**: ADDED testability §Injectables drive the full flow. **Tests**: `uv run pytest tests/test_wizard.py`.
- [x] **1.2** wizard.py: add `_valid_url()` — `urllib.parse.urlsplit`; true iff `scheme in {"http","https"}` and `bool(netloc)` (blank, `http://`, no-scheme reject).
  **Deps**: 1.1. **AC**: design D3 table. **Tests**: unit via 2.1 flow.

## Phase 2: Core — prompts, confirmation, abort, 4-key write

- [x] **2.1** URL loop: blank → existing "Both a Jira URL and a PAT are required…" exit 1 (keeps test 3); non-`http(s)://` → stderr format error, re-prompt until valid or ^C.
  **Deps**: 1.2. **AC**: MODIFIED §Invalid URL format rejected — /myself never called, nothing written. **Tests**: `uv run pytest tests/test_wizard.py`.
- [x] **2.2** Language select (options `SUPPORTED_LANGUAGES`, default `en`, invalid → re-prompt) + read_only confirm (`y`/`yes` → True, empty → default False, invalid → re-prompt).
  **Deps**: 1.1. **AC**: §Optional fields default when skipped; design D2. **Tests**: pytest.
- [x] **2.3** Reorder per D5: after `/myself` succeeds, print summary (URL, language, read_only — never PAT) then `confirm` default NO; decline/empty → return 1, file untouched.
  **Deps**: 2.2. **AC**: §Confirmation declined aborts — existing file left unmodified (overwrite guard). **Tests**: pytest.
- [x] **2.4** Wrap interactive section in `except KeyboardInterrupt` → "Aborted." to stderr, return 1.
  **Deps**: 2.1–2.3. **AC**: §Ctrl-C aborts cleanly — no write/truncate possible (write after all prompts). **Tests**: pytest.
- [x] **2.5** Extend write dict to `{"jira_url", "jira_pat", "language", "read_only"}`; keep `os.open` 0600 + `os.chmod` verbatim.
  **Deps**: 2.2. **AC**: §Interactive success — 0600 file with all 4 keys, success reported. **Tests**: pytest.

## Phase 3: Tests

- [x] **3.1** test_wizard.py: add `select`/`confirm` lambdas to tests 1–2 (empty input → defaults); extend test 1 expected dict to full 4-key shape (amended §Existing suite unaffected); tests 3–4 untouched.
  **Deps**: 2.5. **AC**: ADDED testability — injectable convention preserved, suite green. **Tests**: `uv run pytest tests/test_wizard.py`.
- [x] **3.2** New cases: URL re-prompt (prompt returns `"not-a-url"` then `BASE_URL` → /myself hit once, file written); empty select/confirm → `"en"`/`false` in file; confirm `"y"` at read_only → `true`.
  **Deps**: 3.1. **AC**: §Invalid URL format rejected, §Optional fields default, design D2 read_only. **Tests**: `uv run pytest tests/test_wizard.py`.
- [x] **3.3** New cases: pre-existing file + decline → exit 1, bytes unchanged (truncate guard); prompt raises `KeyboardInterrupt` → exit 1, no file; `/myself` 401 → confirm never called (extends test 2).
  **Deps**: 3.1. **AC**: §Confirmation declined, §Ctrl-C, §Connectivity failure (preserved). **Tests**: `uv run pytest tests/test_wizard.py`.

## Phase 4: Final gate

- [x] **4.1** `uv run ruff check && uv run mypy src && uv run pytest` all green; `uv run mcp-jira setup --help` exits 0; uv.lock shows no new dependency.
  **Deps**: all. **AC**: proposal §success criteria. **Tests**: full gate commands.
