"""Filesystem discovery for Antigravity skills, rules, subagents, and plugins."""

from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .models import (
    MCPServer,
    Plugin,
    Rule,
    Scope,
    Skill,
    Subagent,
    estimate_tokens,
    parse_frontmatter,
)
from .plugin_client import AntigravityPluginClient
from .validator import validate_rule, validate_skill


def find_workspace_root(start_dir: Optional[Path] = None) -> Path:
    """Find the workspace root by walking up from start_dir looking for .git or .agents."""
    curr = (start_dir or Path.cwd()).resolve()

    for p in [curr, *curr.parents]:
        if (p / ".git").exists() or (p / ".agents").exists() or (p / ".agent").exists():
            return p

    return curr


class CustomizationRegistry:
    """Discovers, indexes, and manages skills, rules, subagents, and plugins across scopes."""

    def __init__(self, workspace_root: Optional[Path] = None, home_dir: Optional[Path] = None):
        self.workspace_root = find_workspace_root(workspace_root)
        self.home_dir = home_dir or Path.home()
        self.global_config_dir = self.home_dir / ".gemini" / "config"
        self.builtin_dir = self.home_dir / ".gemini" / "antigravity" / "builtin"
        self.token_budget: int = 20_000

        self.plugin_client = AntigravityPluginClient()

        self.skills: List[Skill] = []
        self.rules: List[Rule] = []
        self.subagents: List[Subagent] = []
        self.plugins: List[Plugin] = []
        self.mcp_servers: List[MCPServer] = []

        # In-memory toggle states (set of identifiers toggled off or on)
        self.active_overrides: Dict[str, bool] = {}

    def discover_all(self) -> Tuple[List[Skill], List[Rule]]:
        """Run full discovery across workspace, global, builtin, and catalog locations."""
        self.skills.clear()
        self.rules.clear()
        self.subagents.clear()
        self.plugins.clear()
        self.mcp_servers.clear()

        # 1. Discover Workspace Skills & Rules
        self._discover_workspace()

        # 2. Discover Built-in Skills & Subagents
        self._discover_builtin()

        # 3. Discover Global Skills & Rules
        self._discover_global()

        # 4. Discover Catalog / Plugin Skills
        self._discover_catalog_and_plugins()

        # 5. Discover Subagents (Builtin, Plugins, Workspace)
        self._discover_subagents()

        # 6. Discover MCP Servers (Antigravity & Plugin MCPs)
        self._discover_mcp_servers()

        # 7. Apply override flags and active state overrides
        self._apply_states_and_overrides()

        # Validate all skills and rules
        for s in self.skills:
            validate_skill(s)
        for r in self.rules:
            validate_rule(r)

        return self.skills, self.rules

    def _discover_workspace(self) -> None:
        """Scan workspace root for .agents/skills, rules, GEMINI.md, AGENTS.md."""
        ws = self.workspace_root
        if not ws.exists():
            return

        for agent_dir_name in [".agents", ".agent", "_agents", "_agent"]:
            agent_dir = ws / agent_dir_name
            if agent_dir.is_dir():
                # Skills
                skills_dir = agent_dir / "skills"
                if skills_dir.is_dir():
                    for item in sorted(skills_dir.iterdir()):
                        if item.is_dir():
                            skill = Skill.from_directory(item, Scope.WORKSPACE)
                            if skill:
                                self.skills.append(skill)

                # Rules
                rules_dir = agent_dir / "rules"
                if rules_dir.is_dir():
                    for item in sorted(rules_dir.glob("*.md")):
                        if item.is_file():
                            rule = Rule.from_file(
                                item, Scope.WORKSPACE, name_override=f"{agent_dir_name}/rules/{item.name}"
                            )
                            if rule:
                                self.rules.append(rule)

        # Root GEMINI.md and AGENTS.md
        for rule_name in ["GEMINI.md", "AGENTS.md"]:
            rule_path = ws / rule_name
            if rule_path.is_file():
                rule = Rule.from_file(rule_path, Scope.WORKSPACE, name_override=rule_name)
                if rule:
                    self.rules.append(rule)

    def _discover_builtin(self) -> None:
        """Scan ~/.gemini/antigravity/builtin/skills/ for built-in skills."""
        b_skills = self.builtin_dir / "skills"
        if b_skills.exists() and b_skills.is_dir():
            for item in sorted(b_skills.iterdir()):
                if item.is_dir():
                    skill = Skill.from_directory(item, Scope.BUILTIN)
                    if skill:
                        self.skills.append(skill)

    def _discover_global(self) -> None:
        """Scan ~/.gemini/config/ for global skills and rules."""
        g = self.global_config_dir
        if not g.exists():
            return

        # Global skills
        skills_dir = g / "skills"
        if skills_dir.is_dir():
            for item in sorted(skills_dir.iterdir()):
                if item.is_dir():
                    skill = Skill.from_directory(item, Scope.GLOBAL)
                    if skill:
                        self.skills.append(skill)

        # Global rules
        for rule_name in ["GEMINI.md", "AGENTS.md"]:
            rule_path = g / rule_name
            if rule_path.is_file():
                rule = Rule.from_file(rule_path, Scope.GLOBAL, name_override=f"global/{rule_name}")
                if rule:
                    self.rules.append(rule)

        rules_dir = g / "rules"
        if rules_dir.is_dir():
            for item in sorted(rules_dir.glob("*.md")):
                if item.is_file():
                    rule = Rule.from_file(item, Scope.GLOBAL, name_override=f"global/rules/{item.name}")
                    if rule:
                        self.rules.append(rule)

    def _discover_catalog_and_plugins(self) -> None:
        """Scan plugins in ~/.gemini/config/plugins/ for catalog skills and plugins."""
        plugins_dir = self.global_config_dir / "plugins"
        if not plugins_dir.exists() or not plugins_dir.is_dir():
            return

        # Query live state from Antigravity Language Server if available
        live_plugins_map = {}
        if self.plugin_client.is_available():
            for lp in self.plugin_client.get_all_plugins():
                live_plugins_map[lp["dir"]] = lp

        existing_names = {s.name for s in self.skills}

        for plug_path in sorted(plugins_dir.iterdir()):
            if not plug_path.is_dir():
                continue

            plug_name = plug_path.name
            plugin_skills: List[str] = []

            # Check skills directory
            s_dir = plug_path / "skills"
            if s_dir.is_dir():
                for item in sorted(s_dir.iterdir()):
                    if item.is_dir() and (item / "SKILL.md").exists():
                        plugin_skills.append(item.name)
                        if item.name not in existing_names:
                            skill = Skill.from_directory(item, Scope.CATALOG)
                            if skill:
                                self.skills.append(skill)
                                existing_names.add(item.name)
                    elif item.name == "SKILL.md":
                        plugin_skills.append(plug_name)
                        if plug_name not in existing_names:
                            skill = Skill.from_directory(plug_path, Scope.CATALOG)
                            if skill:
                                self.skills.append(skill)
                                existing_names.add(plug_name)

            # Determine live status & MCP servers
            live_entry = live_plugins_map.get(plug_name)
            is_active = (not live_entry.get("disabled", False)) if live_entry else True
            mcp_servers = live_entry.get("mcp", []) if live_entry else []

            # Plugin model
            plugin_desc = f"Antigravity plugin providing {len(plugin_skills)} domain capabilities."
            self.plugins.append(
                Plugin(
                    name=plug_name,
                    dir_name=plug_name,
                    path=plug_path,
                    skills_count=len(plugin_skills),
                    skills=plugin_skills,
                    mcp_servers=mcp_servers,
                    description=plugin_desc,
                    is_active=is_active,
                )
            )

    def _discover_subagents(self) -> None:
        """Discover built-in, plugin, and workspace subagents."""
        # 1. Built-in subagents
        self.subagents.append(
            Subagent(
                name="self",
                role="Full Assistant Mirror",
                description="Subagent that inherits parent configuration, tools, and model. Operates in isolated context.",
                tier="BUILT-IN",
                scope=Scope.BUILTIN,
                model="inherit",
                tokens=48,
                tools=["read", "write", "run_command", "mcp"],
            )
        )
        self.subagents.append(
            Subagent(
                name="research",
                role="Codebase & Documentation Researcher",
                description="Read-only specialist subagent for surveying codebase files, searching web, and analyzing APIs.",
                tier="BUILT-IN",
                scope=Scope.BUILTIN,
                model="inherit",
                tokens=64,
                tools=["read", "search_web", "gemini_docs"],
            )
        )

        # 2. Plugin subagents
        plugins_dir = self.global_config_dir / "plugins"
        if plugins_dir.is_dir():
            for plug in sorted(plugins_dir.iterdir()):
                if not plug.is_dir():
                    continue
                agents_dir = plug / "agents"
                if agents_dir.is_dir():
                    for ag_file in sorted(agents_dir.glob("*.md")):
                        name = ag_file.stem
                        content = ag_file.read_text(encoding="utf-8", errors="replace")
                        fm, body = parse_frontmatter(content)
                        role = fm.get("role", f"{name.replace('-', ' ').title()} Specialist")
                        desc = fm.get("description", body[:120].replace("\n", " ").strip() + "...")
                        self.subagents.append(
                            Subagent(
                                name=name,
                                role=role,
                                description=desc,
                                tier="PLUGIN",
                                scope=Scope.GLOBAL,
                                model="inherit",
                                system_prompt=body,
                                tokens=estimate_tokens(f"- {name}: {desc}"),
                                path=ag_file,
                            )
                        )

        # 3. Workspace subagents
        ws = self.workspace_root
        for agent_dir_name in [".agents", ".agent"]:
            ag_dir = ws / agent_dir_name / "subagents"
            if ag_dir.is_dir():
                for item in sorted(ag_dir.glob("*.md")):
                    name = item.stem
                    content = item.read_text(encoding="utf-8", errors="replace")
                    fm, body = parse_frontmatter(content)
                    role = fm.get("role", "Workspace Specialist")
                    desc = fm.get("description", "Workspace-specific subagent.")
                    self.subagents.append(
                        Subagent(
                            name=name,
                            role=role,
                            description=desc,
                            tier="WORKSPACE",
                            scope=Scope.WORKSPACE,
                            model="inherit",
                            system_prompt=body,
                            tokens=estimate_tokens(f"- {name}: {desc}"),
                            path=item,
                        )
                    )

    def _discover_mcp_servers(self) -> None:
        """Discover Antigravity root and plugin MCP servers."""
        mcp_dir = self.home_dir / ".gemini" / "antigravity" / "mcp"
        if not mcp_dir.is_dir():
            return

        user_servers = []
        plugin_servers = []

        for server_dir in sorted(mcp_dir.iterdir()):
            if not server_dir.is_dir():
                continue

            name = server_dir.name
            tools = [
                f.stem
                for f in sorted(server_dir.iterdir())
                if f.suffix == ".json" and f.name != "instructions.md"
            ]

            instructions = ""
            inst_file = server_dir / "instructions.md"
            if inst_file.is_file():
                try:
                    instructions = inst_file.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    pass

            desc = f"{len(tools)} tools enabled"
            srv = MCPServer(
                name=name,
                tools_count=len(tools),
                tools=tools,
                is_active=True,
                path=server_dir,
                description=desc,
                instructions=instructions,
            )

            # Prioritize root user servers like StitchMCP and canva
            if "_" in name or name.startswith("data-agent-kit"):
                plugin_servers.append(srv)
            else:
                user_servers.append(srv)

        self.mcp_servers = user_servers + plugin_servers

    def _apply_states_and_overrides(self) -> None:
        """Mark overrides and apply user toggle states."""
        # Find which skill names exist in multiple scopes (e.g. workspace overrides global/builtin)
        ws_skill_names = {s.name for s in self.skills if s.scope == Scope.WORKSPACE}

        for s in self.skills:
            if s.scope == Scope.WORKSPACE:
                # Check if it overrides a builtin or global
                has_shadow = any(
                    other.name == s.name and other.scope != Scope.WORKSPACE
                    for other in self.skills
                )
                if has_shadow or getattr(s, "is_overridden", False):
                    s.is_overridden = True

            # Apply state override if set
            key = f"skill:{s.scope.value}:{s.name}"
            if key in self.active_overrides:
                s.is_active = self.active_overrides[key]

        for r in self.rules:
            key = f"rule:{r.scope.value}:{r.name}"
            if key in self.active_overrides:
                r.is_active = self.active_overrides[key]

        for sub in self.subagents:
            key = f"subagent:{sub.scope.value}:{sub.name}"
            if key in self.active_overrides:
                sub.is_active = self.active_overrides[key]

        for p in self.plugins:
            key = f"plugin:{p.name}"
            if key in self.active_overrides:
                p.is_active = self.active_overrides[key]

        for m in self.mcp_servers:
            key = f"mcp:{m.name}"
            if key in self.active_overrides:
                m.is_active = self.active_overrides[key]

    def toggle_item(self, item, target_scope: Scope = Scope.WORKSPACE) -> bool:
        """Toggle active state of an item."""
        if isinstance(item, Skill):
            # If in catalog and toggled on with WORKSPACE target:
            if item.scope == Scope.CATALOG and not item.is_active:
                item.is_active = True
                key = f"skill:{item.scope.value}:{item.name}"
                self.active_overrides[key] = True
                return True
            else:
                item.is_active = not item.is_active
                key = f"skill:{item.scope.value}:{item.name}"
                self.active_overrides[key] = item.is_active
                return item.is_active
        elif isinstance(item, Rule):
            item.is_active = not item.is_active
            key = f"rule:{item.scope.value}:{item.name}"
            self.active_overrides[key] = item.is_active
            return item.is_active
        elif isinstance(item, Subagent):
            item.is_active = not item.is_active
            key = f"subagent:{item.scope.value}:{item.name}"
            self.active_overrides[key] = item.is_active
            return item.is_active
        elif isinstance(item, Plugin):
            item.is_active = not item.is_active
            target_key = item.dir_name or item.name
            key = f"plugin:{target_key}"
            self.active_overrides[key] = item.is_active
            if self.plugin_client.is_available():
                self.plugin_client.set_plugin_enabled(target_key, item.is_active)
            return item.is_active
        elif isinstance(item, MCPServer):
            item.is_active = not item.is_active
            key = f"mcp:{item.name}"
            self.active_overrides[key] = item.is_active
            return item.is_active
        elif hasattr(item, "repo") and hasattr(item, "is_installed"):
            # CatalogSkillPack handling
            from .catalog import install_catalog_pack
            if not getattr(item, "is_installed", False):
                target_dir = (
                    self.workspace_root / ".agents" / "skills"
                    if target_scope == Scope.WORKSPACE
                    else self.global_config_dir / "skills"
                )
                success, _ = install_catalog_pack(item.name, target_dir, target_scope.value)
                self.discover_all()
                return success
            else:
                item.is_active = not getattr(item, "is_active", True)
                return item.is_active
        return False

    def activate_all(self, items: list) -> None:
        """Activate all items in the given collection."""
        for item in items:
            if not item.is_active:
                self.toggle_item(item)

    def deactivate_all(self, items: list) -> None:
        """Deactivate all items in the given collection."""
        for item in items:
            if item.is_active:
                self.toggle_item(item)

    def get_total_active_tokens(self) -> int:
        """Calculate total tokens currently contributing to active context."""
        total = 0
        for s in self.skills:
            if s.is_active:
                total += s.tokens
        for r in self.rules:
            if r.is_active:
                total += r.tokens
        return total

    def get_token_breakdown(self) -> Dict[str, Tuple[int, int]]:
        """Return (active_count, total_tokens) per customization category."""
        return {
            "workspace_skills": (
                sum(1 for s in self.skills if s.scope == Scope.WORKSPACE and s.is_active),
                sum(s.tokens for s in self.skills if s.scope == Scope.WORKSPACE and s.is_active),
            ),
            "builtin_skills": (
                sum(1 for s in self.skills if s.scope == Scope.BUILTIN and s.is_active),
                sum(s.tokens for s in self.skills if s.scope == Scope.BUILTIN and s.is_active),
            ),
            "global_skills": (
                sum(1 for s in self.skills if s.scope == Scope.GLOBAL and s.is_active),
                sum(s.tokens for s in self.skills if s.scope == Scope.GLOBAL and s.is_active),
            ),
            "catalog_skills": (
                sum(1 for s in self.skills if s.scope == Scope.CATALOG and s.is_active),
                sum(s.tokens for s in self.skills if s.scope == Scope.CATALOG and s.is_active),
            ),
            "rules": (
                sum(1 for r in self.rules if r.is_active),
                sum(r.tokens for r in self.rules if r.is_active),
            ),
            "subagents": (
                sum(1 for sub in self.subagents if sub.is_active),
                sum(sub.tokens for sub in self.subagents if sub.is_active),
            ),
            "plugins": (
                sum(1 for p in self.plugins if p.is_active),
                sum(p.skills_count for p in self.plugins if p.is_active),
            ),
            "mcp_servers": (
                sum(1 for m in self.mcp_servers if m.is_active),
                sum(m.tools_count for m in self.mcp_servers if m.is_active),
            ),
        }
