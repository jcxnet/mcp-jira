```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:d5fd17617199d6e931718f71c129c6bdeca35ffed5870a04549d33ba26499a5d
verdict: pass
blockers: 0
critical_findings: 0
requirements: 7/7
scenarios: 15/15
test_command: uv run pytest
test_exit_code: 0
test_output_hash: sha256:b62d2df9cb511479a71394feb05750423a86313e0d3d8bf8f401c2bf309a6e53
build_command: uv run mypy src
build_exit_code: 0
build_output_hash: sha256:8b88f6d12bd312c1b024b66d07a7f7619a68482ac4d64e475759b1823199faa5
```

## Verification Report

**Change**: mcp-jira-installer
**Version**: client-installer spec (delta, v1)
**Mode**: Standard (Strict TDD disabled per orchestrator)

### Completeness
| Metric | Value |
|--------|-------|
| Tasks total | 12 |
| Tasks complete | 12 |
| Tasks incomplete | 0 |

### Build & Tests Execution
**Build**: ✅ Passed
```text
$ uv run mypy src
Success: no issues found in 12 source files
(exit 0)
$ uv run ruff check
(exit 0, no findings)
```

**Tests**: ✅ 184 passed / 0 failed / 0 skipped
```text
$ uv run pytest
======================== 184 passed, 1 warning in 3.54s ========================
(exit 0)
```

**Runtime harness**:
- `uv run mcp-jira install --help` → exit 0
- `uv run mcp-jira install < /dev/null` → exit 1, prints guidance
- `uv run mcp-jira setup --help` → exit 0 (no regression)

**Coverage**: ➖ Not available / not required by this change's gate commands.

### Spec Compliance Matrix
| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| R1 install subcommand | Interactive install | `tests/test_installer.py > test_install_merges_all_targets_preserves_secrets_and_modes`, `test_select_subset_writes_only_selected` | ✅ COMPLIANT |
| R1 install subcommand | Non-TTY guidance | `test_non_interactive_prints_guidance_exits_1` + harness `install </dev/null` exit 1 | ✅ COMPLIANT |
| R1 install subcommand | Ctrl-C aborts cleanly | `test_ctrl_c_at_selection_aborts_without_writing` | ✅ COMPLIANT |
| R2 Registration command | Correct shapes written | `test_install_merges_all_targets_preserves_secrets_and_modes` (asserts exact OpenCode/Claude shapes, no `env`) | ✅ COMPLIANT |
| R3 OpenCode global | Merge preserves existing servers | `test_install_merges_all_targets_preserves_secrets_and_modes` (Figma server + `FIGMA_API_KEY` preserved) | ✅ COMPLIANT |
| R3 OpenCode global | Idempotent re-run | `test_install_idempotent_rerun_reports_already_registered` ("already registered" x3, files unchanged) | ✅ COMPLIANT |
| R4 Claude CLI user scope | Merge into existing mcpServers | `test_install_merges_all_targets_preserves_secrets_and_modes` (`state` + `other` server kept) | ✅ COMPLIANT |
| R4 Claude CLI user scope | Idempotent re-run | `test_install_idempotent_rerun_reports_already_registered` | ✅ COMPLIANT |
| R5 Claude Desktop | Capital-C directory wins | `test_probe_desktop_dir_capital_wins` | ✅ COMPLIANT |
| R5 Claude Desktop | Lowercase directory used | `test_probe_desktop_dir_lowercase_used` | ✅ COMPLIANT |
| R6 Write safety | Backup created on first write | `test_write_with_backup_backup_once_and_preserves_mode` (+ integration `.json.bak` assertion) | ✅ COMPLIANT |
| R6 Write safety | Broken config skipped | `test_corrupt_config_skipped_untouched`, `test_load_json_corrupt_raises` | ✅ COMPLIANT |
| R6 Write safety | Post-write corruption detected | `test_write_with_backup_corrupt_write_restores_bak`, `test_write_with_backup_corrupt_new_file_removed` | ✅ COMPLIANT |
| R6 Write safety | Secrets never logged | `test_install_merges_all_targets_preserves_secrets_and_modes`, `test_corrupt_config_skipped_untouched` (`FKEY` absent from capsys) | ✅ COMPLIANT |
| R7 Testability | Injectable temp-dir tests | All 18 tests: `tmp_path` + injected `config_paths`/`targets_selected`/`confirm`, no real home writes | ✅ COMPLIANT |

**Compliance summary**: 15/15 scenarios compliant (7/7 requirements).

### Correctness (Static Evidence)
| Requirement | Status | Notes |
|------------|--------|-------|
| R1 install subcommand | ✅ Implemented | `cli.py` `add_parser("install")` + dispatch → `run_installer()`; `_is_interactive()` gate; `KeyboardInterrupt` → "Aborted." exit 1; form-style multi-select + confirm-before-write (default NO) |
| R2 Registration command | ✅ Implemented | `_TARGETS` entries `[sys.executable, "-m", "mcp_jira"]`; OpenCode `{"type":"local","command":[...],"enabled":true}`; Claude `command`+`args`; no `env` anywhere |
| R3 OpenCode global | ✅ Implemented | `default_config_paths()["opencode"] = ~/.config/opencode/opencode.json`; `upsert_client(config, "mcp", entry)` |
| R4 Claude CLI user scope | ✅ Implemented | `~/.claude.json` top-level `mcpServers` upsert |
| R5 Claude Desktop | ✅ Implemented | `probe_desktop_dir`: `Claude/` → `claude/` → default `Claude/` |
| R6 Write safety | ✅ Implemented | `write_with_backup`: `.bak` once, temp+`os.replace`, chmod preserve (0644 new), post-write re-parse, restore `.bak`/unlink + raise on corruption; unparseable → skip untouched; idempotent → skip; contents never printed |
| R7 Testability | ✅ Implemented | `run_installer(*, interactive, config_paths, targets_selected, confirm)` injectables; pure helpers |

### Coherence (Design)
| Decision | Followed? | Notes |
|----------|-----------|-------|
| Serialized command shapes (OpenCode array + enabled, Claude command+args, no env) | ✅ Yes | Exact match with `_TARGETS` |
| Idempotency: key presence → "already registered", never overwrite | ✅ Yes | `upsert_client` returns False |
| Write strategy: temp + `os.replace`, chmod before rename | ✅ Yes | `os.chmod(tmp, mode)` then `os.replace` |
| Post-write validation: re-parse; restore `.bak` + report loudly | ✅ Yes | `write_with_backup` raises; `run_installer` prints failure + exit 1 |
| Backup timing: `.bak` only when existing AND absent | ✅ Yes | |
| Desktop probe order + default | ✅ Yes | |
| Broken config → skip untouched, no backup | ✅ Yes | |
| Non-TTY guidance + exit 1; `^C` abort exit 1; confirm default NO | ✅ Yes | |
| Modes: preserve existing, 0644 new | ✅ Yes | |
| `merge_write` injectable in `run_installer` signature | ⚠️ Accepted deviation | Dropped during apply (unused param; flow uses `write_with_backup` directly). Orchestrator-amended; behavior verified instead of interface sketch |

### Safety Spot-Check
- Installer targets only `Path.home()`-derived global paths (`~/.config/opencode/opencode.json`, `~/.claude.json`, `~/.config/{Claude,claude}/claude_desktop_config.json`); never reads/writes the repo's own project `opencode.json`. ✅
- Installer prints only labels and paths (`Registered mcp-jira in {path}`, skip notices); never prints config file contents. ✅
- No new dependency: `uv.lock` / `pyproject.toml` unchanged in commit e376c41 (diff HEAD~1..HEAD shows no lock/manifest change). ✅

### Issues Found
**CRITICAL**: None
**WARNING**: None
**SUGGESTION**:
- Spec scenario count: orchestrator context cited 16 scenarios; the retrieved spec contains 15 (`rg -c '^#### Scenario:'` = 15). Report uses the authoritative retrieved count. No implementation impact.
- `merge_write` injectable was dropped from `run_installer` (see coherence table). If future tests need write-path injection beyond monkeypatching `json.dumps`, re-add it. Low priority.
- Untracked `.atl/` directory present in repo root; unrelated to this change, but a candidate for `.gitignore` housekeeping.

### Verdict
PASS — 12/12 tasks complete; 7/7 requirements, 15/15 scenarios covered by passing tests; full suite 184 passed; ruff/mypy clean; runtime harness green; no new dependency; safety spot-checks pass. All evidence is runtime-executed, not static-only.
