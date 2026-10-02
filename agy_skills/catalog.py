import os
import re
from typing import Optional, Dict, List
from .types import SkillInfo

FRONTMATTER_REGEX = re.compile(r"^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n([\s\S]*))?")

def parse_simple_frontmatter(content: str) -> tuple[Optional[str], Optional[str]]:
    lines = content.splitlines()
    name = None
    desc_lines = []
    in_desc = False

    for line in lines:
        name_match = re.match(r"^\s*name:\s*(.*)$", line)
        if name_match:
            name = name_match.group(1).strip().strip("'\"")
            in_desc = False
            continue

        desc_match = re.match(r"^\s*description:\s*(.*)$", line)
        if desc_match:
            desc_val = desc_match.group(1).strip()
            if desc_val in (">", ">-", "|", "|-"):
                desc_lines = []
            elif desc_val:
                desc_lines = [desc_val.strip("'\"")]
            in_desc = True
            continue

        if in_desc:
            if re.match(r"^[ \t]+\S", line):
                desc_lines.append(line.strip().strip("'\""))
            else:
                in_desc = False

    description = " ".join(desc_lines).strip() if desc_lines else None
    return name, description

def parse_skill_file(file_path: str, tier: str, fallback_name: Optional[str] = None) -> Optional[SkillInfo]:
    if not os.path.isfile(file_path):
        return None

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        match = FRONTMATTER_REGEX.match(content)
        name, description = None, None
        if match:
            frontmatter_str = match.group(1)
            name, description = parse_simple_frontmatter(frontmatter_str)

        if not name:
            name = fallback_name or os.path.basename(os.path.dirname(file_path))
        if not description:
            description = "No description provided."

        line_count = len(content.splitlines())
        is_link = os.path.islink(file_path) or os.path.islink(os.path.dirname(file_path))

        return SkillInfo(
            name=name,
            description=description,
            path=file_path,
            tier=tier,
            is_symlink=is_link,
            is_builtin=(tier == "builtin"),
            lines_count=line_count,
        )
    except Exception:
        return None

def scan_skills_dir(dir_path: str, tier: str) -> Dict[str, SkillInfo]:
    skills: Dict[str, SkillInfo] = {}
    if not os.path.isdir(dir_path):
        return skills

    for entry in sorted(os.listdir(dir_path)):
        if entry.startswith("."):
            continue
        entry_path = os.path.join(dir_path, entry)

        # Case 1: entry is a directory (or symlink to dir) containing SKILL.md
        if os.path.isdir(entry_path):
            skill_md = os.path.join(entry_path, "SKILL.md")
            if os.path.isfile(skill_md):
                info = parse_skill_file(skill_md, tier, fallback_name=entry)
                if info:
                    skills[info.name] = info
        # Case 2: entry itself is SKILL.md
        elif entry == "SKILL.md" and os.path.isfile(entry_path):
            fallback = os.path.basename(dir_path)
            info = parse_skill_file(entry_path, tier, fallback_name=fallback)
            if info:
                skills[info.name] = info

    return skills

def load_catalog_map(catalog_dirs: List[str]) -> Dict[str, SkillInfo]:
    catalog: Dict[str, SkillInfo] = {}
    for d in catalog_dirs:
        found = scan_skills_dir(d, tier="catalog")
        for k, v in found.items():
            if k not in catalog:
                catalog[k] = v
    return catalog
