# Design: `mcp-jira install` client installer

## Technical Approach

New `src/mcp_jira/installer.py` mirrors `wizard.py`'s form-loop + injectable pattern: one `run_installer()` entry, `_is_interactive()` non-TTY gate, injectable `targets_selected`/`confirm`/`config_paths`/`merge_write` defaulting to stdlib, `KeyboardInterrupt` → "Aborted." exit 1. Flow: select targets → load+upsert each (skipping corrupt/idempotent) → summary + confirm-before-write → write with backup + re-parse validation → success report. Registers `[sys.executable, "-m", "mcp_jira"]` (venv-absolute, cwd-independent) into OpenCode global, Claude CLI user scope, and Claude Desktop configs — merge-only, zero new deps (spec R1–R7; proposal approach).

## Architecture Decisions

| Option | Tradeoff | Decision |
|---|---|---|
| Serialized command form | OpenCode needs array; Claude needs `command`+`args`; string form breaks OpenCode `enabled` shape | OpenCode `{"type":"local","command":[...],"enabled":true}`; Claude `{"command":py,"args":["-m","mcp_jira"]}`. No `env` (PAT stays in mcp-jira's 0600 file) (R2, proposal approach) |
| Idempotency rule | Equivalence-check vs key-presence | Key presence: any existing `mcp-jira` entry → "already registered", never overwritten (R4/R5/R6, proposal decision a) |
| Write strategy | Direct write vs temp+rename | Temp file in same dir + `os.replace` (atomic-ish, correct on crash); `os.chmod` before rename to preserve existing mode, 0644 for new files (R7) |
| Post-write validation | Report-only vs restore | Re-parse written file; on failure restore `.bak` and report loudly — client untouched (R7) |
| Backup timing | Always vs once | `.bak` copy only when file exists AND `.bak` absent — first write only (R7) |
| Desktop dir probe | Case guess vs probe | `~/.config/Claude/` then `~/.config/claude/`, first existing wins, default `Claude/` (R5, decision b) |
| Broken config handling | Repair vs skip | Unparseable → skip client, file untouched, no backup, notice printed (R7) |

## Data Flow

    mcp-jira install
        │  (_is_interactive()? else guidance + exit 1)
        ▼
    targets_selected(prompt, options, default) ──► selected client ids (default all 3)
        │
        ▼  per client: config_paths() → path
    load_json ──► None (missing→write new) | dict (merge) | corrupt → skip client
        │
        ▼  upsert_client(config, "mcp"|"mcpServers", entry)
    key exists? ──► "already registered", skip        (no write, no backup)
        │
        ▼  collect pending writes
    Summary → confirm("Write N config(s)? (y/N)") ──► no → "Aborted; nothing was written." exit 1
        │
        ▼  per pending: shutil.copy2 → .bak (once)
    write temp → chmod → os.replace → json.loads re-parse → fail? restore .bak + report
        │
        ▼
    "Registered mcp-jira in {path}" per client — exit 0
    KeyboardInterrupt anywhere → "Aborted." exit 1 (all writes happen only after confirm)

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/mcp_jira/installer.py` | Create | `run_installer` + `load_json`/`upsert_client`/`write_with_backup`/`probe_desktop_dir` (~150 lines, stdlib) |
| `src/mcp_jira/cli.py` | Modify | `add_parser("install", help=...)`; dispatch `args.command == "install"` → `run_installer()` |
| `tests/test_installer.py` | Create | Injectable/tmp-path tests; no real home writes |
| `README.md` | Modify | §Agent configuration → `mcp-jira install` guidance (keep token-rotation smoke sections) |

## Interfaces / Contracts

```python
# installer.py — injectables default to stdlib; tests inject tmp paths/fakes
def run_installer(
    *,
    interactive: bool | None = None,          # None → _is_interactive()
    config_paths: Callable[[], dict[str, Path]] | None = None,
    targets_selected: Callable[[str, Sequence[str], str], str] | None = None,  # → raw answer
    confirm: Callable[[str], str] = input,
    merge_write: Callable[[Path, Path | None, dict, Callable[[dict], bool]], bool] | None = None,
) -> int

def load_json(path: Path) -> dict | None:      # None = missing; ValueError = corrupt
def upsert_client(config: dict, container: str, entry: dict) -> bool  # True = added, False = already registered
def write_with_backup(path: Path, data: dict) -> None  # .bak once, temp+rename, re-parse, restore on failure
def probe_desktop_dir(home: Path) -> Path      # Claude/ → claude/ → Claude/
```

Client shapes (R2): OpenCode container `"mcp"`, entry `{"type":"local","command":[sys.executable,"-m","mcp_jira"],"enabled":true}`; Claude (CLI + Desktop) container `"mcpServers"`, entry `{"command":sys.executable,"args":["-m","mcp_jira"]}`.

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `upsert_client`, `load_json`, `probe_desktop_dir` | Pure functions, tmp_path fixtures (R7) |
| Integration | Full `run_installer` with injected tmp config paths | Merge all 3 targets: shapes, preserved keys (Figma), modes, `.bak` once, `"already registered"` on re-run |
| Unit | Write safety | Corrupt source skipped unmodified; forced invalid write restored from `.bak` + loud failure; secrets (Figma key) never in capsys output |
| Unit | Flow control | Non-TTY exit 1 + guidance; `^C`/declined confirm → exit 1, nothing written |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary. The installer writes a static, non-shell-interpreted command (JSON array / `command`+`args`); it never executes it. `sys.executable` is trusted (venv-absolute).

## Migration / Rollout

No migration. Rollback per file: restore `.bak` or delete the `mcp-jira` key (proposal rollback plan).

## Open Questions

- [ ] None blocking. Desktop path unverifiable on this machine — probe + injectable covers it; verification runs unit tests only for that branch.
