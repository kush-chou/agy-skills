"""Data models for Antigravity Skills and Rules."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import re
from typing import Dict, List, Optional, Tuple


class Scope(str, Enum):
    WORKSPACE = "workspace"
    GLOBAL = "global"


class EntityType(str, Enum):
    SKILL = "skill"
    RULE = "rule"


@dataclass
class TokenBudget:
    limit: int = 20_000


DEFAULT_TOKEN_BUDGET: int = 20_000


def estimate_tokens(text: str) -> int:
    """Estimate token count from raw text content (~3.5 chars/token)."""
    if not text:
        return 0
    return max(1, round(len(text) / 3.5))


def parse_frontmatter(content: str) -> Tuple[Dict[str, str], str]:
    """Extract YAML frontmatter and body from markdown content."""
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
        key_match = re.match(r"^([a-zA-Z0-9_-]+):\s*(.*)$", line)
        if key_match:
            if current_key and multiline_val:
                frontmatter[current_key] = " ".join(multiline_val).strip()
                multiline_val = []

            current_key = key_match.group(1)
            raw_val = key_match.group(2).strip()

            if raw_val in (">-", ">", "|", "|-"):
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
    tokens: int = 0
    is_active: bool = True
    is_valid: bool = True
    validation_errors: List[str] = field(default_factory=list)
    raw_content: str = ""
    body: str = ""
    is_overridden: bool = False
    scripts: List[Path] = field(default_factory=list)
    references: List[Path] = field(default_factory=list)
    examples: List[Path] = field(default_factory=list)
    resources: List[Path] = field(default_factory=list)
    aliases: List[Path] = field(default_factory=list)

    @classmethod
    def from_directory(cls, dir_path: Path, scope: Scope) -> Optional["Skill"]:
        skill_file = dir_path / "SKILL.md"
        if not skill_file.is_file():
            return None

        content = skill_file.read_text(encoding="utf-8", errors="replace")
        frontmatter, body = parse_frontmatter(content)
        name = frontmatter.get("name", dir_path.name)
        description = frontmatter.get("description", "")
        tokens = estimate_tokens(content)

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
            tokens=tokens,
            raw_content=content,
            body=body,
            is_active=True,
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
    tokens: int = 0
    is_active: bool = True
    is_valid: bool = True
    validation_errors: List[str] = field(default_factory=list)
    raw_content: str = ""
    description: str = ""
    is_overridden: bool = False
    aliases: List[Path] = field(default_factory=list)

    @classmethod
    def from_file(cls, file_path: Path, scope: Scope, name_override: Optional[str] = None) -> Optional["Rule"]:
        if not file_path.is_file():
            return None

        content = file_path.read_text(encoding="utf-8", errors="replace")
        size_bytes = file_path.stat().st_size
        name = name_override or file_path.name
        tokens = estimate_tokens(content)
        is_valid = size_bytes <= 24576

        desc = ""
        for line in content.splitlines():
            clean = line.strip()
            if not clean:
                continue
            if clean.startswith("#"):
                clean = clean.lstrip("#").strip()
            if clean and not desc:
                desc = clean
                break

        return cls(
            name=name,
            path=file_path,
            scope=scope,
            size_bytes=size_bytes,
            tokens=tokens,
            is_active=True,
            is_valid=is_valid,
            raw_content=content,
            description=desc,
        )
