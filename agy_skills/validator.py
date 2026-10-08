"""Validator for Antigravity skills and rules."""

from pathlib import Path
import re
from typing import List

from .models import Rule, Skill

MAX_RULE_SIZE_BYTES = 24_000  # 24 KB Antigravity hard cap


def validate_skill(skill: Skill) -> List[str]:
    """Validate a Skill according to Antigravity rules and conventions."""
    errors: List[str] = []

    # 1. Name format: kebab-case
    if not skill.name:
        errors.append("Skill missing 'name' in YAML frontmatter.")
    elif not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", skill.name):
        errors.append(f"Skill name '{skill.name}' must be lowercase-hyphenated (kebab-case).")

    # 2. Name matches directory
    if skill.name and skill.path.name != skill.name:
        errors.append(f"Directory name '{skill.path.name}' does not match skill name '{skill.name}'.")

    # 3. Description checks
    if not skill.description or not skill.description.strip():
        errors.append("Skill missing 'description' in YAML frontmatter.")
    elif len(skill.description.strip()) < 20:
        errors.append("Skill description is too brief (recommended: at least 20 chars specifying what and when).")

    # 4. SKILL.md file existence
    if not skill.skill_file.is_file():
        errors.append("Missing required 'SKILL.md' file.")

    skill.validation_errors = errors
    skill.is_valid = len(errors) == 0
    return errors


def validate_rule(rule: Rule) -> List[str]:
    """Validate a Rule according to Antigravity rules and conventions."""
    errors: List[str] = []

    # 1. 24,000 bytes hard cap
    if rule.size_bytes > MAX_RULE_SIZE_BYTES:
        errors.append(
            f"Rule exceeds 24 KB limit ({rule.size_bytes:,} bytes > {MAX_RULE_SIZE_BYTES:,} bytes). "
            "Antigravity will truncate rules over 24,000 bytes."
        )

    # 2. Non-empty
    if rule.size_bytes == 0 or not rule.raw_content.strip():
        errors.append("Rule file is empty.")

    rule.validation_errors = errors
    rule.is_valid = len(errors) == 0
    return errors
