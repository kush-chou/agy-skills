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
            status = "● active" if p.is_active else "○ disabled"
            print(f"  • {p.name:<28} [INSTALLED]  {status:<12} ({p.skills_count} skills)")

    if registry.mcp_servers:
        print(f"\n=== Antigravity MCP Servers ({len(registry.mcp_servers)} found) ===")
        for m in registry.mcp_servers:
            status = "● active" if m.is_active else "○ disabled"
            print(f"  • {m.name:<28} [{m.tools_count} tools]  {status:<12}")

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

    found_mcp = next((m for m in registry.mcp_servers if m.name == target_name), None)
    if found_mcp:
        print(f"\n--- MCP Server: {found_mcp.name} ---")
        print(f"Status:      {'● Active' if found_mcp.is_active else '○ Inactive'}")
        print(f"Tools Count: {found_mcp.tools_count}")
        print(f"Path:        {found_mcp.path}")
        print(f"Tools:       {', '.join(found_mcp.tools)}")
        if found_mcp.instructions:
            print(f"Instructions:\n{found_mcp.instructions}")
        return

    from .catalog import CURATED_CATALOG
    found_cat = next((c for c in CURATED_CATALOG if c.name == target_name or c.repo == target_name), None)
    if found_cat:
        print(f"\n--- Marketplace Skill Pack: {found_cat.name} ---")
        print(f"Author:      {found_cat.author}")
        print(f"Repo:        {found_cat.repo} ({found_cat.source_url})")
        print(f"Stars:       ★ {found_cat.stars}")
        print(f"Category:    {found_cat.category}")
        print(f"Trigger:     {found_cat.slash_trigger}")
        print(f"Tokens:      ~{found_cat.tokens} tok")
        print(f"Description: {found_cat.description}")
        return

    print(f"Error: No customization found matching '{target_name}'.", file=sys.stderr)
    sys.exit(1)


def manage_plugin_cli(registry: CustomizationRegistry, plugin_name: str, action: str = "toggle") -> int:
    registry.discover_all()
    target_plugin = next(
        (p for p in registry.plugins if p.name == plugin_name or p.dir_name == plugin_name),
        None,
    )
    if not target_plugin:
        print(f"Error: Plugin '{plugin_name}' not found.", file=sys.stderr)
        return 1

    client = registry.plugin_client
    if not client.is_available():
        print(
            f"Error: Antigravity Language Server not available on port 5387. Cannot update plugin '{plugin_name}'.",
            file=sys.stderr,
        )
        return 1

    if action == "enable":
        new_state = True
    elif action == "disable":
        new_state = False
    else:  # toggle
        new_state = not target_plugin.is_active

    key = target_plugin.dir_name or target_plugin.name
    success = client.set_plugin_enabled(key, new_state)
    if success:
        state_str = "ENABLED" if new_state else "DISABLED"
        print(f"✔ Plugin '{key}' is now {state_str} (zero restart).")
        return 0
    else:
        print(f"✖ Failed to update plugin '{key}'.", file=sys.stderr)
        return 1


def print_search(query: str, workspace_root: Path, home_dir: Optional[Path] = None) -> None:
    from .catalog import check_installed_status, search_catalog

    check_installed_status(workspace_root, home_dir)
    results = search_catalog(query)

    print(f"\n🌐 Antigravity Skill Marketplace (Matching '{query}'):")
    print(f"   Showing {len(results)} verified pack(s) from SkillLeaderboard & VoltAgent\n")

    for pack in results:
        status = "✔ Installed" if pack.is_installed else "○ Available"
        stars_badge = f"★ {pack.stars}"
        tok_badge = f"~{pack.tokens}t"
        print(f"  • {pack.name:<26} {stars_badge:<10} {tok_badge:<6} {pack.category:<16} {status:<12}")
        print(f"    {pack.description}")
        print(f"    Trigger: {pack.slash_trigger:<18} Source: {pack.source_url}\n")


def run_install(pack_name: str, scope: Scope, workspace_root: Path, home_dir: Optional[Path] = None) -> int:
    from .catalog import install_catalog_pack

    home = home_dir or Path.home()
    if scope == Scope.GLOBAL:
        target_dir = home / ".gemini" / "config" / "skills"
        scope_str = "Global (~/.gemini/config/skills)"
    else:
        target_dir = workspace_root / ".agents" / "skills"
        scope_str = f"Workspace ({workspace_root}/.agents/skills)"

    success, message = install_catalog_pack(pack_name, target_dir, scope_str)
    print(f"\n{message}\n")
    return 0 if success else 1


if __name__ == "__main__":
    from .main import main
    main()
