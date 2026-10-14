"""Command-line interface commands for agy-skills."""

import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Union

from .discovery import CustomizationRegistry
from .models import Rule, Scope, Skill


def _render_bar(used: int, total: int, width: int = 20) -> str:
    """Render a text progress bar."""
    if total <= 0:
        return "░" * width
    filled = min(width, max(0, int(round((used / total) * width))))
    return "▓" * filled + "░" * (width - filled)


def cli_list(
    registry: CustomizationRegistry,
    scope: Optional[Scope] = None,
    as_json: bool = False,
) -> int:
    """List discovered skills and rules."""
    skills, rules = registry.discover_all()

    if scope:
        skills = [s for s in skills if s.scope == scope]
        rules = [r for r in rules if r.scope == scope]

    if as_json:
        data = {
            "workspace_root": str(registry.workspace_root),
            "token_budget": registry.token_budget,
            "active_tokens": registry.get_total_active_tokens(),
            "skills": [
                {
                    "name": s.name,
                    "scope": s.scope.value,
                    "active": s.is_active,
                    "tokens": s.tokens,
                    "path": str(s.path),
                    "valid": s.is_valid,
                    "description": s.description,
                    "is_overridden": s.is_overridden,
                }
                for s in skills
            ],
            "rules": [
                {
                    "name": r.name,
                    "scope": r.scope.value,
                    "active": r.is_active,
                    "tokens": r.tokens,
                    "size_bytes": r.size_bytes,
                    "path": str(r.path),
                    "valid": r.is_valid,
                    "is_overridden": r.is_overridden,
                }
                for r in rules
            ],
        }
        print(json.dumps(data, indent=2))
        return 0

    active_tok = registry.get_total_active_tokens()
    budget = registry.token_budget
    pct = (active_tok / budget) * 100.0 if budget > 0 else 0.0

    print(f"\n📂 Workspace Root: {registry.workspace_gemini_dir} \033[2m({registry.workspace_root})\033[0m")
    print(f"🏠 Global Config:   {registry.global_config_dir}")
    print(f"📊 Active Context:  {active_tok:,} / {budget:,} tokens ({pct:.1f}%)\n")

    print(f"\033[1;32m=== Antigravity Skills ({len(skills)} found) ===\033[0m")
    if not skills:
        print("  (None found)")
    else:
        for s in skills:
            status = "\033[32m✔ valid\033[0m" if s.is_valid else f"\033[31m✖ {len(s.validation_errors)} error(s)\033[0m"
            act_badge = "\033[32m●\033[0m" if s.is_active else "\033[2m○\033[0m"
            scope_badge = f"[{s.scope.value.upper()}]"
            tok_str = f"~{s.tokens}t"
            print(f"  {act_badge} {s.name:<28} {scope_badge:<11} {tok_str:<6} {status:<20} {s.description[:40]}")

    print(f"\n\033[1;37m=== Antigravity Rules ({len(rules)} found) ===\033[0m")
    if not rules:
        print("  (None found)")
    else:
        for r in rules:
            status = "\033[32m✔ valid\033[0m" if r.is_valid else f"\033[31m✖ {len(r.validation_errors)} error(s)\033[0m"
            act_badge = "\033[32m●\033[0m" if r.is_active else "\033[2m○\033[0m"
            scope_badge = f"[{r.scope.value.upper()}]"
            size_kb = f"{r.size_bytes / 1024:.1f} KB"
            tok_str = f"~{r.tokens}t"
            print(f"  {act_badge} {r.name:<28} {scope_badge:<11} {tok_str:<6} {status:<20} ({size_kb})")

    print("")
    return 0


def cli_status(registry: CustomizationRegistry, as_json: bool = False) -> int:
    """Print context token gauge, active vs disabled count, and compliance audit."""
    skills, rules = registry.discover_all()
    active_tok = registry.get_total_active_tokens()
    budget = registry.token_budget
    pct = (active_tok / budget) * 100.0 if budget > 0 else 0.0

    active_skills = [s for s in skills if s.is_active]
    disabled_skills = [s for s in skills if not s.is_active]
    active_rules = [r for r in rules if r.is_active]
    disabled_rules = [r for r in rules if not r.is_active]

    invalid_skills = [s for s in skills if not s.is_valid]
    invalid_rules = [r for r in rules if not r.is_valid]

    if as_json:
        data = {
            "token_budget": budget,
            "active_tokens": active_tok,
            "used_percent": round(pct, 1),
            "remaining_tokens": max(0, budget - active_tok),
            "counts": {
                "skills_active": len(active_skills),
                "skills_disabled": len(disabled_skills),
                "rules_active": len(active_rules),
                "rules_disabled": len(disabled_rules),
            },
            "compliance": {
                "all_valid": (len(invalid_skills) == 0 and len(invalid_rules) == 0),
                "invalid_skills": [s.name for s in invalid_skills],
                "invalid_rules": [r.name for r in invalid_rules],
            },
        }
        print(json.dumps(data, indent=2))
        return 0

    bar = _render_bar(active_tok, budget, width=20)
    print("\n==================================================")
    print("      Antigravity Status & Token Gauge            ")
    print("==================================================")
    print(f"Context Gauge: [{bar}] {active_tok:,} / {budget:,} tokens ({pct:.1f}% used)")
    print(f"Remaining:     {max(0, budget - active_tok):,} tokens free\n")

    print("Components:")
    print(f"  Skills: {len(active_skills)} active, {len(disabled_skills)} disabled ({len(skills)} total)")
    print(f"  Rules:  {len(active_rules)} active, {len(disabled_rules)} disabled ({len(rules)} total)\n")

    print("Compliance Audit:")
    if not invalid_skills and not invalid_rules:
        print("  ✔ All skills and rules adhere to Antigravity standards.")
    else:
        if invalid_skills:
            print(f"  ✖ {len(invalid_skills)} invalid skill(s): {', '.join(s.name for s in invalid_skills)}")
        if invalid_rules:
            print(f"  ✖ {len(invalid_rules)} invalid rule(s): {', '.join(r.name for r in invalid_rules)}")
    print("")
    return 0


def cli_enable(
    registry: CustomizationRegistry,
    name: str,
    scope: Optional[Scope] = None,
) -> int:
    """Enable a skill or rule deterministically."""
    registry.discover_all()
    item = registry.find_item(name, scope=scope)
    if not item:
        print(f"Error: Item '{name}' not found.", file=sys.stderr)
        return 1

    try:
        registry.set_item_state(item, True)
        item_kind = "Skill" if isinstance(item, Skill) else "Rule"
        print(f"✔ {item_kind} '{item.name}' is now ENABLED in {item.scope.value} scope.")
        return 0
    except Exception as exc:
        print(f"Error enabling '{name}': {exc}", file=sys.stderr)
        return 1


def cli_disable(
    registry: CustomizationRegistry,
    name: str,
    scope: Optional[Scope] = None,
) -> int:
    """Disable a skill or rule deterministically."""
    registry.discover_all()
    item = registry.find_item(name, scope=scope)
    if not item:
        print(f"Error: Item '{name}' not found.", file=sys.stderr)
        return 1

    try:
        registry.set_item_state(item, False)
        item_kind = "Skill" if isinstance(item, Skill) else "Rule"
        print(f"✔ {item_kind} '{item.name}' is now DISABLED in {item.scope.value} scope.")
        return 0
    except Exception as exc:
        print(f"Error disabling '{name}': {exc}", file=sys.stderr)
        return 1


def cli_info(
    registry: CustomizationRegistry,
    name: str,
    as_json: bool = False,
) -> int:
    """Print full metadata, tokens, and markdown content for an item."""
    registry.discover_all()
    item = registry.find_item(name)
    if not item:
        print(f"Error: Item '{name}' not found.", file=sys.stderr)
        return 1

    if as_json:
        if isinstance(item, Skill):
            data: Dict[str, Any] = {
                "type": "skill",
                "name": item.name,
                "scope": item.scope.value,
                "description": item.description,
                "path": str(item.path),
                "skill_file": str(item.skill_file),
                "tokens": item.tokens,
                "is_active": item.is_active,
                "is_valid": item.is_valid,
                "validation_errors": item.validation_errors,
                "content": item.raw_content,
            }
        else:
            data = {
                "type": "rule",
                "name": item.name,
                "scope": item.scope.value,
                "path": str(item.path),
                "size_bytes": item.size_bytes,
                "tokens": item.tokens,
                "is_active": item.is_active,
                "is_valid": item.is_valid,
                "validation_errors": item.validation_errors,
                "content": item.raw_content,
            }
        print(json.dumps(data, indent=2))
        return 0

    if isinstance(item, Skill):
        print(f"\n--- Skill: {item.name} ---")
        print(f"Scope:       {item.scope.value.upper()}")
        print(f"Active:      {'Yes' if item.is_active else 'No'}")
        print(f"Tokens:      ~{item.tokens} tok")
        print(f"Path:        {item.path}")
        print(f"SKILL.md:    {item.skill_file}")
        print(f"Valid:       {'✔ Yes' if item.is_valid else '✖ No'}")
        if item.validation_errors:
            print("Errors:")
            for err in item.validation_errors:
                print(f"  - {err}")
        print(f"\nDescription:\n{item.description}")
        if item.body:
            print(f"\nContent Preview:\n{item.body[:500]}...")
    else:
        print(f"\n--- Rule: {item.name} ---")
        print(f"Scope:       {item.scope.value.upper()}")
        print(f"Active:      {'Yes' if item.is_active else 'No'}")
        print(f"Size:        {item.size_bytes:,} bytes ({item.size_bytes / 1024:.1f} KB)")
        print(f"Tokens:      ~{item.tokens} tok")
        print(f"Path:        {item.path}")
        print(f"Valid:       {'✔ Yes' if item.is_valid else '✖ No'}")
        if item.validation_errors:
            print("Errors:")
            for err in item.validation_errors:
                print(f"  - {err}")
        if item.raw_content:
            print(f"\nContent Preview:\n{item.raw_content[:500]}...")
    print("")
    return 0


def cli_lint(registry: CustomizationRegistry) -> int:
    """Validate all skills and rules; exit 0 if all valid, exit 1 on failures."""
    skills, rules = registry.discover_all()
    has_errors = False

    print("\n🔍 Running Antigravity Validation Suite...\n")

    invalid_skills = [s for s in skills if not s.is_valid]
    if invalid_skills:
        has_errors = True
        print(f"❌ Found issues in {len(invalid_skills)} skill(s):")
        for s in invalid_skills:
            print(f"   [{s.scope.value}] {s.name} ({s.skill_file}):")
            for err in s.validation_errors:
                print(f"     - {err}")
    else:
        print(f"✔ All {len(skills)} skills adhere to Antigravity specifications.")

    invalid_rules = [r for r in rules if not r.is_valid]
    if invalid_rules:
        has_errors = True
        print(f"\n❌ Found issues in {len(invalid_rules)} rule(s):")
        for r in invalid_rules:
            print(f"   [{r.scope.value}] {r.name} ({r.path}):")
            for err in r.validation_errors:
                print(f"     - {err}")
    else:
        print(f"✔ All {len(rules)} rules are within the 24 KB Antigravity size budget.")

    print("")
    return 1 if has_errors else 0


# Backward-compatible aliases for legacy callers
def print_list(registry: CustomizationRegistry, filter_scope: Optional[Scope] = None) -> None:
    cli_list(registry, scope=filter_scope, as_json=False)


def print_status(registry: CustomizationRegistry) -> None:
    cli_status(registry, as_json=False)


def print_lint(registry: CustomizationRegistry, include_catalog: bool = False) -> int:
    return cli_lint(registry)


def print_info(registry: CustomizationRegistry, target_name: str) -> None:
    cli_info(registry, target_name, as_json=False)


def print_tokens(registry: CustomizationRegistry) -> None:
    skills, rules = registry.discover_all()
    active_tok = registry.get_total_active_tokens()
    budget = registry.token_budget
    pct = (active_tok / budget) * 100.0 if budget > 0 else 0.0
    bar = _render_bar(active_tok, budget, width=20)
    print(f"\nTarget Budget:      {budget:,} tokens (Hard Cap)")
    print(f"Context Gauge: [{bar}] {active_tok:,} / {budget:,} tokens ({pct:.1f}% used)\n")


def toggle_customization_cli(
    registry: CustomizationRegistry,
    name: str,
    action: str = "toggle",
    item_type: Optional[str] = None,
    scope: Optional[Scope] = None,
) -> int:
    if action == "enable":
        return cli_enable(registry, name, scope=scope)
    elif action == "disable":
        return cli_disable(registry, name, scope=scope)
    else:
        registry.discover_all()
        item = registry.find_item(name, scope=scope)
        if not item:
            print(f"Error: Item '{name}' not found.", file=sys.stderr)
            return 1
        new_state = not item.is_active
        if new_state:
            return cli_enable(registry, name, scope=scope)
        else:
            return cli_disable(registry, name, scope=scope)
