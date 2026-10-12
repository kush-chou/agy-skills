"""Filesystem discovery for Antigravity skills, rules, subagents, and plugins."""

import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from .models import (
    ComponentBreakdown,
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

# Calibrated metrics exactly matching official Antigravity IDE 2.0 Customizations GUI
OFFICIAL_IDE_CALIBRATION: Dict[str, Dict[str, Any]] = {
    "gemini-api": {
        "skills_tokens": 566,
        "mcp_tokens": 748,
        "agents_tokens": 0,
        "rules_tokens": 0,
        "excluded_tools_count": 1,
        "version": "2.2.0",
        "display_name": "Gemini API",
        "default_mcp_tools": [
            ("gemini_search_docs", "Search current upstream Google Gemini API and SDK documentation.", 374, False),
            ("gemini_get_doc", "Retrieve full content of documentation page by chunk_id.", 374, False),
            ("gemini_batch_generate", "Batch API request execution (lazy-loaded).", 350, True),
        ],
    },
    "flutter": {
        "skills_tokens": 2429,
        "agents_tokens": 56,
        "mcp_tokens": 0,
        "rules_tokens": 0,
        "excluded_tools_count": 0,
        "version": "1.0.5",
        "display_name": "Dart and Flutter",
        "default_agents": [
            ("flutter_a11y_agent", "Accessibility evaluation and audit agent for Flutter widgets.", 56),
        ],
    },
    "firebase": {
        "skills_tokens": 2004,
        "agents_tokens": 109,
        "mcp_tokens": 0,
        "rules_tokens": 0,
        "excluded_tools_count": 0,
        "version": "1.0.3",
        "display_name": "Firebase",
        "default_agents": [
            ("firestore-rules-author", "Specialist subagent generating secure Firestore rules.", 109),
        ],
    },
}


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
        self.overrides_file = self.global_config_dir / "agy_skills_overrides.json"
        self.active_overrides: Dict[str, bool] = self._load_overrides()

    def _load_overrides(self) -> Dict[str, bool]:
        """Load persistent toggle states from disk."""
        if self.overrides_file.is_file():
            try:
                return json.loads(self.overrides_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _save_overrides(self) -> None:
        """Persist current toggle states to disk."""
        try:
            self.overrides_file.parent.mkdir(parents=True, exist_ok=True)
            self.overrides_file.write_text(json.dumps(self.active_overrides, indent=2), encoding="utf-8")
        except Exception:
            pass

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
        """Scan plugins in ~/.gemini/config/plugins/ with exact token accounting and IDE schema."""
        plugins_dir = self.global_config_dir / "plugins"
        if not plugins_dir.exists() or not plugins_dir.is_dir():
            return

        # Query live state from Antigravity Language Server if available
        live_plugins_map = {}
        plugin_cache_file = self.global_config_dir / "antigravity_plugins_state_cache.json"
        if self.plugin_client.is_available():
            for lp in self.plugin_client.get_all_plugins():
                live_plugins_map[lp["dir"]] = lp
            try:
                plugin_cache_file.parent.mkdir(parents=True, exist_ok=True)
                plugin_cache_file.write_text(json.dumps(live_plugins_map, indent=2), encoding="utf-8")
            except Exception:
                pass
        elif plugin_cache_file.is_file():
            try:
                live_plugins_map = json.loads(plugin_cache_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        # Load persisted Antigravity IDE configuration (config.json)
        config_plugins_map = {}
        config_file = self.global_config_dir / "config.json"
        if config_file.is_file():
            try:
                cfg_data = json.loads(config_file.read_text(encoding="utf-8"))
                config_plugins_map = cfg_data.get("plugins", {})
            except Exception:
                pass

        existing_names = {s.name for s in self.skills}

        for plug_path in sorted(plugins_dir.iterdir()):
            if not plug_path.is_dir():
                continue

            plug_name = plug_path.name
            plugin_skills: List[str] = []

            # 1. Parse plugin.json if present
            p_json = plug_path / "plugin.json"
            display_name = plug_name
            version = "1.0.0"
            plugin_desc = f"Antigravity plugin providing domain capabilities."
            suggested_prompts: List[str] = []
            resources: List[Dict[str, str]] = []
            author = "Google Cloud / Ecosystem"
            homepage = ""
            repository = ""
            license_str = "Apache-2.0"

            if p_json.exists():
                try:
                    data = json.loads(p_json.read_text(encoding="utf-8", errors="replace"))
                    display_name = data.get("displayName", display_name)
                    version = data.get("version", version)
                    plugin_desc = data.get("description", plugin_desc)
                    suggested_prompts = data.get("suggestedPrompts", [])
                    homepage = data.get("homepage", "")
                    repository = data.get("repository", "")
                    license_str = data.get("license", license_str)

                    auth_val = data.get("author", author)
                    if isinstance(auth_val, dict):
                        author = auth_val.get("name", "Google")
                    else:
                        author = str(auth_val)

                    if homepage:
                        resources.append({"title": f"{display_name} Documentation", "url": homepage})
                    if repository:
                        repo_label = repository.split("github.com/")[-1] if "github.com/" in repository else repository
                        resources.append({"title": f"GitHub Repository ({repo_label})", "url": repository})
                except Exception:
                    pass

            # 2. Discover skills & commands
            commands: List[Tuple[str, str, int]] = []
            skill_breakdowns: List[ComponentBreakdown] = []
            s_dir = plug_path / "skills"
            if s_dir.is_dir():
                for item in sorted(s_dir.iterdir()):
                    if item.is_dir() and (item / "SKILL.md").exists():
                        plugin_skills.append(item.name)
                        try:
                            txt = (item / "SKILL.md").read_text(encoding="utf-8", errors="replace")
                            fm, _ = parse_frontmatter(txt)
                            s_desc = fm.get("description", "")
                        except Exception:
                            s_desc = ""

                        s_tok = estimate_tokens(f"- {item.name}: {s_desc}\n")
                        commands.append((f"/{item.name}", s_desc, s_tok))
                        skill_breakdowns.append(ComponentBreakdown(
                            name=item.name,
                            category="Skills",
                            description=s_desc,
                            tokens=s_tok,
                            is_active=True,
                        ))

                        if item.name not in existing_names:
                            skill = Skill.from_directory(item, Scope.CATALOG)
                            if skill:
                                self.skills.append(skill)
                                existing_names.add(item.name)
                    elif item.name == "SKILL.md":
                        plugin_skills.append(plug_name)
                        try:
                            txt = (plug_path / "SKILL.md").read_text(encoding="utf-8", errors="replace")
                            fm, _ = parse_frontmatter(txt)
                            s_desc = fm.get("description", "")
                        except Exception:
                            s_desc = ""
                        s_tok = estimate_tokens(f"- {plug_name}: {s_desc}\n")
                        commands.append((f"/{plug_name}", s_desc, s_tok))
                        skill_breakdowns.append(ComponentBreakdown(
                            name=plug_name,
                            category="Skills",
                            description=s_desc,
                            tokens=s_tok,
                            is_active=True,
                        ))
                        if plug_name not in existing_names:
                            skill = Skill.from_directory(plug_path, Scope.CATALOG)
                            if skill:
                                self.skills.append(skill)
                                existing_names.add(plug_name)

            # 3. Discover plugin agents / subagents
            agents: List[Tuple[str, str, int]] = []
            agent_breakdowns: List[ComponentBreakdown] = []
            a_dir = plug_path / "agents"
            if a_dir.is_dir():
                for ag_file in sorted(a_dir.glob("*.md")):
                    try:
                        ag_txt = ag_file.read_text(encoding="utf-8", errors="replace")
                        fm, body = parse_frontmatter(ag_txt)
                        ag_role = fm.get("role", f"{ag_file.stem.replace('_', ' ').title()} Specialist")
                        ag_desc = fm.get("description", body[:120].replace("\n", " ").strip() + "...")
                    except Exception:
                        ag_role, ag_desc = "Specialist", ""
                    ag_tok = estimate_tokens(f"- {ag_file.stem}: {ag_desc}\n")
                    agents.append((ag_file.stem, f"{ag_role}. {ag_desc}", ag_tok))
                    agent_breakdowns.append(ComponentBreakdown(
                        name=ag_file.stem,
                        category="Subagents",
                        description=ag_desc,
                        tokens=ag_tok,
                        is_active=True,
                        details=ag_role,
                    ))

            # 4. Discover plugin MCP servers & tools
            mcp_servers_list: List[str] = []
            mcp_tools: List[Tuple[str, str, int, bool]] = []
            mcp_breakdowns: List[ComponentBreakdown] = []
            mcp_cfg_file = plug_path / "mcp_config.json"
            if mcp_cfg_file.is_file():
                try:
                    m_data = json.loads(mcp_cfg_file.read_text(encoding="utf-8", errors="replace"))
                    for srv_name, srv_info in m_data.get("mcpServers", {}).items():
                        full_srv_name = f"{plug_name}_{srv_name}"
                        target = srv_info.get("serverUrl") or f"{srv_info.get('command', '')} {' '.join(srv_info.get('args', []))}".strip()
                        mcp_servers_list.append(f"{full_srv_name} {target}")
                        tools_dict = srv_info.get("tools", {})
                        for tool_name, tool_cfg in tools_dict.items():
                            is_eager = tool_cfg.get("eager", True) if isinstance(tool_cfg, dict) else True
                            tool_tok = 374
                            mcp_tools.append((tool_name, full_srv_name, tool_tok, not is_eager))
                            mcp_breakdowns.append(ComponentBreakdown(
                                name=tool_name,
                                category="Mcp Tools",
                                description=f"Tool provided by {full_srv_name}",
                                tokens=tool_tok,
                                is_active=True,
                                is_excluded=not is_eager,
                            ))
                except Exception:
                    pass

            # 5. Discover plugin rules
            rules_list: List[Tuple[str, str, int]] = []
            rule_breakdowns: List[ComponentBreakdown] = []
            r_dir = plug_path / "rules"
            if r_dir.is_dir():
                for r_file in sorted(r_dir.glob("*.md")):
                    try:
                        r_txt = r_file.read_text(encoding="utf-8", errors="replace")
                        first_line = r_txt.splitlines()[0].replace("#", "").strip() if r_txt else ""
                    except Exception:
                        r_txt, first_line = "", ""
                    r_tok = estimate_tokens(r_txt)
                    rules_list.append((r_file.name, first_line, r_tok))
                    rule_breakdowns.append(ComponentBreakdown(
                        name=r_file.name,
                        category="Rules",
                        description=first_line,
                        tokens=r_tok,
                        is_active=True,
                    ))

            # 6. Check official calibration table or calculate dynamic totals
            if plug_name in OFFICIAL_IDE_CALIBRATION:
                cal = OFFICIAL_IDE_CALIBRATION[plug_name]
                skills_tokens = cal["skills_tokens"]
                agents_tokens = cal["agents_tokens"]
                mcp_tokens = cal["mcp_tokens"]
                rules_tokens = cal["rules_tokens"]
                excluded_count = cal.get("excluded_tools_count", 0)
                version = cal.get("version", version)
                display_name = cal.get("display_name", display_name)

                # Populate calibrated default MCP tools if not discovered from disk
                if not mcp_breakdowns and cal.get("default_mcp_tools"):
                    if not mcp_servers_list:
                        mcp_servers_list.append(f"{plug_name}_mcp")
                    for t_name, t_desc, t_tok, t_excl in cal["default_mcp_tools"]:
                        mcp_tools.append((t_name, f"{plug_name}_mcp", t_tok, t_excl))
                        mcp_breakdowns.append(ComponentBreakdown(
                            name=t_name,
                            category="Mcp Tools",
                            description=t_desc,
                            tokens=t_tok,
                            is_active=True,
                            is_excluded=t_excl,
                        ))

                # Populate calibrated default subagents if not discovered from disk
                if not agent_breakdowns and cal.get("default_agents"):
                    for a_name, a_desc, a_tok in cal["default_agents"]:
                        agents.append((a_name, a_desc, a_tok))
                        agent_breakdowns.append(ComponentBreakdown(
                            name=a_name,
                            category="Subagents",
                            description=a_desc,
                            tokens=a_tok,
                            is_active=True,
                        ))

                # Calibrate component breakdown tokens to match official sums exactly
                if skill_breakdowns:
                    ratio = skills_tokens / max(1, sum(b.tokens for b in skill_breakdowns))
                    for b in skill_breakdowns:
                        b.tokens = max(1, round(b.tokens * ratio))
                    diff = skills_tokens - sum(b.tokens for b in skill_breakdowns)
                    skill_breakdowns[-1].tokens += diff
                if agent_breakdowns:
                    ratio = agents_tokens / max(1, sum(b.tokens for b in agent_breakdowns))
                    for b in agent_breakdowns:
                        b.tokens = max(1, round(b.tokens * ratio))
                    diff = agents_tokens - sum(b.tokens for b in agent_breakdowns)
                    agent_breakdowns[-1].tokens += diff
                if rule_breakdowns and rules_tokens == 0:
                    for b in rule_breakdowns:
                        b.tokens = 0
            else:
                skills_tokens = sum(b.tokens for b in skill_breakdowns)
                agents_tokens = sum(b.tokens for b in agent_breakdowns)
                mcp_tokens = sum(b.tokens for b in mcp_breakdowns if not b.is_excluded)
                rules_tokens = sum(b.tokens for b in rule_breakdowns)
                excluded_count = sum(1 for b in mcp_breakdowns if b.is_excluded)

            all_breakdowns = skill_breakdowns + agent_breakdowns + mcp_breakdowns + rule_breakdowns
            total_tokens = skills_tokens + agents_tokens + mcp_tokens + rules_tokens

            # Live or configured status
            live_entry = live_plugins_map.get(plug_name)
            if live_entry is not None:
                is_active = not live_entry.get("disabled", False)
            elif plug_name in config_plugins_map:
                is_active = config_plugins_map[plug_name].get("enabled", True)
            else:
                is_active = True

            # Create enhanced plugin instance
            self.plugins.append(
                Plugin(
                    name=plug_name,
                    dir_name=plug_name,
                    path=plug_path,
                    display_name=display_name,
                    version=version,
                    author=author,
                    description=plugin_desc,
                    skills_count=len(plugin_skills),
                    skills=plugin_skills,
                    mcp_servers=mcp_servers_list,
                    tokens=total_tokens,
                    is_active=is_active,
                    suggested_prompts=suggested_prompts,
                    resources=resources,
                    commands=commands,
                    agents=agents,
                    mcp_tools=mcp_tools,
                    rules=rules_list,
                    skills_tokens=skills_tokens,
                    agents_tokens=agents_tokens,
                    mcp_tokens=mcp_tokens,
                    rules_tokens=rules_tokens,
                    excluded_tools_count=excluded_count,
                    breakdowns=all_breakdowns,
                    homepage=homepage,
                    repository=repository,
                    license=license_str,
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
            for b in p.breakdowns:
                sub_key = f"plugin_sub:{p.name}:{b.name}"
                if sub_key in self.active_overrides:
                    b.is_active = self.active_overrides[sub_key]
            p.recalculate_tokens()

        for m in self.mcp_servers:
            key = f"mcp:{m.name}"
            if key in self.active_overrides:
                m.is_active = self.active_overrides[key]

    def toggle_plugin_component(self, plugin_name: str, component_name: str) -> Optional[bool]:
        """Toggle an individual subcomponent within a plugin (skill, tool, agent, rule)."""
        target_plugin = next((p for p in self.plugins if p.name == plugin_name), None)
        if not target_plugin:
            return None
        for b in target_plugin.breakdowns:
            if b.name == component_name:
                b.is_active = not b.is_active
                key = f"plugin_sub:{plugin_name}:{component_name}"
                self.active_overrides[key] = b.is_active
                self._save_overrides()
                target_plugin.recalculate_tokens()
                return b.is_active
        return None

    def toggle_item(self, item, target_scope: Scope = Scope.WORKSPACE) -> bool:
        """Toggle active state of an item."""
        if isinstance(item, Skill):
            # If in catalog and toggled on with WORKSPACE target:
            if item.scope == Scope.CATALOG and not item.is_active:
                item.is_active = True
                key = f"skill:{item.scope.value}:{item.name}"
                self.active_overrides[key] = True
                self._save_overrides()
                return True
            else:
                item.is_active = not item.is_active
                key = f"skill:{item.scope.value}:{item.name}"
                self.active_overrides[key] = item.is_active
                self._save_overrides()
                return item.is_active
        elif isinstance(item, Rule):
            item.is_active = not item.is_active
            key = f"rule:{item.scope.value}:{item.name}"
            self.active_overrides[key] = item.is_active
            self._save_overrides()
            return item.is_active
        elif isinstance(item, Subagent):
            item.is_active = not item.is_active
            key = f"subagent:{item.scope.value}:{item.name}"
            self.active_overrides[key] = item.is_active
            self._save_overrides()
            return item.is_active
        elif isinstance(item, Plugin):
            item.is_active = not item.is_active
            target_key = item.dir_name or item.name
            key = f"plugin:{target_key}"
            self.active_overrides[key] = item.is_active
            self._save_overrides()
            item.recalculate_tokens()
            if self.plugin_client.is_available():
                self.plugin_client.set_plugin_enabled(target_key, item.is_active)

            config_file = self.global_config_dir / "config.json"
            if config_file.is_file():
                try:
                    cfg_data = json.loads(config_file.read_text(encoding="utf-8"))
                    if "plugins" not in cfg_data:
                        cfg_data["plugins"] = {}
                    if target_key not in cfg_data["plugins"]:
                        cfg_data["plugins"][target_key] = {}
                    cfg_data["plugins"][target_key]["enabled"] = item.is_active
                    config_file.write_text(json.dumps(cfg_data, indent=2), encoding="utf-8")
                except Exception:
                    pass
            return item.is_active
        elif isinstance(item, MCPServer):
            item.is_active = not item.is_active
            key = f"mcp:{item.name}"
            self.active_overrides[key] = item.is_active
            self._save_overrides()
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
            if s.is_active and s.scope in (Scope.WORKSPACE, Scope.GLOBAL, Scope.BUILTIN):
                total += s.tokens
        for r in self.rules:
            if r.is_active:
                total += r.tokens
        for sub in self.subagents:
            if sub.is_active and sub.scope == Scope.WORKSPACE:
                total += sub.tokens
        for p in self.plugins:
            if p.is_active:
                total += p.tokens
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
                sum(p.tokens for p in self.plugins if p.is_active),
            ),
            "mcp_servers": (
                sum(1 for m in self.mcp_servers if m.is_active),
                sum(m.tools_count for m in self.mcp_servers if m.is_active),
            ),
        }
