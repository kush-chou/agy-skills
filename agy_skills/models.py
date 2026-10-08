"""Data models for Antigravity Skills, Rules, Subagents, and Plugins."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import re
from typing import Dict, List, Optional, Tuple


class Scope(str, Enum):
    WORKSPACE = "workspace"
    GLOBAL = "global"
    BUILTIN = "builtin"
    CATALOG = "catalog"


class EntityType(str, Enum):
    SKILL = "skill"
    RULE = "rule"
    SUBAGENT = "subagent"
    PLUGIN = "plugin"


def estimate_tokens(text: str) -> int:
    """Estimate token count for prompt listing / documentation text."""
    if not text:
        return 0
    return max(1, round(len(text) / 2.75))


def parse_frontmatter(content: str) -> Tuple[Dict[str, str], str]:
    """Extract frontmatter and body from markdown content."""
    frontmatter: Dict[str, str] = {}
    body = content

    pattern = r"^---\s*\n(.*?)\n---\s*\n(.*)$"
    match = re.match(pattern, content, re.DOTALL)
    if not match:
        return frontmatter, body

    fm_text, body = match.group(1), match.group(2)
    current_key: Optional[str] = None
    multiline_val: List[str] = []

    for line in fm_text.splitlines():
        # Check for new key: value
        key_match = re.match(r"^([a-zA-Z0-9_-]+):\s*(.*)$", line)
        if key_match:
            if current_key and multiline_val:
                frontmatter[current_key] = " ".join(multiline_val).strip()
                multiline_val = []

            current_key = key_match.group(1)
            raw_val = key_match.group(2).strip()

            if raw_val in (">-", ">", "|", "|-"):
                # Multiline folded/literal indicator
                multiline_val = []
            else:
                frontmatter[current_key] = raw_val.strip("\"'")
        elif current_key and (line.startswith("  ") or line.startswith("\t")):
            multiline_val.append(line.strip())

    if current_key and multiline_val:
        frontmatter[current_key] = " ".join(multiline_val).strip()

    return frontmatter, body


@dataclass
class Skill:
    name: str
    description: str
    path: Path
    skill_file: Path
    scope: Scope
    raw_content: str = ""
    body: str = ""
    author: str = "Google Antigravity"
    slash_trigger: str = ""
    tier: str = "WORKSPACE"
    tokens: int = 0
    is_active: bool = True
    is_overridden: bool = False
    scripts: List[Path] = field(default_factory=list)
    references: List[Path] = field(default_factory=list)
    examples: List[Path] = field(default_factory=list)
    resources: List[Path] = field(default_factory=list)
    is_valid: bool = True
    validation_errors: List[str] = field(default_factory=list)

    @classmethod
    def from_directory(cls, dir_path: Path, scope: Scope) -> Optional["Skill"]:
        skill_file = dir_path / "SKILL.md"
        if not skill_file.is_file():
            return None

        try:
            content = skill_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return None

        frontmatter, body = parse_frontmatter(content)
        name = frontmatter.get("name", dir_path.name)
        description = frontmatter.get("description", "")
        author = frontmatter.get("author", "Google Antigravity")
        slash_trigger = frontmatter.get("slash_trigger", f"/{name}")
        override = frontmatter.get("override", "").lower() in ("true", "1", "yes")

        tier_map = {
            Scope.WORKSPACE: "WORKSPACE",
            Scope.GLOBAL: "GLOBAL",
            Scope.BUILTIN: "BUILT-IN",
            Scope.CATALOG: "CATALOG AVAILABLE",
        }
        tier = tier_map.get(scope, "WORKSPACE")
        listing = f"- {name}: {description}"
        tokens = estimate_tokens(listing)

        # Inactive by default if in Catalog
        is_active = (scope != Scope.CATALOG)

        def list_dir_files(sub: str) -> List[Path]:
            p = dir_path / sub
            if p.is_dir():
                return sorted([f for f in p.iterdir() if f.is_file()])
            return []

        return cls(
            name=name,
            description=description,
            path=dir_path,
            skill_file=skill_file,
            scope=scope,
            raw_content=content,
            body=body,
            author=author,
            slash_trigger=slash_trigger,
            tier=tier,
            tokens=tokens,
            is_active=is_active,
            is_overridden=override,
            scripts=list_dir_files("scripts"),
            references=list_dir_files("references"),
            examples=list_dir_files("examples"),
            resources=list_dir_files("resources"),
        )


@dataclass
class Rule:
    name: str
    path: Path
    scope: Scope
    size_bytes: int = 0
    raw_content: str = ""
    tier: str = "WORKSPACE"
    tokens: int = 0
    is_active: bool = True
    is_valid: bool = True
    validation_errors: List[str] = field(default_factory=list)

    @classmethod
    def from_file(cls, file_path: Path, scope: Scope, name_override: Optional[str] = None) -> Optional["Rule"]:
        if not file_path.is_file():
            return None

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            size_bytes = file_path.stat().st_size
        except Exception:
            return None

        name = name_override or file_path.name
        tier = "WORKSPACE" if scope == Scope.WORKSPACE else "GLOBAL"
        tokens = estimate_tokens(content)

        return cls(
            name=name,
            path=file_path,
            scope=scope,
            size_bytes=size_bytes,
            raw_content=content,
            tier=tier,
            tokens=tokens,
            is_active=True,
        )


@dataclass
class Subagent:
    name: str
    role: str
    description: str
    tier: str = "BUILT-IN"
    scope: Scope = Scope.BUILTIN
    model: str = "inherit"
    system_prompt: str = ""
    tokens: int = 0
    is_active: bool = True
    tools: List[str] = field(default_factory=list)
    path: Optional[Path] = None


@dataclass
class Plugin:
    name: str
    path: Path
    tier: str = "INSTALLED"
    scope: Scope = Scope.GLOBAL
    author: str = "Google Cloud / Ecosystem"
    description: str = ""
    skills_count: int = 0
    tokens: int = 0
    is_active: bool = True
    skills: List[str] = field(default_factory=list)
    mcp_servers: List[str] = field(default_factory=list)
