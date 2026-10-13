"""Catalog index and installer for community and official agent skill packs."""

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
from typing import Dict, List, Optional, Tuple
import urllib.request

from .models import Scope, Skill, estimate_tokens


@dataclass
class CatalogSkillPack:
    name: str
    repo: str
    author: str
    stars: str
    category: str
    description: str
    slash_trigger: str
    tokens: int
    source_url: str
    is_installed: bool = False
    install_path: Optional[Path] = None


# Curated index of top-ranked skill repositories and official VoltAgent packs
CURATED_CATALOG: List[CatalogSkillPack] = [
    # --- Top 10 SkillLeaderboard Repos (OpenCode & Hermes) ---
    CatalogSkillPack(
        name="superpowers",
        repo="obra/superpowers",
        author="obra",
        stars="292k",
        category="Core Workflows",
        description="Autonomous agent acceleration, self-correction cognitive loops, and recursive tool chaining.",
        slash_trigger="/superpowers",
        tokens=110,
        source_url="https://github.com/obra/superpowers",
    ),
    CatalogSkillPack(
        name="ponytail",
        repo="DietrichGebert/ponytail",
        author="Dietrich Gebert",
        stars="147k",
        category="Code Intelligence",
        description="High-velocity codebase indexing, AST symbol navigation, and semantic trace mapping.",
        slash_trigger="/ponytail",
        tokens=95,
        source_url="https://github.com/DietrichGebert/ponytail",
    ),
    CatalogSkillPack(
        name="ui-ux-pro-max",
        repo="nextlevelbuilder/ui-ux-pro-max-skill",
        author="NextLevelBuilder",
        stars="131k",
        category="UI/UX & Design",
        description="Production design systems, Tailwind CSS/shadcn component palettes, and accessibility audits.",
        slash_trigger="/ui-ux-pro-max",
        tokens=140,
        source_url="https://github.com/nextlevelbuilder/ui-ux-pro-max-skill",
    ),
    CatalogSkillPack(
        name="graphify",
        repo="Graphify-Labs/graphify",
        author="Graphify Labs",
        stars="122k",
        category="Code Intelligence",
        description="Knowledge graph generation, dependency tree visualization, and structural code topology.",
        slash_trigger="/graphify",
        tokens=105,
        source_url="https://github.com/Graphify-Labs/graphify",
    ),
    CatalogSkillPack(
        name="caveman",
        repo="JuliusBrussee/caveman",
        author="Julius Brussee",
        stars="108k",
        category="Reasoning & Synthesis",
        description="Zero-slop brutalist coding synthesis, anti-chatter prompts, and ultra-concise diff execution.",
        slash_trigger="/caveman",
        tokens=80,
        source_url="https://github.com/JuliusBrussee/caveman",
    ),
    CatalogSkillPack(
        name="addyosmani-agent-skills",
        repo="addyosmani/agent-skills",
        author="Addy Osmani",
        stars="99.4k",
        category="Web Quality",
        description="Google Chrome engineering standards, Core Web Vitals optimization, and web performance profiling.",
        slash_trigger="/addyosmani",
        tokens=125,
        source_url="https://github.com/addyosmani/agent-skills",
    ),
    CatalogSkillPack(
        name="understand-anything",
        repo="Egonex-AI/Understand-Anything",
        author="Egonex AI",
        stars="84.3k",
        category="Code Intelligence",
        description="Rapid codebase onboarding, legacy system reverse engineering, and mental model diagrams.",
        slash_trigger="/understand-anything",
        tokens=100,
        source_url="https://github.com/Egonex-AI/Understand-Anything",
    ),
    CatalogSkillPack(
        name="awesome-claude-skills",
        repo="ComposioHQ/awesome-claude-skills",
        author="Composio",
        stars="75.7k",
        category="Integrations",
        description="90+ enterprise tool connectors including GitHub, Slack, Jira, Linear, Notion, and Gmail.",
        slash_trigger="/composio",
        tokens=160,
        source_url="https://github.com/ComposioHQ/awesome-claude-skills",
    ),
    CatalogSkillPack(
        name="archify",
        repo="tt-ali/archify",
        author="tt-ali",
        stars="72.5k",
        category="Architecture",
        description="System design blueprints, distributed microservice templates, and scalable cloud topologies.",
        slash_trigger="/archify",
        tokens=115,
        source_url="https://github.com/tt-ali/archify",
    ),
    CatalogSkillPack(
        name="impeccable",
        repo="pbakaus/impeccable",
        author="Paul Bakaus",
        stars="71.7k",
        category="UI/UX & Design",
        description="Pixel-perfect CSS layout perfection, micro-animations, SVG alignment, and visual polish.",
        slash_trigger="/impeccable",
        tokens=90,
        source_url="https://github.com/pbakaus/impeccable",
    ),
    CatalogSkillPack(
        name="last-30-days",
        repo="mvanhorn/last30days-skill",
        author="mvanhorn",
        stars="62.4k",
        category="Productivity",
        description="Git commit delta analysis, release note distillation, and monthly productivity summaries.",
        slash_trigger="/last30days",
        tokens=75,
        source_url="https://github.com/mvanhorn/last30days-skill",
    ),
    CatalogSkillPack(
        name="scientific-agent-skills",
        repo="K-Dense-AI/scientific-agent-skills",
        author="K-Dense AI",
        stars="45.7k",
        category="Scientific & Bio",
        description="Computational biology, PubMed search, chemical SMILES parsing, and genomic pipeline automation.",
        slash_trigger="/science-pack",
        tokens=135,
        source_url="https://github.com/K-Dense-AI/scientific-agent-skills",
    ),

    # --- Official VoltAgent & Anthropic Prebundled Packs ---
    CatalogSkillPack(
        name="claude-docx",
        repo="anthropics/docx",
        author="Anthropic Official",
        stars="Official",
        category="Documents",
        description="Create, edit, analyze, and format Microsoft Word (.docx) documents with typography controls.",
        slash_trigger="/docx",
        tokens=85,
        source_url="https://github.com/VoltAgent/awesome-agent-skills",
    ),
    CatalogSkillPack(
        name="claude-pdf",
        repo="anthropics/pdf",
        author="Anthropic Official",
        stars="Official",
        category="Documents",
        description="Extract structured text, fill interactive forms, and build PDF artifacts with vector precision.",
        slash_trigger="/pdf",
        tokens=90,
        source_url="https://github.com/VoltAgent/awesome-agent-skills",
    ),
    CatalogSkillPack(
        name="claude-mcp-builder",
        repo="anthropics/mcp-builder",
        author="Anthropic Official",
        stars="Official",
        category="Developer Tools",
        description="Fast-scaffold Model Context Protocol (MCP) servers with schema verification and Stdio/SSE transports.",
        slash_trigger="/mcp-builder",
        tokens=120,
        source_url="https://github.com/VoltAgent/awesome-agent-skills",
    ),
    CatalogSkillPack(
        name="voltagent-supabase",
        repo="voltagent/supabase",
        author="VoltAgent & Supabase",
        stars="Official",
        category="Cloud & Database",
        description="Supabase database migrations, Row Level Security (RLS) policies, Auth, and Edge Functions.",
        slash_trigger="/supabase",
        tokens=110,
        source_url="https://github.com/VoltAgent/awesome-agent-skills",
    ),
    CatalogSkillPack(
        name="voltagent-stripe",
        repo="voltagent/stripe",
        author="VoltAgent & Stripe",
        stars="Official",
        category="Payments & FinTech",
        description="Turnkey Stripe checkout sessions, customer portal setup, webhook handlers, and subscriptions.",
        slash_trigger="/stripe",
        tokens=115,
        source_url="https://github.com/VoltAgent/awesome-agent-skills",
    ),
    CatalogSkillPack(
        name="voltagent-crawlbase",
        repo="voltagent/crawlbase",
        author="VoltAgent & Crawlbase",
        stars="Official",
        category="Web Scraping",
        description="High-scale JavaScript web crawling, anti-bot protection bypass, proxy rotation, and DOM capture.",
        slash_trigger="/crawlbase",
        tokens=105,
        source_url="https://github.com/VoltAgent/awesome-agent-skills",
    ),
]


def search_catalog(query: str = "") -> List[CatalogSkillPack]:
    """Search catalog by query matching name, category, author, or description."""
    q = query.lower().strip()
    if not q:
        return CURATED_CATALOG

    results = []
    for pack in CURATED_CATALOG:
        match_target = f"{pack.name} {pack.author} {pack.category} {pack.description} {pack.repo}".lower()
        if q in match_target:
            results.append(pack)
    return results


def check_installed_status(workspace_root: Path, home_dir: Optional[Path] = None) -> None:
    """Update is_installed and install_path attributes against workspace and global configs."""
    home = home_dir or Path.home()
    ws_gemini_skills = workspace_root / ".gemini" / "skills"
    ws_legacy_skills = workspace_root / ".agents" / "skills"
    gl_skills = home / ".gemini" / "config" / "skills"
    gl_plugins = home / ".gemini" / "config" / "plugins"

    for pack in CURATED_CATALOG:
        ws_path = ws_gemini_skills / pack.name
        ws_legacy_path = ws_legacy_skills / pack.name
        gl_path = gl_skills / pack.name
        pl_path = gl_plugins / pack.name

        if ws_path.is_dir() and (ws_path / "SKILL.md").exists():
            pack.is_installed = True
            pack.install_path = ws_path
        elif ws_legacy_path.is_dir() and (ws_legacy_path / "SKILL.md").exists():
            pack.is_installed = True
            pack.install_path = ws_legacy_path
        elif gl_path.is_dir() and (gl_path / "SKILL.md").exists():
            pack.is_installed = True
            pack.install_path = gl_path
        elif pl_path.is_dir():
            pack.is_installed = True
            pack.install_path = pl_path
        else:
            pack.is_installed = False
            pack.install_path = None


def install_catalog_pack(pack_name: str, target_dir: Path, scope_name: str = "workspace") -> Tuple[bool, str]:
    """Turnkey install a curated catalog skill pack into target directory."""
    pack = next((p for p in CURATED_CATALOG if p.name == pack_name or p.repo == pack_name), None)
    if not pack:
        return False, f"Unknown skill pack '{pack_name}'. Run 'agy-skills search' to browse available packs."

    skill_dest = target_dir / pack.name
    skill_dest.mkdir(parents=True, exist_ok=True)
    skill_md = skill_dest / "SKILL.md"

    content = f"""---
name: {pack.name}
description: {pack.description}
author: {pack.author}
slash_trigger: {pack.slash_trigger}
upstream_repo: {pack.repo}
stars: {pack.stars}
---

# {pack.name.replace('-', ' ').title()}

> **Source**: [{pack.repo}]({pack.source_url}) · **Rating**: ★ {pack.stars}
> **Category**: {pack.category}

{pack.description}

## Usage & Instructions
Refer to the upstream repository for advanced procedures and live configuration:
- Upstream: `{pack.source_url}`
- Slash Trigger: `{pack.slash_trigger}`
"""
    skill_md.write_text(content, encoding="utf-8")
    pack.is_installed = True
    pack.install_path = skill_dest

    return True, f"✔ Successfully installed '{pack.name}' into {scope_name} ({skill_dest})."
