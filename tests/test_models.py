"""Unit tests for models and frontmatter parsing."""

from pathlib import Path
import tempfile
import unittest

from agy_skills.models import (
    EntityType,
    Rule,
    Scope,
    Skill,
    Subagent,
    parse_frontmatter,
)


class TestModels(unittest.TestCase):
    def test_parse_frontmatter_single_line(self):
        content = """---
name: test-skill
description: A helpful skill for testing
---
# Skill Title
Instructions here.
"""
        fm, body = parse_frontmatter(content)
        self.assertEqual(fm.get("name"), "test-skill")
        self.assertEqual(fm.get("description"), "A helpful skill for testing")
        self.assertIn("# Skill Title", body)

    def test_parse_frontmatter_folded_multiline(self):
        content = """---
name: deploy-helper
description: >-
  This skill performs deployment operations
  across multiple environments and stages.
---
## Body
Details.
"""
        fm, body = parse_frontmatter(content)
        self.assertEqual(fm.get("name"), "deploy-helper")
        self.assertEqual(
            fm.get("description"),
            "This skill performs deployment operations across multiple environments and stages.",
        )
        self.assertIn("## Body", body)

    def test_skill_from_directory(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            dir_path = Path(tmp_dir) / "test-skill"
            dir_path.mkdir()
            skill_md = dir_path / "SKILL.md"
            skill_md.write_text(
                "---\nname: test-skill\ndescription: Test description for unit testing.\n---\nBody here.",
                encoding="utf-8",
            )
            scripts_dir = dir_path / "scripts"
            scripts_dir.mkdir()
            (scripts_dir / "run.sh").write_text("echo hi", encoding="utf-8")

            skill = Skill.from_directory(dir_path, Scope.WORKSPACE)
            self.assertIsNotNone(skill)
            self.assertEqual(skill.name, "test-skill")
            self.assertEqual(skill.scope, Scope.WORKSPACE)
            self.assertEqual(len(skill.scripts), 1)
            self.assertEqual(skill.scripts[0].name, "run.sh")

    def test_rule_from_file(self):
        with tempfile.NamedTemporaryFile("w+", suffix=".md", delete=False) as tf:
            tf.write("# Test Rules\nMust write tests.")
            tf_path = Path(tf.name)

        try:
            rule = Rule.from_file(tf_path, Scope.GLOBAL)
            self.assertIsNotNone(rule)
            self.assertEqual(rule.scope, Scope.GLOBAL)
            self.assertGreater(rule.size_bytes, 0)
            self.assertIn("Must write tests.", rule.raw_content)
        finally:
            tf_path.unlink()

    def test_subagent_from_file(self):
        with tempfile.NamedTemporaryFile("w+", suffix=".md", delete=False) as tf:
            tf.write("---\nname: test-bot\ndescription: A bot for testing models.\ntools: [run_command, read_file]\nmodel: inherit\n---\nSystem instructions here.")
            tf_path = Path(tf.name)

        try:
            agent = Subagent.from_file(tf_path, Scope.WORKSPACE)
            self.assertIsNotNone(agent)
            self.assertEqual(agent.name, "test-bot")
            self.assertEqual(agent.description, "A bot for testing models.")
            self.assertEqual(agent.tools, ["run_command", "read_file"])
            self.assertEqual(agent.model, "inherit")
            self.assertEqual(agent.scope, Scope.WORKSPACE)
            self.assertEqual(agent.entity_type, EntityType.SUBAGENT)
            self.assertIn("System instructions here.", agent.raw_content)
        finally:
            tf_path.unlink()


if __name__ == "__main__":
    unittest.main()
