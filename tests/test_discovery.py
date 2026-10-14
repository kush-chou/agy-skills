"""Unit tests for lean Antigravity skills and rules discovery."""

import json
from pathlib import Path
import tempfile
import unittest

from agy_skills.discovery import CustomizationRegistry, find_workspace_root
from agy_skills.models import Scope


class TestDiscovery(unittest.TestCase):
    def test_find_workspace_root(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir).resolve()
            git_dir = root / ".git"
            git_dir.mkdir()

            sub_dir = root / "src" / "pkg"
            sub_dir.mkdir(parents=True)

            found = find_workspace_root(sub_dir)
            self.assertEqual(found, root)

    def test_find_workspace_root_never_home(self):
        # Even if home has .git, find_workspace_root strictly refuses to return home
        home = Path.home().resolve()
        sub = home / "some_random_sub_test_dir_12345"
        # Since sub doesn't have .git, walking up reaches home which is skipped
        res = find_workspace_root(home)
        self.assertIsNone(res)

    def test_discover_subagents(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / ".git").mkdir()
            home = root / "fake_home"
            home.mkdir()

            # Global subagent
            g_agent = home / ".gemini" / "config" / "agents" / "global-agent.md"
            g_agent.parent.mkdir(parents=True, exist_ok=True)
            g_agent.write_text(
                "---\nname: global-agent\ndescription: Global assistant agent.\ntools: [read_file]\n---\nSystem prompt here.",
                encoding="utf-8",
            )

            # Workspace subagent
            w_agent = root / ".agents" / "agents" / "local-agent.md"
            w_agent.parent.mkdir(parents=True, exist_ok=True)
            w_agent.write_text(
                "---\nname: local-agent\ndescription: Workspace local agent.\ntools: [run_command]\n---\nLocal system prompt.",
                encoding="utf-8",
            )

            registry = CustomizationRegistry(workspace_root=root, home_dir=home)
            registry.discover_all()

            self.assertEqual(len(registry.subagents), 2)
            names = {a.name for a in registry.subagents}
            self.assertEqual(names, {"global-agent", "local-agent"})

            # Toggle workspace agent
            local_a = registry.find_item("local-agent")
            self.assertIsNotNone(local_a)
            self.assertTrue(local_a.is_active)
            registry.toggle_item(local_a)
            self.assertFalse(local_a.is_active)
            self.assertTrue((root / ".agents" / "agents" / ".disabled" / "local-agent.md").is_file())

            # Toggle back
            registry.toggle_item(local_a)
            self.assertTrue(local_a.is_active)
            self.assertTrue(w_agent.is_file())

    def test_discover_workspace_items(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / ".git").mkdir()

            # Create workspace skill
            skill_dir = root / ".agents" / "skills" / "local-helper"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\nname: local-helper\ndescription: Project specific helper procedure.\n---\n# Steps\n1. Run",
                encoding="utf-8",
            )

            # Create workspace rule
            (root / "GEMINI.md").write_text("# Project guidelines\nDo not break builds.", encoding="utf-8")

            home = root / "fake_home"
            home.mkdir()

            registry = CustomizationRegistry(workspace_root=root, home_dir=home)
            skills, rules = registry.discover_all()

            ws_skills = [s for s in skills if s.scope == Scope.WORKSPACE]
            ws_rules = [r for r in rules if r.scope == Scope.WORKSPACE]

            self.assertEqual(len(ws_skills), 1)
            self.assertEqual(ws_skills[0].name, "local-helper")
            self.assertEqual(len(ws_rules), 1)
            self.assertEqual(ws_rules[0].name, "GEMINI.md")

    def test_discover_global_items(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / ".git").mkdir()
            home = root / "fake_home"
            home.mkdir()

            # Global skill
            g_skill = home / ".gemini" / "config" / "skills" / "global-helper"
            g_skill.mkdir(parents=True)
            (g_skill / "SKILL.md").write_text(
                "---\nname: global-helper\ndescription: Global helper tool.\n---\nBody",
                encoding="utf-8",
            )

            # Global rule
            g_rule = home / ".gemini" / "config" / "GEMINI.md"
            g_rule.parent.mkdir(parents=True, exist_ok=True)
            g_rule.write_text("# Global Rules\nBe kind.", encoding="utf-8")

            registry = CustomizationRegistry(workspace_root=root, home_dir=home)
            skills, rules = registry.discover_all()

            gl_skills = [s for s in skills if s.scope == Scope.GLOBAL]
            gl_rules = [r for r in rules if r.scope == Scope.GLOBAL]

            self.assertEqual(len(gl_skills), 1)
            self.assertEqual(gl_skills[0].name, "global-helper")
            self.assertEqual(len(gl_rules), 1)
            self.assertEqual(gl_rules[0].name, "GEMINI.md")

    def test_workspace_overrides_global(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / ".git").mkdir()
            home = root / "fake_home"
            home.mkdir()

            # Global skill 'deploy-tool'
            g_skill = home / ".gemini" / "config" / "skills" / "deploy-tool"
            g_skill.mkdir(parents=True)
            (g_skill / "SKILL.md").write_text(
                "---\nname: deploy-tool\ndescription: Global deploy tool.\n---\nGlobal body",
                encoding="utf-8",
            )

            # Workspace skill 'deploy-tool' (same name)
            w_skill = root / ".agents" / "skills" / "deploy-tool"
            w_skill.mkdir(parents=True)
            (w_skill / "SKILL.md").write_text(
                "---\nname: deploy-tool\ndescription: Workspace deploy tool.\n---\nWorkspace body",
                encoding="utf-8",
            )

            registry = CustomizationRegistry(workspace_root=root, home_dir=home)
            skills, _ = registry.discover_all()

            ws_item = next(s for s in skills if s.scope == Scope.WORKSPACE and s.name == "deploy-tool")
            gl_item = next(s for s in skills if s.scope == Scope.GLOBAL and s.name == "deploy-tool")

            self.assertTrue(ws_item.is_active)
            self.assertFalse(ws_item.is_overridden)

            # Global item is marked overridden and inactive
            self.assertTrue(gl_item.is_overridden)
            self.assertFalse(gl_item.is_active)

    def test_declarative_toggling_persists_to_json(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / ".git").mkdir()
            home = root / "fake_home"
            home.mkdir()

            skill_dir = root / ".agents" / "skills" / "my-skill"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\nname: my-skill\ndescription: Workspace skill.\n---\nBody",
                encoding="utf-8",
            )

            registry = CustomizationRegistry(workspace_root=root, home_dir=home)
            registry.discover_all()

            skill = registry.find_item("my-skill")
            self.assertIsNotNone(skill)
            self.assertTrue(skill.is_active)

            # Toggle off
            registry.toggle_item(skill)
            self.assertFalse(skill.is_active)
            self.assertFalse(skill_dir.is_dir())
            self.assertTrue((root / ".agents" / "skills" / ".disabled" / "my-skill").is_dir())

            # Workspace config.json records enabled: False
            cfg_file = root / ".agents" / "config.json"
            self.assertTrue(cfg_file.is_file())
            data = json.loads(cfg_file.read_text(encoding="utf-8"))
            self.assertFalse(data["skills"]["my-skill"]["enabled"])

            # Toggle back on
            registry.toggle_item(skill)
            self.assertTrue(skill.is_active)
            self.assertTrue(skill_dir.is_dir())
            self.assertFalse((root / ".agents" / "skills" / ".disabled" / "my-skill").exists())
            data2 = json.loads(cfg_file.read_text(encoding="utf-8"))
            self.assertTrue(data2["skills"]["my-skill"]["enabled"])


if __name__ == "__main__":
    unittest.main()
