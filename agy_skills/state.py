"""Deterministic JSON configuration state management for agy-skills.

Handles reading and atomic writing of workspace and global configurations:
- Workspace: <workspace>/.agents/config.json (fallback: <workspace>/.gemini/config.json)
- Global: ~/.gemini/config/config.json

Schema:
{
  "skills": {
    "<skill_name>": { "enabled": true }
  },
  "rules": {
    "<rule_name>": { "enabled": true }
  }
}

Zero silent failures: all file operations propagate explicit I/O and JSON decoding errors.
"""

import json
import os
from pathlib import Path
import tempfile
from typing import Any, Dict, Optional, Tuple

from .models import Scope


def get_workspace_config_path(workspace_root: Path) -> Path:
    """Resolve the active config.json path for a workspace with fallback logic."""
    agents_cfg = workspace_root / ".agents" / "config.json"
    gemini_cfg = workspace_root / ".gemini" / "config.json"

    if agents_cfg.is_file():
        return agents_cfg
    if gemini_cfg.is_file():
        return gemini_cfg

    if (workspace_root / ".agents").is_dir():
        return agents_cfg
    if (workspace_root / ".gemini").is_dir():
        return gemini_cfg

    return agents_cfg


def get_global_config_path(home_dir: Optional[Path] = None) -> Path:
    """Return the canonical global config.json path (~/.gemini/config/config.json)."""
    home = home_dir or Path.home()
    return home / ".gemini" / "config" / "config.json"


def read_config(path: Path) -> Dict[str, Any]:
    """Read and parse a JSON configuration file.

    Propagates IOError, PermissionError, and json.JSONDecodeError on corrupt or unreadable files.
    Missing files return an empty dictionary.
    """
    if not path.exists():
        return {}

    if not path.is_file():
        raise IOError(f"Config path '{path}' exists but is not a regular file.")

    content = path.read_text(encoding="utf-8")
    if not content.strip():
        return {}

    data = json.loads(content)
    if not isinstance(data, dict):
        raise ValueError(f"Config at '{path}' must be a JSON object, got {type(data).__name__}.")
    return data


def write_config(path: Path, data: Dict[str, Any]) -> None:
    """Atomically write configuration data to the target file.

    Ensures parent directories exist, writes to a temporary file in the target directory,
    flushes, and replaces the target file atomically.
    Propagates any filesystem or permission errors.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    # Use atomic file replacement in the same filesystem directory
    tmp_fd, tmp_path_str = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    tmp_path = Path(tmp_path_str)
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())

        os.replace(tmp_path, path)
    except Exception:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise


def is_skill_enabled(config: Dict[str, Any], name: str, default: bool = True) -> bool:
    """Return whether a skill is enabled in the configuration."""
    skills = config.get("skills", {})
    if isinstance(skills, dict) and name in skills:
        entry = skills[name]
        if isinstance(entry, dict) and "enabled" in entry:
            return bool(entry["enabled"])
    return default


def set_skill_enabled(config: Dict[str, Any], name: str, enabled: bool) -> None:
    """Update enabled state for a skill in configuration dictionary."""
    skills = config.setdefault("skills", {})
    if not isinstance(skills, dict):
        skills = {}
        config["skills"] = skills

    if name in skills and isinstance(skills[name], dict):
        skills[name]["enabled"] = enabled
    else:
        skills[name] = {"enabled": enabled}


def is_rule_enabled(config: Dict[str, Any], name: str, default: bool = True) -> bool:
    """Return whether a rule is enabled in the configuration."""
    rules = config.get("rules", {})
    if isinstance(rules, dict) and name in rules:
        entry = rules[name]
        if isinstance(entry, dict) and "enabled" in entry:
            return bool(entry["enabled"])
    return default


def set_rule_enabled(config: Dict[str, Any], name: str, enabled: bool) -> None:
    """Update enabled state for a rule in configuration dictionary."""
    rules = config.setdefault("rules", {})
    if not isinstance(rules, dict):
        rules = {}
        config["rules"] = rules

    if name in rules and isinstance(rules[name], dict):
        rules[name]["enabled"] = enabled
    else:
        rules[name] = {"enabled": enabled}


def load_config_for_scope(
    scope: Scope,
    workspace_root: Path,
    home_dir: Optional[Path] = None,
) -> Tuple[Path, Dict[str, Any]]:
    """Load the appropriate config.json path and data for a given scope."""
    if scope == Scope.WORKSPACE:
        cfg_path = get_workspace_config_path(workspace_root)
    else:
        cfg_path = get_global_config_path(home_dir)

    data = read_config(cfg_path)
    return cfg_path, data


def save_config_for_scope(
    scope: Scope,
    data: Dict[str, Any],
    workspace_root: Path,
    home_dir: Optional[Path] = None,
) -> Path:
    """Save configuration data to the target file for a given scope."""
    if scope == Scope.WORKSPACE:
        cfg_path = get_workspace_config_path(workspace_root)
    else:
        cfg_path = get_global_config_path(home_dir)

    write_config(cfg_path, data)
    return cfg_path
