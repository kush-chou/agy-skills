"""Command-line interface and diagnostic tools for agy-skills."""

import argparse
from pathlib import Path
import sys
from typing import Optional

from .discovery import CustomizationRegistry
from .models import Scope


def print_list(registry: CustomizationRegistry) -> None:
    skills, rules = registry.discover_all()
    active_tok = registry.get_total_active_tokens()
    budget = registry.token_budget
    pct = (active_tok / budget) * 100.0 if budget > 0 else 0.0

    print(f"\n📂 Workspace Root: {registry.workspace_root}")
    print(f"🏠 Global Config:   {registry.global_config_dir}")
    print(f"📊 Active Context:  {active_tok:,} / {budget:,} tokens ({pct:.1f}%)\n")

    print(f"=== Antigravity Skills ({len(skills)} found) ===")
    if not skills:
        print("  (None found)")
    else:
        for s in skills:
            status = "✔ valid" if s.is_valid else f"✖ {len(s.validation_errors)} error(s)"
            scope_badge = f"[{s.scope.value.upper()}]"
            tok_str = f"~{s.tokens}t"
            print(f"  • {s.name:<28} {scope_badge:<11} {tok_str:<6} {status:<12} {s.description[:40]}...")

    print(f"\n=== Antigravity Rules ({len(rules)} found) ===")
    if not rules:
        print("  (None found)")
    else:
        for r in rules:
            status = "✔ valid" if r.is_valid else f"✖ {len(r.validation_errors)} error(s)"
            scope_badge = f"[{r.scope.value.upper()}]"
            size_kb = f"{r.size_bytes / 1024:.1f} KB"
            tok_str = f"~{r.tokens}t"
            print(f"  • {r.name:<28} {scope_badge:<11} {tok_str:<6} {status:<12} ({size_kb})")

    if registry.subagents:
        print(f"\n=== Antigravity Subagents ({len(registry.subagents)} found) ===")
        for sub in registry.subagents:
            tier_badge = f"[{sub.tier}]"
            print(f"  • {sub.name:<28} {tier_badge:<11} {sub.role}")

    if registry.plugins:
        print(f"\n=== Antigravity Plugins ({len(registry.plugins)} found) ===")
        for p in registry.plugins:
            print(f"  • {p.name:<28} [INSTALLED]  ({p.skills_count} skills)")

    print("")


def print_lint(registry: CustomizationRegistry, include_catalog: bool = False) -> int:
    skills, rules = registry.discover_all()
    has_errors = False

    print("\n🔍 Running Antigravity Validation Suite...\n")

    # Lint workspace, built-in, and global skills
    target_skills = [s for s in skills if s.scope in (Scope.WORKSPACE, Scope.GLOBAL, Scope.BUILTIN)] if not include_catalog else skills
    invalid_skills = [s for s in target_skills if not s.is_valid]
    if invalid_skills:
        has_errors = True
        print(f"❌ Found issues in {len(invalid_skills)} skill(s):")
        for s in invalid_skills:
            print(f"   [{s.scope.value}] {s.name} ({s.skill_file}):")
            for err in s.validation_errors:
                print(f"     - {err}")
    else:
        print(f"✔ All {len(target_skills)} active scope skills adhere to Antigravity specifications.")

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


def print_info(registry: CustomizationRegistry, target_name: str) -> None:
    skills, rules = registry.discover_all()

    found_skill = next((s for s in skills if s.name == target_name), None)
    if found_skill:
        print(f"\n--- Skill: {found_skill.name} ---")
        print(f"Scope:         {found_skill.scope.value}")
        print(f"Directory:     {found_skill.path}")
        print(f"SKILL.md:      {found_skill.skill_file}")
        print(f"Author:        {found_skill.author}")
        print(f"Slash Trigger: {found_skill.slash_trigger}")
        print(f"Tokens:        ~{found_skill.tokens} tok")
        print(f"Description:   {found_skill.description}")
        print(f"Scripts:       {[p.name for p in found_skill.scripts]}")
        print(f"References:    {[p.name for p in found_skill.references]}")
        print(f"Status:        {'✔ Valid' if found_skill.is_valid else '✖ Invalid'}")
        if found_skill.validation_errors:
            print("Errors:")
            for e in found_skill.validation_errors:
                print(f"  - {e}")
        return

    found_rule = next((r for r in rules if r.name == target_name or r.path.name == target_name), None)
    if found_rule:
        print(f"\n--- Rule: {found_rule.name} ---")
        print(f"Scope:  {found_rule.scope.value}")
        print(f"Path:   {found_rule.path}")
        print(f"Size:   {found_rule.size_bytes:,} bytes ({found_rule.size_bytes / 1024:.2f} KB)")
        print(f"Tokens: ~{found_rule.tokens} tok")
        print(f"Status: {'✔ Valid' if found_rule.is_valid else '✖ Invalid'}")
        if found_rule.validation_errors:
            print("Errors:")
            for e in found_rule.validation_errors:
                print(f"  - {e}")
        return

    found_sub = next((sub for sub in registry.subagents if sub.name == target_name), None)
    if found_sub:
        print(f"\n--- Subagent: {found_sub.name} ---")
        print(f"Tier:   {found_sub.tier}")
        print(f"Role:   {found_sub.role}")
        print(f"Model:  {found_sub.model}")
        print(f"Tokens: ~{found_sub.tokens} tok")
        print(f"Tools:  {', '.join(found_sub.tools)}")
        print(f"Desc:   {found_sub.description}")
        return

    found_plug = next((p for p in registry.plugins if p.name == target_name), None)
    if found_plug:
        print(f"\n--- Plugin: {found_plug.name} ---")
        print(f"Tier:   {found_plug.tier}")
        print(f"Path:   {found_plug.path}")
        print(f"Skills: {found_plug.skills_count}")
        print(f"Desc:   {found_plug.description}")
        return

    print(f"Error: No customization found matching '{target_name}'.", file=sys.stderr)
    sys.exit(1)
