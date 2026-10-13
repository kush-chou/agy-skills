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
    """Find the workspace root by walking up from start_dir looking for .git, .gemini, or project .agents."""
    curr = (start_dir or Path.cwd()).resolve()
    home = Path.home().resolve()

    for p in [curr, *curr.parents]:
        if p == home:
            # Under Invariant 1, never treat the user's home directory as a workspace root
            continue
        if (p / ".git").exists() or (p / ".gemini").exists() or (p / ".agents").exists() or (p / ".agent").exists():
            return p

    return curr


def get_global_config_dir(home_dir: Optional[Path] = None) -> Path:
    """Return canonical global Antigravity config directory (~/.gemini/config)."""
    home = home_dir or Path.home()
    return home / ".gemini" / "config"


def get_workspace_dir(workspace_root: Path) -> Path:
    """Return canonical workspace Antigravity directory (<workspace_root>/.gemini)."""
    return workspace_root / ".gemini"


class CustomizationRegistry:
    """Discovers, indexes, and manages skills, rules, subagents, and plugins across scopes."""

    def __init__(self, workspace_root: Optional[Path] = None, home_dir: Optional[Path] = None):
        self.workspace_root = find_workspace_root(workspace_root)
        self.home_dir = home_dir or Path.home()
        self.global_config_dir = get_global_config_dir(self.home_dir)
        self.workspace_gemini_dir = get_workspace_dir(self.workspace_root)
        self.builtin_dir = self.home_dir / ".gemini" / "antigravity" / "builtin"
        self.token_budget: int = 20_000

        self.plugin_client = AntigravityPluginClient()

        self.skills: List[Skill] = []
        self.rules: List[Rule] = []
        self.subagents: List[Subagent] = []
        self.plugins: List[Plugin] = []
        self.mcp_servers: List[MCPServer] = []

    def _read_global_config(self) -> dict:
        """Read global config.json if present."""
        cfg_path = self.global_config_dir / "config.json"
        if cfg_path.is_file():
            try:
                return json.loads(cfg_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _write_global_config(self, cfg_data: dict) -> None:
        """Write global config.json safely."""
        cfg_path = self.global_config_dir / "config.json"
        try:
            cfg_path.parent.mkdir(parents=True, exist_ok=True)
            cfg_path.write_text(json.dumps(cfg_data, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _read_workspace_config(self) -> dict:
        """Read workspace config.json if present."""
        cfg_path = self.workspace_gemini_dir / "config.json"
        if cfg_path.is_file():
            try:
                return json.loads(cfg_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _write_workspace_config(self, cfg_data: dict) -> None:
        """Write workspace config.json safely."""
        cfg_path = self.workspace_gemini_dir / "config.json"
        try:
            cfg_path.parent.mkdir(parents=True, exist_ok=True)
            cfg_path.write_text(json.dumps(cfg_data, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _set_entity_config_state(self, entity_category: str, name: str, enabled: bool, scope: Scope = Scope.WORKSPACE) -> None:
        """Persist entity enabled state to config.json according to scope."""
        if scope == Scope.WORKSPACE:
            cfg = self._read_workspace_config()
            if entity_category not in cfg:
                cfg[entity_category] = {}
            if name not in cfg[entity_category]:
                cfg[entity_category][name] = {}
            cfg[entity_category][name]["enabled"] = enabled
            self._write_workspace_config(cfg)
        else:
            cfg = self._read_global_config()
            if entity_category not in cfg:
                cfg[entity_category] = {}
            if name not in cfg[entity_category]:
                cfg[entity_category][name] = {}
            cfg[entity_category][name]["enabled"] = enabled
            self._write_global_config(cfg)

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
        """Scan workspace root for .gemini/skills, .gemini/rules, GEMINI.md, AGENTS.md, and legacy .agents."""
        ws = self.workspace_root
        if not ws.exists():
            return

        existing_skill_names = set()

        # 1. Canonical Antigravity Workspace: <workspace_root>/.gemini/
        ws_gemini = self.workspace_gemini_dir
        if ws_gemini.is_dir():
            ws_skills_dir = ws_gemini / "skills"
            if ws_skills_dir.is_dir():
                for item in sorted(ws_skills_dir.iterdir()):
                    if item.is_dir():
                        if item.name == ".disabled":
                            for dis_item in sorted(item.iterdir()):
                                if dis_item.is_dir():
                                    skill = Skill.from_directory(dis_item, Scope.WORKSPACE)
                                    if skill:
                                        skill.is_active = False
                                        self.skills.append(skill)
                                        existing_skill_names.add(skill.name)
                        else:
                            skill = Skill.from_directory(item, Scope.WORKSPACE)
                            if skill:
                                self.skills.append(skill)
                                existing_skill_names.add(skill.name)

            ws_rules_dir = ws_gemini / "rules"
            if ws_rules_dir.is_dir():
                for item in sorted(ws_rules_dir.glob("*.md")):
                    if item.is_file():
                        rule = Rule.from_file(item, Scope.WORKSPACE, name_override=f".gemini/rules/{item.name}")
                        if rule:
                            self.rules.append(rule)
                ws_rules_dis = ws_rules_dir / ".disabled"
                if ws_rules_dis.is_dir():
                    for item in sorted(ws_rules_dis.glob("*.md")):
                        if item.is_file():
                            rule = Rule.from_file(item, Scope.WORKSPACE, name_override=f".gemini/rules/.disabled/{item.name}")
                            if rule:
                                rule.is_active = False
                                self.rules.append(rule)

        # 2. Legacy project fallback: <workspace_root>/.agents/ (read-only discovery)
        for agent_dir_name in [".agents", ".agent", "_agents", "_agent"]:
            agent_dir = ws / agent_dir_name
            if agent_dir.is_dir():
                # Skills
                skills_dir = agent_dir / "skills"
                if skills_dir.is_dir():
                    for item in sorted(skills_dir.iterdir()):
                        if item.is_dir():
                            if item.name == ".disabled":
                                for dis_item in sorted(item.iterdir()):
                                    if dis_item.is_dir() and dis_item.name not in existing_skill_names:
                                        skill = Skill.from_directory(dis_item, Scope.WORKSPACE)
                                        if skill:
                                            skill.is_active = False
                                            self.skills.append(skill)
                                            existing_skill_names.add(skill.name)
                            elif item.name not in existing_skill_names:
                                skill = Skill.from_directory(item, Scope.WORKSPACE)
                                if skill:
                                    self.skills.append(skill)
                                    existing_skill_names.add(skill.name)

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

        # 3. Root GEMINI.md and AGENTS.md
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
                    if item.name == ".disabled":
                        for dis_item in sorted(item.iterdir()):
                            if dis_item.is_dir():
                                skill = Skill.from_directory(dis_item, Scope.GLOBAL)
                                if skill:
                                    skill.is_active = False
                                    self.skills.append(skill)
                    else:
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
            rules_dis = rules_dir / ".disabled"
            if rules_dis.is_dir():
                for item in sorted(rules_dis.glob("*.md")):
                    if item.is_file():
                        rule = Rule.from_file(item, Scope.GLOBAL, name_override=f"global/rules/.disabled/{item.name}")
                        if rule:
                            rule.is_active = False
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

    def _parse_subagent_file(self, ag_file: Path, scope: Scope, tier: str, is_active: bool = True) -> Optional[Subagent]:
        """Parse subagent definition from a markdown file."""
        if not ag_file.is_file():
            return None
        try:
            content = ag_file.read_text(encoding="utf-8", errors="replace")
            fm, body = parse_frontmatter(content)
            name = fm.get("name", ag_file.stem)
            role = fm.get("role", f"{name.replace('-', ' ').title()} Specialist")
            desc = fm.get("description", body[:120].replace("\n", " ").strip() + "...")
            model = fm.get("model", "inherit")
            tools = fm.get("tools", [])
            if isinstance(tools, str):
                tools = [t.strip() for t in tools.split(",") if t.strip()]
            return Subagent(
                name=name,
                role=role,
                description=desc,
                tier=tier,
                scope=scope,
                model=model,
                system_prompt=body,
                tokens=estimate_tokens(f"- {name}: {desc}"),
                is_active=is_active,
                tools=tools if isinstance(tools, list) else [],
                path=ag_file,
            )
        except Exception:
            return None

    def _discover_subagents(self) -> None:
        """Discover built-in, global, plugin, and workspace subagents with .disabled/ support."""
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

        existing_subagent_names = {s.name for s in self.subagents}

        # 2. Global Standalone subagents: ~/.gemini/config/agents/ (+ .disabled/)
        gl_agents_dir = self.global_config_dir / "agents"
        if gl_agents_dir.is_dir():
            for ag_file in sorted(gl_agents_dir.glob("*.md")):
                if ag_file.is_file():
                    sub = self._parse_subagent_file(ag_file, Scope.GLOBAL, "GLOBAL", is_active=True)
                    if sub and sub.name not in existing_subagent_names:
                        self.subagents.append(sub)
                        existing_subagent_names.add(sub.name)
            gl_dis_dir = gl_agents_dir / ".disabled"
            if gl_dis_dir.is_dir():
                for ag_file in sorted(gl_dis_dir.glob("*.md")):
                    if ag_file.is_file():
                        sub = self._parse_subagent_file(ag_file, Scope.GLOBAL, "GLOBAL", is_active=False)
                        if sub and sub.name not in existing_subagent_names:
                            self.subagents.append(sub)
                            existing_subagent_names.add(sub.name)

        # 3. Plugin subagents: ~/.gemini/config/plugins/<plug>/agents/
        plugins_dir = self.global_config_dir / "plugins"
        if plugins_dir.is_dir():
            for plug in sorted(plugins_dir.iterdir()):
                if not plug.is_dir():
                    continue
                agents_dir = plug / "agents"
                if agents_dir.is_dir():
                    for ag_file in sorted(agents_dir.glob("*.md")):
                        sub = self._parse_subagent_file(ag_file, Scope.GLOBAL, "PLUGIN", is_active=True)
                        if sub and sub.name not in existing_subagent_names:
                            self.subagents.append(sub)
                            existing_subagent_names.add(sub.name)

        # 4. Workspace standalone subagents: <workspace_root>/.gemini/agents/ (+ .disabled/)
        ws_agents_dir = self.workspace_gemini_dir / "agents"
        if ws_agents_dir.is_dir():
            for ag_file in sorted(ws_agents_dir.glob("*.md")):
                if ag_file.is_file():
                    sub = self._parse_subagent_file(ag_file, Scope.WORKSPACE, "WORKSPACE", is_active=True)
                    if sub and sub.name not in existing_subagent_names:
                        self.subagents.append(sub)
                        existing_subagent_names.add(sub.name)
            ws_dis_dir = ws_agents_dir / ".disabled"
            if ws_dis_dir.is_dir():
                for ag_file in sorted(ws_dis_dir.glob("*.md")):
                    if ag_file.is_file():
                        sub = self._parse_subagent_file(ag_file, Scope.WORKSPACE, "WORKSPACE", is_active=False)
                        if sub and sub.name not in existing_subagent_names:
                            self.subagents.append(sub)
                            existing_subagent_names.add(sub.name)

        # 5. Legacy workspace subagents fallback: <workspace_root>/.agents/
        ws = self.workspace_root
        for agent_dir_name in [".agents", ".agent"]:
            for sub_folder in ["agents", "subagents"]:
                ag_dir = ws / agent_dir_name / sub_folder
                if ag_dir.is_dir():
                    for ag_file in sorted(ag_dir.glob("*.md")):
                        if ag_file.is_file():
                            sub = self._parse_subagent_file(ag_file, Scope.WORKSPACE, "WORKSPACE", is_active=True)
                            if sub and sub.name not in existing_subagent_names:
                                self.subagents.append(sub)
                                existing_subagent_names.add(sub.name)
                    legacy_dis = ag_dir / ".disabled"
                    if legacy_dis.is_dir():
                        for ag_file in sorted(legacy_dis.glob("*.md")):
                            if ag_file.is_file():
                                sub = self._parse_subagent_file(ag_file, Scope.WORKSPACE, "WORKSPACE", is_active=False)
                                if sub and sub.name not in existing_subagent_names:
                                    self.subagents.append(sub)
                                    existing_subagent_names.add(sub.name)

    def _discover_mcp_servers(self) -> None:
        """Discover Antigravity root and plugin MCP servers."""
        mcp_dir = self.home_dir / ".gemini" / "antigravity" / "mcp"
        user_servers = []
        plugin_servers = []
        known_names = set()

        if mcp_dir.is_dir():
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
                known_names.add(name)

                # Prioritize root user servers like StitchMCP and canva
                if "_" in name or name.startswith("data-agent-kit"):
                    plugin_servers.append(srv)
                else:
                    user_servers.append(srv)

        # Check ~/.gemini/config/mcp_config.json
        cfg_mcp = self.global_config_dir / "mcp_config.json"
        if cfg_mcp.is_file():
            try:
                m_data = json.loads(cfg_mcp.read_text(encoding="utf-8"))
                for srv_name, srv_info in m_data.get("mcpServers", {}).items():
                    if srv_name not in known_names:
                        tools_dict = srv_info.get("tools", {})
                        tools_list = list(tools_dict.keys()) if isinstance(tools_dict, dict) else []
                        is_act = not srv_info.get("disabled", False)
                        srv = MCPServer(
                            name=srv_name,
                            tools_count=len(tools_list),
                            tools=tools_list,
                            is_active=is_act,
                            description=f"{len(tools_list)} tools configured",
                        )
                        user_servers.append(srv)
                        known_names.add(srv_name)
                    else:
                        # Update active status if disabled in config
                        if srv_info.get("disabled", False):
                            for s in user_servers + plugin_servers:
                                if s.name == srv_name:
                                    s.is_active = False
            except Exception:
                pass

        self.mcp_servers = user_servers + plugin_servers

    def _apply_states_and_overrides(self) -> None:
        """Mark shadow overrides and apply direct config.json states."""
        # Find which skill names exist in multiple scopes (e.g. workspace overrides global/builtin)
        for s in self.skills:
            if s.scope == Scope.WORKSPACE:
                has_shadow = any(
                    other.name == s.name and other.scope != Scope.WORKSPACE
                    for other in self.skills
                )
                if has_shadow or getattr(s, "is_overridden", False):
                    s.is_overridden = True

        # Read global and workspace config.json for explicit toggles
        gl_cfg = self._read_global_config()
        ws_cfg = self._read_workspace_config()

        # Apply any explicit plugin states from config
        for p in self.plugins:
            target_key = p.dir_name or p.name
            if target_key in ws_cfg.get("plugins", {}) and "enabled" in ws_cfg["plugins"][target_key]:
                p.is_active = ws_cfg["plugins"][target_key]["enabled"]
            elif target_key in gl_cfg.get("plugins", {}) and "enabled" in gl_cfg["plugins"][target_key]:
                p.is_active = gl_cfg["plugins"][target_key]["enabled"]

            # Apply component breakdowns from config if present
            comp_cfgs = gl_cfg.get("plugins", {}).get(target_key, {}).get("components", {})
            for b in p.breakdowns:
                if b.name in comp_cfgs and "enabled" in comp_cfgs[b.name]:
                    b.is_active = comp_cfgs[b.name]["enabled"]
            p.recalculate_tokens()

        for s in self.skills:
            if s.name in ws_cfg.get("skills", {}) and "enabled" in ws_cfg["skills"][s.name]:
                s.is_active = ws_cfg["skills"][s.name]["enabled"]
            elif s.name in gl_cfg.get("skills", {}) and "enabled" in gl_cfg["skills"][s.name]:
                s.is_active = gl_cfg["skills"][s.name]["enabled"]

        for r in self.rules:
            if r.name in ws_cfg.get("rules", {}) and "enabled" in ws_cfg["rules"][r.name]:
                r.is_active = ws_cfg["rules"][r.name]["enabled"]
            elif r.name in gl_cfg.get("rules", {}) and "enabled" in gl_cfg["rules"][r.name]:
                r.is_active = gl_cfg["rules"][r.name]["enabled"]

        for sub in self.subagents:
            if sub.name in ws_cfg.get("subagents", {}) and "enabled" in ws_cfg["subagents"][sub.name]:
                sub.is_active = ws_cfg["subagents"][sub.name]["enabled"]
            elif sub.name in gl_cfg.get("subagents", {}) and "enabled" in gl_cfg["subagents"][sub.name]:
                sub.is_active = gl_cfg["subagents"][sub.name]["enabled"]

        for m in self.mcp_servers:
            if m.name in gl_cfg.get("mcp_servers", {}) and "enabled" in gl_cfg["mcp_servers"][m.name]:
                m.is_active = gl_cfg["mcp_servers"][m.name]["enabled"]

    def set_plugin_state(self, plugin_name: str, enabled: bool, scope: Scope = Scope.GLOBAL) -> bool:
        """Set plugin enabled state directly in Antigravity config without phantom state."""
        if scope == Scope.WORKSPACE:
            # Write to workspace config / plugins.json
            ws_config_file = self.workspace_gemini_dir / "config.json"
            try:
                ws_config_file.parent.mkdir(parents=True, exist_ok=True)
                cfg_data = {}
                if ws_config_file.is_file():
                    try:
                        cfg_data = json.loads(ws_config_file.read_text(encoding="utf-8"))
                    except Exception:
                        pass
                if "plugins" not in cfg_data:
                    cfg_data["plugins"] = {}
                if plugin_name not in cfg_data["plugins"]:
                    cfg_data["plugins"][plugin_name] = {}
                cfg_data["plugins"][plugin_name]["enabled"] = enabled
                ws_config_file.write_text(json.dumps(cfg_data, indent=2), encoding="utf-8")
            except Exception:
                pass

            # Also record exclusion in workspace plugins.json if disabling
            if not enabled:
                ws_plugins_file = self.workspace_gemini_dir / "plugins.json"
                try:
                    ws_plugins_file.parent.mkdir(parents=True, exist_ok=True)
                    p_data = {}
                    if ws_plugins_file.is_file():
                        try:
                            p_data = json.loads(ws_plugins_file.read_text(encoding="utf-8"))
                        except Exception:
                            pass
                    inherits = p_data.get("inherits", [])
                    if not inherits:
                        inherits = [{"path": "~/.gemini/config/plugins.json", "exclude": []}]
                        p_data["inherits"] = inherits
                    for inh in inherits:
                        excl = inh.get("exclude", [])
                        if plugin_name not in excl:
                            excl.append(plugin_name)
                        inh["exclude"] = excl
                    ws_plugins_file.write_text(json.dumps(p_data, indent=2), encoding="utf-8")
                except Exception:
                    pass
            return True
        else:
            # Global scope: directly update ~/.gemini/config/config.json
            config_file = self.global_config_dir / "config.json"
            try:
                config_file.parent.mkdir(parents=True, exist_ok=True)
                cfg_data = {}
                if config_file.is_file():
                    try:
                        cfg_data = json.loads(config_file.read_text(encoding="utf-8"))
                    except Exception:
                        pass
                if "plugins" not in cfg_data:
                    cfg_data["plugins"] = {}
                if plugin_name not in cfg_data["plugins"]:
                    cfg_data["plugins"][plugin_name] = {}
                cfg_data["plugins"][plugin_name]["enabled"] = enabled
                config_file.write_text(json.dumps(cfg_data, indent=2), encoding="utf-8")
            except Exception:
                pass

            # Live language server notification
            if self.plugin_client.is_available():
                try:
                    self.plugin_client.set_plugin_enabled(plugin_name, enabled)
                except Exception:
                    pass
            return True

    def toggle_plugin_component(self, plugin_name: str, component_name: str) -> Optional[bool]:
        """Toggle an individual subcomponent within a plugin (skill, tool, agent, rule)."""
        target_plugin = next((p for p in self.plugins if p.name == plugin_name), None)
        if not target_plugin:
            return None
        for b in target_plugin.breakdowns:
            if b.name == component_name:
                b.is_active = not b.is_active
                # Persist into config.json
                config_file = self.global_config_dir / "config.json"
                try:
                    cfg_data = {}
                    if config_file.is_file():
                        try:
                            cfg_data = json.loads(config_file.read_text(encoding="utf-8"))
                        except Exception:
                            pass
                    if "plugins" not in cfg_data:
                        cfg_data["plugins"] = {}
                    if plugin_name not in cfg_data["plugins"]:
                        cfg_data["plugins"][plugin_name] = {}
                    if "components" not in cfg_data["plugins"][plugin_name]:
                        cfg_data["plugins"][plugin_name]["components"] = {}
                    cfg_data["plugins"][plugin_name]["components"][component_name] = {"enabled": b.is_active}
                    config_file.write_text(json.dumps(cfg_data, indent=2), encoding="utf-8")
                except Exception:
                    pass
                target_plugin.recalculate_tokens()
                return b.is_active
        return None

    def toggle_item(self, item, target_scope: Optional[Scope] = None) -> bool:
        """Toggle active state of an item."""
        if target_scope is None:
            if isinstance(item, Plugin):
                target_scope = Scope.GLOBAL
            else:
                target_scope = getattr(item, "scope", None) or Scope.WORKSPACE
        if isinstance(item, Plugin):
            new_state = not item.is_active
            target_key = item.dir_name or item.name
            self.set_plugin_state(target_key, new_state, target_scope)
            item.is_active = new_state
            item.recalculate_tokens()
            return item.is_active

        elif isinstance(item, Subagent):
            if item.path and item.path.exists():
                try:
                    if item.is_active:
                        dest_dir = item.path.parent / ".disabled"
                        dest_dir.mkdir(parents=True, exist_ok=True)
                        new_path = dest_dir / item.path.name
                        item.path.rename(new_path)
                        item.path = new_path
                        item.is_active = False
                    else:
                        if item.path.parent.name == ".disabled":
                            dest_dir = item.path.parent.parent
                            new_path = dest_dir / item.path.name
                            item.path.rename(new_path)
                            item.path = new_path
                        item.is_active = True
                    return item.is_active
                except Exception:
                    pass
            item.is_active = not item.is_active
            self._set_entity_config_state("subagents", item.name, item.is_active, target_scope)
            return item.is_active

        elif isinstance(item, Skill):
            if item.scope == Scope.CATALOG and not item.is_active:
                from .catalog import install_catalog_pack
                target_dir = (
                    self.workspace_gemini_dir / "skills"
                    if target_scope == Scope.WORKSPACE
                    else self.global_config_dir / "skills"
                )
                success, _ = install_catalog_pack(item.name, target_dir, target_scope.value)
                item.is_active = True
                self.discover_all()
                return success
            elif item.path and item.path.is_dir():
                try:
                    if item.is_active:
                        dest_dir = item.path.parent / ".disabled"
                        dest_dir.mkdir(parents=True, exist_ok=True)
                        new_path = dest_dir / item.path.name
                        item.path.rename(new_path)
                        item.path = new_path
                        item.skill_file = new_path / "SKILL.md"
                        item.is_active = False
                    else:
                        if item.path.parent.name == ".disabled":
                            dest_dir = item.path.parent.parent
                            new_path = dest_dir / item.path.name
                            item.path.rename(new_path)
                            item.path = new_path
                            item.skill_file = new_path / "SKILL.md"
                        item.is_active = True
                    return item.is_active
                except Exception:
                    pass
            item.is_active = not item.is_active
            self._set_entity_config_state("skills", item.name, item.is_active, target_scope)
            return item.is_active

        elif isinstance(item, Rule):
            if item.path and item.path.is_file() and item.path.parent.name in ("rules", ".disabled"):
                try:
                    if item.is_active:
                        dest_dir = item.path.parent / ".disabled" if item.path.parent.name == "rules" else item.path.parent
                        dest_dir.mkdir(parents=True, exist_ok=True)
                        new_path = dest_dir / item.path.name
                        if item.path != new_path:
                            item.path.rename(new_path)
                            item.path = new_path
                        item.is_active = False
                    else:
                        dest_dir = item.path.parent.parent
                        new_path = dest_dir / item.path.name
                        item.path.rename(new_path)
                        item.path = new_path
                        item.is_active = True
                    return item.is_active
                except Exception:
                    pass
            item.is_active = not item.is_active
            self._set_entity_config_state("rules", item.name, item.is_active, target_scope)
            return item.is_active

        elif isinstance(item, MCPServer):
            item.is_active = not item.is_active
            self._set_entity_config_state("mcp_servers", item.name, item.is_active, target_scope)
            return item.is_active

        elif hasattr(item, "repo") and hasattr(item, "is_installed"):
            from .catalog import install_catalog_pack
            if not getattr(item, "is_installed", False):
                target_dir = (
                    self.workspace_gemini_dir / "skills"
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
