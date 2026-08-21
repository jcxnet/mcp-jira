"""Config loading for mcp-jira: file + env override + fail-fast validation.

File must exist in the per-OS config dir (``CONFIG_MISSING`` otherwise) — see
:func:`mcp_jira.platform.config_dir`. ``JIRA_URL``/``JIRA_PAT`` env vars
override the file values when set; ``language``/``read_only`` are file-only
settings. Unknown ``language`` falls back to ``en``. A group/world-readable
config file logs a warning to stderr and still loads.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from mcp_jira.errors import EN_MESSAGES, JiraError
from mcp_jira.platform import config_dir, is_windows

SUPPORTED_LANGUAGES = ("en", "es")
_CONFIG_FILE = "config.json"


def default_config_path() -> Path:
    """Return the per-OS config file path (server-config §schema)."""
    return config_dir() / _CONFIG_FILE


@dataclass(frozen=True)
class Settings:
    """Validated runtime settings; ``language`` is normalized to en/es."""

    jira_url: str
    jira_pat: str
    language: str = "en"
    read_only: bool = False


def load_config(path: Path | None = None, env: Mapping[str, str] | None = None) -> Settings:
    """Load and validate configuration, raising ``JiraError`` with a §4.4 code."""
    path = path or default_config_path()
    env = os.environ if env is None else env
    if not path.exists():
        raise JiraError("CONFIG_MISSING", EN_MESSAGES["CONFIG_MISSING"])
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        raise JiraError("CONFIG_INVALID", _invalid(str(exc))) from exc
    if not isinstance(data, dict):
        raise JiraError("CONFIG_INVALID", _invalid("config must be a JSON object"))
    jira_url = env.get("JIRA_URL") or data.get("jira_url")
    jira_pat = env.get("JIRA_PAT") or data.get("jira_pat")
    if jira_url is None or jira_pat is None:
        raise JiraError("CONFIG_MISSING", EN_MESSAGES["CONFIG_MISSING"])
    if not isinstance(jira_url, str) or not isinstance(jira_pat, str):
        raise JiraError("CONFIG_INVALID", _invalid("jira_url and jira_pat must be strings"))
    if not jira_url.strip():
        raise JiraError("CONFIG_INVALID", _invalid("jira_url must not be empty"))
    if not jira_pat.strip():
        raise JiraError("CONFIG_MISSING", EN_MESSAGES["CONFIG_MISSING"])
    language = data.get("language", "en")
    if not isinstance(language, str):
        raise JiraError("CONFIG_INVALID", _invalid("language must be a string"))
    if language not in SUPPORTED_LANGUAGES:
        language = "en"
    read_only = data.get("read_only", False)
    if not isinstance(read_only, bool):
        raise JiraError("CONFIG_INVALID", _invalid("read_only must be a boolean"))
    _warn_if_shared(path)
    return Settings(jira_url=jira_url, jira_pat=jira_pat, language=language, read_only=read_only)


def _invalid(detail: str) -> str:
    return EN_MESSAGES["CONFIG_INVALID"].format(detail=detail)


def _warn_if_shared(path: Path) -> None:
    """Warn (not block) when the config file is group/world-readable.

    Windows has no POSIX mode bits, so the check only runs on POSIX.
    """
    if is_windows():
        return
    mode = path.stat().st_mode & 0o777
    if mode & 0o044:
        print(
            f"Warning: config file {path} is readable by others (mode {mode:o}); "
            f"consider `chmod 600 {path}` — it contains a Jira PAT.",
            file=sys.stderr,
        )
