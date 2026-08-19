# Tasks: `mcp-jira install` — register the server into MCP clients

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~410 (installer.py ~150 + cli.py ~3 + test_installer.py ~210 + README ~35) |
| 400-line budget risk | Medium |
| Chained PRs recommended | No |
| Suggested split | Single PR (monitor before PR; if >400, request size:exception) |
| Delivery strategy | auto-chain |
| Chain strategy | pending (no chain needed; stacked-to-main cached unused) |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: pending
400-line budget risk: Medium

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | `install` subcommand: installer.py flow+merge/backup/validate, cli.py wiring, test_installer.py, README install section | PR 1 (single) | `uv run pytest tests/test_installer.py` | `uv run mcp-jira install --help` exits 0; `uv run mcp-jira install </dev/null` prints guidance, exits 1 (no TTY needed; full TTY flow manual — no pexpect dep) | revert installer.py + cli.py + test_installer.py + README §Agent configuration; user configs restored via .bak/key deletion |

## Phase 1: Foundation — installer primitives

- [x] **1.1** Create `src/mcp_jira/installer.py`: `load_json(path) -> dict | None` (missing→None, `JSONDecodeError`→raise) + `probe_desktop_dir(home)` (`Claude/` → `claude/` → default `Claude/`).
  **Deps**: none. **AC**: R5 probe scenarios, R7 testability. **Tests**: `uv run pytest tests/test_installer.py`.
- [x] **1.2** installer.py: `upsert_client(config, container, entry) -> bool` — existing `mcp-jira` key → False ("already registered"), else insert + True; never overwrite.
  **Deps**: 1.1. **AC**: R3/R4/R5 merge + idempotent scenarios. **Tests**: pytest.
- [x] **1.3** installer.py: `write_with_backup(path, data)` — `shutil.copy2` → `<path>.bak` once (existing file, no .bak), temp file same dir + `os.chmod` (preserve mode; 0644 new) + `os.replace`, re-parse `json.loads`, on corruption restore `.bak` + raise.
  **Deps**: 1.1. **AC**: R6 backup/mode/post-write-corruption. **Tests**: pytest.

## Phase 2: Core — run_installer flow

- [x] **2.1** installer.py: `run_installer(*, interactive=None, config_paths=None, targets_selected=None, confirm=input, merge_write=None)` — non-TTY → guidance + return 1; `KeyboardInterrupt` → "Aborted." return 1; default `config_paths()` → the 3 real targets.
  **Deps**: 1.1. **AC**: R1 non-TTY + ^C scenarios. **Tests**: pytest.
- [x] **2.2** installer.py: shapes + selection — OpenCode `mcp` `{"type":"local","command":[sys.executable,"-m","mcp_jira"],"enabled":true}`; Claude CLI+Desktop `mcpServers` `{"command":sys.executable,"args":["-m","mcp_jira"]}`; no `env`; multi-select via `targets_selected` (default all 3); corrupt config → skip client untouched; idempotent → "already registered" skip.
  **Deps**: 2.1. **AC**: R2 shapes, R3/R4/R5 merge, R6 broken-skip. **Tests**: pytest.
- [x] **2.3** installer.py: write phase — summary → `confirm` default NO → decline → "Aborted; nothing was written." return 1; per pending: `write_with_backup`, print "Registered mcp-jira in {path}", return 0; never print config contents.
  **Deps**: 2.2. **AC**: R1 interactive, R6 secrets-never-logged. **Tests**: pytest.

## Phase 3: Integration — CLI wiring

- [x] **3.1** cli.py: `subparsers.add_parser("install", help="register mcp-jira into OpenCode/Claude configs")`; import + dispatch `args.command == "install"` → `return run_installer()`.
  **Deps**: 2.3. **AC**: R1 subcommand exists. **Tests**: `uv run mcp-jira install --help`; `uv run pytest`.

## Phase 4: Tests

- [x] **4.1** test_installer.py: integration via tmp_path + injected `config_paths`/`targets_selected`/`confirm` — all 3 targets merged with correct shapes; Figma key + other servers preserved; modes preserved; `.bak` once; re-run → "already registered", files unchanged.
  **Deps**: 3.1. **AC**: R2–R7 scenarios. **Tests**: `uv run pytest tests/test_installer.py`.
- [x] **4.2** test_installer.py: unit — `load_json` corrupt→raise/missing→None; `upsert_client` existing→False; `write_with_backup` backup-once, forced corrupt write restores `.bak` + loud failure, new file 0644; `probe_desktop_dir` capital wins / lowercase used / default.
  **Deps**: 1.3. **AC**: R6, R5 probe scenarios. **Tests**: pytest.
- [x] **4.3** test_installer.py: flow — `interactive=False` → guidance + 1; `^C` at `targets_selected` → 1, nothing written; declined confirm → 1, nothing written; corrupt config skipped untouched; Figma key never in capsys.
  **Deps**: 2.3. **AC**: R1, R6 secrets. **Tests**: pytest.

## Phase 5: Docs + final gate

- [x] **5.1** README.md: replace §Agent configuration JSON blocks (~lines 86–134) with `mcp-jira install` guidance; keep §Token rotation + smoke sections.
  **Deps**: 3.1. **AC**: proposal affected areas. **Tests**: none — doc artifact.
- [x] **5.2** Gate: `uv run ruff check && uv run mypy src && uv run pytest` green; `uv run mcp-jira install --help` exits 0; uv.lock shows no new dependency.
  **Deps**: all. **AC**: proposal §success criteria. **Tests**: full gate commands.
