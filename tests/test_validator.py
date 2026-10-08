"""Unit tests for Antigravity rules and skill validation."""

from pathlib import Path
import tempfile
import unittest

from agy_skills.models import Rule, Scope, Skill
from agy_skills.validator import (
    MAX_RULE_SIZE_BYTES,
    validate_rule,
    validate_skill,
)


class TestValidator(unittest.TestCase):
    def test_valid_skill(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            dir_path = Path(tmp_dir) / "valid-skill"
            dir_path.mkdir()
            skill_file = dir_path / "SKILL.md"
            skill_file.write_text(
                "---\nname: valid-skill\ndescription: A valid skill description that is long enough.\n---\n# Docs",
                encoding="utf-8",
            )
            skill = Skill.from_directory(dir_path, Scope.WORKSPACE)
            self.assertIsNotNone(skill)
            errors = validate_skill(skill)
            self.assertEqual(errors, [])
            self.assertTrue(skill.is_valid)

    def test_invalid_skill_name_kebab_case(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            dir_path = Path(tmp_dir) / "Invalid_Name"
            dir_path.mkdir()
            skill_file = dir_path / "SKILL.md"
            skill_file.write_text(
                "---\nname: Invalid_Name\ndescription: A valid description that meets the length threshold.\n---\n",
                encoding="utf-8",
            )
            skill = Skill.from_directory(dir_path, Scope.WORKSPACE)
            self.assertIsNotNone(skill)
            errors = validate_skill(skill)
            self.assertFalse(skill.is_valid)
            self.assertTrue(any("kebab-case" in e for e in errors))

    def test_invalid_skill_short_description(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            dir_path = Path(tmp_dir) / "short-desc"
            dir_path.mkdir()
            skill_file = dir_path / "SKILL.md"
            skill_file.write_text(
                "---\nname: short-desc\ndescription: Too short.\n---\n",
                encoding="utf-8",
            )
            skill = Skill.from_directory(dir_path, Scope.WORKSPACE)
            self.assertIsNotNone(skill)
            errors = validate_skill(skill)
            self.assertFalse(skill.is_valid)
            self.assertTrue(any("too brief" in e for e in errors))

    def test_rule_within_budget(self):
        with tempfile.NamedTemporaryFile("w+", suffix=".md", delete=False) as tf:
            tf.write("# Style Guidelines\nAlways write tests and clean code.")
            tf_path = Path(tf.name)

        try:
            rule = Rule.from_file(tf_path, Scope.WORKSPACE)
            self.assertIsNotNone(rule)
            errors = validate_rule(rule)
            self.assertEqual(errors, [])
            self.assertTrue(rule.is_valid)
        finally:
            tf_path.unlink()

    def test_rule_exceeding_24kb(self):
        with tempfile.NamedTemporaryFile("w+", suffix=".md", delete=False) as tf:
            tf.write("x" * (MAX_RULE_SIZE_BYTES + 100))
            tf_path = Path(tf.name)

        try:
            rule = Rule.from_file(tf_path, Scope.WORKSPACE)
            self.assertIsNotNone(rule)
            errors = validate_rule(rule)
            self.assertFalse(rule.is_valid)
            self.assertTrue(any("24 KB" in e for e in errors))
        finally:
            tf_path.unlink()


if __name__ == "__main__":
    unittest.main()
