"""Unit tests for mcp_jira.config (schema, env overrides, validation, perms warning)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from mcp_jira import platform
from mcp_jira.config import Settings, default_config_path, load_config
from mcp_jira.errors import JiraError


def _write(cfg_path, data: dict, mode: int = 0o600) -> None:
    cfg_path.write_text(json.dumps(data))
    cfg_path.chmod(mode)


def test_valid_config_loads(tmp_path) -> None:
    cfg = tmp_path / "config.json"
    _write(cfg, {"jira_url": "https://jira.example.test", "jira_pat": "tok"})
    settings = load_config(cfg, env={})
    assert settings == Settings(jira_url="https://jira.example.test", jira_pat="tok")


def test_defaults_language_en_read_only_false(tmp_path) -> None:
    cfg = tmp_path / "config.json"
    _write(cfg, {"jira_url": "https://j", "jira_pat": "tok"})
    settings = load_config(cfg, env={})
    assert settings.language == "en"
    assert settings.read_only is False


def test_missing_file_raises_config_missing(tmp_path) -> None:
    with pytest.raises(JiraError) as exc:
        load_config(tmp_path / "nope.json", env={})
    assert exc.value.code == "CONFIG_MISSING"


def test_default_config_path_linux(monkeypatch) -> None:
    monkeypatch.setattr(platform, "is_windows", lambda: False)
    monkeypatch.setattr(platform, "is_macos", lambda: False)
    home = Path("/home/u")
    monkeypatch.setattr(Path, "home", lambda: home)
    assert default_config_path() == home / ".config/mcp-jira/config.json"


def test_default_config_path_macos(monkeypatch) -> None:
    monkeypatch.setattr(platform, "is_windows", lambda: False)
    monkeypatch.setattr(platform, "is_macos", lambda: True)
    home = Path("/Users/u")
    monkeypatch.setattr(Path, "home", lambda: home)
    assert default_config_path() == home / "Library/Application Support/mcp-jira/config.json"


def test_default_config_path_windows(monkeypatch) -> None:
    monkeypatch.setattr(platform, "is_windows", lambda: True)
    monkeypatch.setattr(platform, "is_macos", lambda: False)
    monkeypatch.setattr(Path, "home", lambda: Path("C:/Users/u"))
    monkeypatch.setattr(os, "environ", {"APPDATA": "C:/Users/u/AppData/Roaming"}, raising=False)
    assert default_config_path() == Path("C:/Users/u/AppData/Roaming/mcp-jira/config.json")


def test_malformed_json_raises_config_invalid(tmp_path) -> None:
    cfg = tmp_path / "config.json"
    cfg.write_text("{not json")
    with pytest.raises(JiraError) as exc:
        load_config(cfg, env={})
    assert exc.value.code == "CONFIG_INVALID"


def test_non_object_json_raises_config_invalid(tmp_path) -> None:
    cfg = tmp_path / "config.json"
    cfg.write_text("[1, 2]")
    with pytest.raises(JiraError) as exc:
        load_config(cfg, env={})
    assert exc.value.code == "CONFIG_INVALID"


@pytest.mark.parametrize("missing", ["jira_url", "jira_pat"])
def test_missing_key_raises_config_missing(tmp_path, missing: str) -> None:
    data = {"jira_url": "https://j", "jira_pat": "tok"}
    del data[missing]
    cfg = tmp_path / "config.json"
    _write(cfg, data)
    with pytest.raises(JiraError) as exc:
        load_config(cfg, env={})
    assert exc.value.code == "CONFIG_MISSING"


def test_env_overrides_file_values(tmp_path) -> None:
    cfg = tmp_path / "config.json"
    _write(cfg, {"jira_url": "https://file.test", "jira_pat": "file-pat"})
    settings = load_config(cfg, env={"JIRA_URL": "https://env.test", "JIRA_PAT": "env-pat"})
    assert settings.jira_url == "https://env.test"
    assert settings.jira_pat == "env-pat"


def test_language_and_read_only_are_file_only(tmp_path) -> None:
    cfg = tmp_path / "config.json"
    _write(
        cfg,
        {
            "jira_url": "https://file.test",
            "jira_pat": "tok",
            "language": "es",
            "read_only": True,
        },
    )
    settings = load_config(cfg, env={"JIRA_URL": "https://env.test", "JIRA_PAT": "env-pat"})
    assert settings.language == "es"
    assert settings.read_only is True


def test_unknown_language_falls_back_to_en(tmp_path) -> None:
    cfg = tmp_path / "config.json"
    _write(cfg, {"jira_url": "https://j", "jira_pat": "tok", "language": "fr"})
    assert load_config(cfg, env={}).language == "en"


@pytest.mark.parametrize("bad", [True, 5, None])
def test_language_bad_type_invalid(tmp_path, bad) -> None:
    cfg = tmp_path / "config.json"
    _write(cfg, {"jira_url": "https://j", "jira_pat": "tok", "language": bad})
    with pytest.raises(JiraError) as exc:
        load_config(cfg, env={})
    assert exc.value.code == "CONFIG_INVALID"


def test_empty_url_invalid(tmp_path) -> None:
    cfg = tmp_path / "config.json"
    _write(cfg, {"jira_url": "   ", "jira_pat": "tok"})
    with pytest.raises(JiraError) as exc:
        load_config(cfg, env={})
    assert exc.value.code == "CONFIG_INVALID"


def test_non_boolean_read_only_invalid(tmp_path) -> None:
    cfg = tmp_path / "config.json"
    _write(cfg, {"jira_url": "https://j", "jira_pat": "tok", "read_only": "yes"})
    with pytest.raises(JiraError) as exc:
        load_config(cfg, env={})
    assert exc.value.code == "CONFIG_INVALID"


def test_world_readable_warns_on_stderr(tmp_path, capsys) -> None:
    cfg = tmp_path / "config.json"
    _write(cfg, {"jira_url": "https://j", "jira_pat": "tok"}, mode=0o644)
    settings = load_config(cfg, env={})
    assert settings.jira_url == "https://j"
    assert "Warning" in capsys.readouterr().err


def test_0600_no_warning(tmp_path, capsys) -> None:
    cfg = tmp_path / "config.json"
    _write(cfg, {"jira_url": "https://j", "jira_pat": "tok"}, mode=0o600)
    load_config(cfg, env={})
    assert capsys.readouterr().err == ""
