"""Command-line interface and diagnostic tools for agy-skills."""

import argparse
from pathlib import Path
import sys
from typing import Optional

from .discovery import CustomizationRegistry
from .models import Plugin, Scope


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
            print(f"  • {p.name:<28} [INSTALLED]  {status:<12} ~{p.tokens:,} tok  ({p.skills_count} skills)")

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
        print_plugin_info(found_plug)
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


def print_plugin_info(p: Plugin, show_breakdowns: bool = True) -> None:
    """Print complete Antigravity IDE Customizations view for a plugin."""
    budget = 20_000
    pct = (p.tokens / budget) * 100.0

    print(f"\n\033[1;36mCustomizations\033[0m / \033[1;37m{p.name}\033[0m  \033[2m(Version {p.version})\033[0m")
    print("=" * 68)
    if p.description:
        print(f"{p.description}\n")

    if p.suggested_prompts:
        print("\033[1;33mSuggested Prompts / Examples:\033[0m")
        for sp in p.suggested_prompts:
            print(f"  • \"{sp}\"")
        print("")

    if p.resources:
        print("\033[1;33mResources:\033[0m")
        for res in p.resources:
            url_str = f" \033[2m({res['url']})\033[0m" if res.get("url") else ""
            print(f"  • \033[1;34m{res.get('title', '')}\033[0m [↗]{url_str}")
        print("")

    if p.commands:
        print(f"\033[1;32mCommands ({len(p.commands)}) ▼\033[0m")
        for trig, desc, tok in p.commands:
            print(f"  • \033[1;36m{trig:<32}\033[0m \033[33m(~{tok} tok)\033[0m")
            if desc:
                print(f"    {desc}")
        print("")

    if p.agents:
        print(f"\033[1;35mAgents ({len(p.agents)}) ▼\033[0m")
        for ag_name, ag_desc, ag_tok in p.agents:
            print(f"  • \033[1;35m{ag_name:<32}\033[0m \033[33m(~{ag_tok} tok)\033[0m")
            if ag_desc:
                print(f"    {ag_desc}")
        print("")

    if p.mcp_servers or p.mcp_tools:
        cnt = len(p.mcp_servers) or len(p.mcp_tools)
        print(f"\033[1;34mMCP servers ({cnt}) ▼\033[0m")
        for srv in p.mcp_servers:
            print(f"  • {srv}")
        print("")

    if p.rules:
        print(f"\033[1;33mRules ({len(p.rules)}) ▼\033[0m")
        for r_name, r_desc, r_tok in p.rules:
            tok_badge = f"\033[33m(~{r_tok} tok)\033[0m" if r_tok else ""
            print(f"  • \033[1;33m{r_name:<32}\033[0m {tok_badge}")
            if r_desc:
                print(f"    {r_desc}")
        print("")

    # Context usage
    print(f"\033[1;37mContext usage ({p.tokens:,} tokens)\033[0m")
    print(f"Customizations    {p.tokens:,} / {budget:,} tokens ({pct:.1f}%)")

    # Colored segmented ANSI bar
    bar_len = 32
    s_blocks = int(round((p.skills_tokens / budget) * bar_len))
    m_blocks = int(round((p.mcp_tokens / budget) * bar_len))
    a_blocks = int(round((p.agents_tokens / budget) * bar_len))
    r_blocks = int(round((p.rules_tokens / budget) * bar_len))
    rem_blocks = max(0, bar_len - (s_blocks + m_blocks + a_blocks + r_blocks))

    seg_bar = (
        f"\033[34m{'█' * s_blocks}\033[0m"
        f"\033[32m{'█' * m_blocks}\033[0m"
        f"\033[36m{'█' * a_blocks}\033[0m"
        f"\033[33m{'█' * r_blocks}\033[0m"
        f"\033[2m{'░' * rem_blocks}\033[0m"
    )
    print(f"[{seg_bar}]")

    # Category summaries matching IDE GUI
    if p.skills_tokens or p.commands:
        s_pct = (p.skills_tokens / budget) * 100.0
        print(f"  • \033[34mSkills\033[0m ({p.skills_tokens:,} tokens) {s_pct:.1f}%      \033[2mShow {len(p.commands)} breakdowns\033[0m")
    if p.mcp_tokens or p.mcp_tools:
        m_pct = (p.mcp_tokens / budget) * 100.0
        warn_str = f"  \033[33m⚠️ {p.excluded_tools_count} excluded\033[0m" if p.excluded_tools_count else ""
        print(f"  • \033[32mMcp Tools\033[0m ({p.mcp_tokens:,} tokens) {m_pct:.1f}%{warn_str}      \033[2mShow {len(p.mcp_tools)} breakdowns\033[0m")
    if p.agents_tokens or p.agents:
        a_pct = (p.agents_tokens / budget) * 100.0
        print(f"  • \033[36mSubagents\033[0m ({p.agents_tokens:,} tokens) {a_pct:.1f}%      \033[2mShow {len(p.agents)} breakdowns\033[0m")
    if p.rules_tokens or p.rules:
        r_pct = (p.rules_tokens / budget) * 100.0
        print(f"  • \033[33mRules\033[0m ({p.rules_tokens:,} tokens) {r_pct:.1f}%      \033[2mShow {len(p.rules)} breakdowns\033[0m")

    # Deep itemized breakdown
    if show_breakdowns and p.breakdowns:
        print(f"\n\033[1;37mItemized Breakdown ({len(p.breakdowns)} components):\033[0m")
        print(f"  {'TYPE':<12} {'NAME':<32} {'TOKENS':<16} {'STATUS':<12} {'DESCRIPTION'}")
        print("  " + "-" * 82)
        for b in p.breakdowns:
            st = "\033[32m● active\033[0m" if b.is_active else "\033[2m○ disabled\033[0m"
            excl = " \033[33m(excl)\033[0m" if b.is_excluded else ""
            tok_str = f"{b.tokens:,}t ({b.tokens/budget*100:.1f}%){excl}"
            print(f"  {b.category:<12} {b.name:<32} {tok_str:<24} {st:<20} {b.description[:36]}")

    status_str = "\033[32m● ENABLED\033[0m" if p.is_active else "\033[2m○ DISABLED\033[0m"
    print(f"\nStatus: {status_str} · Scope: [{p.scope.value.upper()}] · Author: {p.author}")
    print(f"Path:   {p.path}\n")


def print_tokens(registry: CustomizationRegistry) -> None:
    """Print complete Antigravity context budget audit and breakdown."""
    registry.discover_all()
    budget = registry.token_budget
    active_tok = registry.get_total_active_tokens()
    pct = (active_tok / budget) * 100.0

    print(f"\n=======================================================")
    print(f"    Antigravity Context Window & Token Budget Audit    ")
    print(f"=======================================================")
    print(f"Target Budget:      {budget:,} tokens (Hard Cap)")
    print(f"Active Consumption: {active_tok:,} tokens ({pct:.1f}% used)")
    print(f"Remaining Headroom: {max(0, budget - active_tok):,} tokens ({max(0.0, 100.0 - pct):.1f}% free)\n")

    # Segmented Bar
    bar_len = 40
    bd = registry.get_token_breakdown()
    ws_tok = bd["workspace_skills"][1]
    bi_tok = bd["builtin_skills"][1]
    gl_tok = bd["global_skills"][1]
    r_tok = bd["rules"][1]
    sub_tok = bd["subagents"][1]
    p_tok = bd["plugins"][1]

    fill_len = int(round((pct / 100.0) * bar_len))
    empty_len = max(0, bar_len - fill_len)
    bar_str = ("█" * fill_len) + ("░" * empty_len)
    print(f"Context Gauge: [{bar_str}] {active_tok:,} / {budget:,} tokens\n")

    print("Category Breakdown:")
    print(f"  • Workspace Skills : {bd['workspace_skills'][0]:>2} active ({ws_tok:>5,} tok)")
    print(f"  • Built-in Skills  : {bd['builtin_skills'][0]:>2} active ({bi_tok:>5,} tok)")
    print(f"  • Global Skills    : {bd['global_skills'][0]:>2} active ({gl_tok:>5,} tok)")
    print(f"  • Active Rules     : {bd['rules'][0]:>2} active ({r_tok:>5,} tok)")
    print(f"  • Active Subagents : {bd['subagents'][0]:>2} active ({sub_tok:>5,} tok)")
    print(f"  • Active Plugins   : {bd['plugins'][0]:>2} active ({p_tok:>5,} tok)\n")

    # Heaviest components
    all_components = []
    for s in registry.skills:
        if s.is_active and s.scope in (Scope.WORKSPACE, Scope.GLOBAL, Scope.BUILTIN):
            all_components.append((f"[SKILL] {s.name}", s.tokens))
    for r in registry.rules:
        if r.is_active:
            all_components.append((f"[RULE] {r.name}", r.tokens))
    for p in registry.plugins:
        if p.is_active:
            all_components.append((f"[PLUGIN] {p.name}", p.tokens))

    all_components.sort(key=lambda x: x[1], reverse=True)

    print("Top Context Consumers:")
    for name, tok in all_components[:8]:
        item_pct = (tok / budget) * 100.0
        print(f"  {tok:>5,} tok ({item_pct:>4.1f}%)  {name}")

    print("")


def toggle_plugin_component_cli(registry: CustomizationRegistry, plugin_name: str, component_name: str) -> int:
    """CLI toggle for a specific subcomponent within a plugin."""
    registry.discover_all()
    result = registry.toggle_plugin_component(plugin_name, component_name)
    if result is None:
        print(f"Error: Component '{component_name}' not found in plugin '{plugin_name}'.", file=sys.stderr)
        return 1
    state = "ENABLED" if result else "DISABLED"
    plug = next((p for p in registry.plugins if p.name == plugin_name), None)
    new_tokens = plug.tokens if plug else 0
    print(f"✔ Subcomponent '{component_name}' in plugin '{plugin_name}' is now {state}.")
    print(f"   Plugin '{plugin_name}' now consumes {new_tokens:,} tokens.\n")
    return 0


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
