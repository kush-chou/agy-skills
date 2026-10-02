import os
import re
from typing import Optional, Dict, List, Tuple
from .types import SkillInfo, RuleInfo, SubagentInfo

FRONTMATTER_REGEX = re.compile(r"^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n([\s\S]*))?")

def estimate_tokens(text: str) -> int:
    """Estimates tokens using standard LLM ratio ~3.8 characters per token."""
    if not text:
        return 0
    return max(1, int(len(text) / 3.8))

def detect_collection(name: str) -> str:
    n = name.lower()

    # Google Official Built-ins
    if n in ("antigravity-guide", "antigravity_guide", "agy-customizations", "generative_ui",
            "migrate-workflows", "permissioned-github", "ui-extension", "ui-plugin-navigation",
            "plugin", "automation"):
        return "@google/antigravity-builtin"

    # Google Stitch Suite
    if n.startswith("stitch-") or "stitch" in n:
        return "@google/stitch"

    # Google LiteRT Suite
    if n.startswith("litert-") or "litert" in n or "quantization" in n:
        return "@google/litert"

    # Android Suite
    if ("android" in n or n.startswith("r8-") or "appfunctions" in n or "camerax" in n or
        "navigation" in n or "edge-to-edge" in n or "wear-compose" in n or "leanback" in n or
        "glimmer" in n or "media3" in n or "play-billing" in n or "play-policy" in n or
        "engage-sdk" in n or "agp-9" in n or n == "styles" or n == "adaptive" or
        "migrate-xml-views-to-jetpack-compose" in n or "restore-credentials" in n or "verified-email" in n):
        return "@android"

    # Matt Pocock Engineering Skills
    if ("matt" in n or "ts-" in n or n in (
        "teach", "spec-driven-development", "setup-ts-deep-modules", "setup-matt-pocock-skills",
        "to-spec", "to-tickets", "to-questionnaire", "implement-spec", "diagnosing-bugs",
        "scaffold-exercises", "triage", "wayfinder", "ask-matt", "code-simplification",
        "domain-modeling", "codebase-design", "improve-codebase-architecture"
    )):
        return "@mattpocock"

    # Addy Osmani Engineering Skills
    if "addy" in n or "perf" in n or "web-performance" in n or n in ("cuttle", "performance-optimization"):
        return "@addyosmani"

    # Antigravity Philosophy & Agents
    if n in ("karpathy-principles", "torvalds-principles", "mantis", "nautilus", "conversational-cadence", "mutual-amplification", "visual-priming", "context-hygiene", "surgical-inference", "tasteful-abstraction"):
        return "@antigravity/principles"

    return "@community/core"

def parse_simple_frontmatter(content: str) -> Tuple[Optional[str], Optional[str], Dict[str, str]]:
    lines = content.splitlines()
    name = None
    desc_lines = []
    in_desc = False
    extra: Dict[str, str] = {}

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

        role_match = re.match(r"^\s*role:\s*(.*)$", line)
        if role_match:
            extra["role"] = role_match.group(1).strip().strip("'\"")
            continue

        always_match = re.match(r"^\s*always_on:\s*(.*)$", line)
        if always_match:
            extra["always_on"] = always_match.group(1).strip().lower()
            continue

        if in_desc:
            if re.match(r"^[ \t]+\S", line):
                desc_lines.append(line.strip().strip("'\""))
            else:
                in_desc = False

    description = " ".join(desc_lines).strip() if desc_lines else None
    return name, description, extra

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
            name, description, _ = parse_simple_frontmatter(frontmatter_str)

        if not name:
            name = fallback_name or os.path.basename(os.path.dirname(file_path))
        if not description:
            description = "No description provided."

        line_count = len(content.splitlines())
        is_link = os.path.islink(file_path) or os.path.islink(os.path.dirname(file_path))

        # Only the declaration (name + desc + path) counts toward always-on prompt budget for skills
        skill_decl = f"- {name}: {description}\nPath: {file_path}"
        tokens = estimate_tokens(skill_decl)

        return SkillInfo(
            name=name,
            description=description,
            path=file_path,
            tier=tier,
            is_symlink=is_link,
            is_builtin=(tier == "builtin"),
            lines_count=line_count,
            token_cost=tokens,
            collection=detect_collection(name),
        )
    except Exception:
        return None

def scan_skills_dir(dir_path: str, tier: str) -> Dict[str, SkillInfo]:
    skills: Dict[str, SkillInfo] = {}
    if not os.path.isdir(dir_path):
        return skills

    # Recursively find all SKILL.md files (following symlinks for active directories)
    for root, dirs, files in os.walk(dir_path, followlinks=True):
        # Exclude hidden directories
        dirs[:] = [d for d in dirs if not d.startswith(".")]

        if "SKILL.md" in files:
            skill_md = os.path.join(root, "SKILL.md")
            fallback = os.path.basename(root)
            info = parse_skill_file(skill_md, tier, fallback_name=fallback)
            if info:
                skills[info.name] = info

    return skills

def parse_rule_file(file_path: str, tier: str, fallback_name: Optional[str] = None) -> Optional[RuleInfo]:
    if not os.path.isfile(file_path):
        return None

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        match = FRONTMATTER_REGEX.match(content)
        name = fallback_name or os.path.basename(file_path).replace(".md", "")
        description = "System invariant rule."
        is_always_on = True

        if match:
            frontmatter_str = match.group(1)
            parsed_name, parsed_desc, extra = parse_simple_frontmatter(frontmatter_str)
            if parsed_name:
                name = parsed_name
            if parsed_desc:
                description = parsed_desc
                # If rule has a description frontmatter, Antigravity treats it as conditional
                is_always_on = False
            if "always_on" in extra:
                is_always_on = (extra["always_on"] == "true")

        line_count = len(content.splitlines())
        is_link = os.path.islink(file_path)

        # Full body is injected into prompt if always-on; only description if conditional
        cost_text = content if is_always_on else f"- {file_path}: {description}"
        tokens = estimate_tokens(cost_text)

        return RuleInfo(
            name=name,
            description=description,
            path=file_path,
            tier=tier,
            is_always_on=is_always_on,
            is_symlink=is_link,
            lines_count=line_count,
            token_cost=tokens,
            collection=detect_collection(name),
        )
    except Exception:
        return None

def scan_rules_dir(dir_path: str, tier: str) -> Dict[str, RuleInfo]:
    rules: Dict[str, RuleInfo] = {}
    if not os.path.isdir(dir_path):
        return rules

    for entry in sorted(os.listdir(dir_path)):
        if entry.startswith(".") or not entry.endswith(".md"):
            continue
        entry_path = os.path.join(dir_path, entry)
        info = parse_rule_file(entry_path, tier, fallback_name=entry.replace(".md", ""))
        if info:
            rules[info.name] = info

    return rules

def parse_subagent_file(file_path: str, tier: str, fallback_name: Optional[str] = None) -> Optional[SubagentInfo]:
    if not os.path.isfile(file_path):
        return None

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        match = FRONTMATTER_REGEX.match(content)
        name = fallback_name or os.path.basename(file_path).replace(".md", "")
        role = "Specialized Agent"
        description = "Subagent worker"

        if match:
            frontmatter_str = match.group(1)
            parsed_name, parsed_desc, extra = parse_simple_frontmatter(frontmatter_str)
            if parsed_name:
                name = parsed_name
            if parsed_desc:
                description = parsed_desc
            if "role" in extra:
                role = extra["role"]

        line_count = len(content.splitlines())
        is_link = os.path.islink(file_path)
        # Subagent declaration token cost in system prompt
        decl = f"- {name}: {role}. {description}"
        tokens = estimate_tokens(decl)

        return SubagentInfo(
            name=name,
            role=role,
            description=description,
            path=file_path,
            tier=tier,
            is_symlink=is_link,
            lines_count=line_count,
            token_cost=tokens,
            collection=detect_collection(name),
        )
    except Exception:
        return None

def scan_subagents_dir(dir_path: str, tier: str) -> Dict[str, SubagentInfo]:
    subagents: Dict[str, SubagentInfo] = {}
    if not os.path.isdir(dir_path):
        return subagents

    for entry in sorted(os.listdir(dir_path)):
        if entry.startswith(".") or not entry.endswith(".md"):
            continue
        entry_path = os.path.join(dir_path, entry)
        info = parse_subagent_file(entry_path, tier, fallback_name=entry.replace(".md", ""))
        if info:
            subagents[info.name] = info

    return subagents

def load_catalog_map(catalog_dirs: List[str]) -> Dict[str, SkillInfo]:
    catalog: Dict[str, SkillInfo] = {}
    for d in catalog_dirs:
        found = scan_skills_dir(d, tier="catalog")
        for k, v in found.items():
            if k not in catalog:
                catalog[k] = v
    return catalog
