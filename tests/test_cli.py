"""Unit tests for agy-skills CLI commands and outputs."""

import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

from agy_skills.cli import (
    cli_disable,
    cli_enable,
    cli_info,
    cli_lint,
    cli_list,
    cli_status,
)
from agy_skills.discovery import CustomizationRegistry
from agy_skills.models import Scope


class TestCLI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".git").mkdir()

        # Create valid workspace skill
        s_dir = self.root / ".agents" / "skills" / "sample-skill"
        s_dir.mkdir(parents=True)
        (s_dir / "SKILL.md").write_text(
            "---\nname: sample-skill\ndescription: A valid sample skill for testing CLI output.\n---\nBody here.",
            encoding="utf-8",
        )

        # Create workspace rule
        (self.root / "GEMINI.md").write_text("# Style Guide\nWrite clean tests.", encoding="utf-8")

        self.home = self.root / "fake_home"
        self.home.mkdir()

        self.registry = CustomizationRegistry(workspace_root=self.root, home_dir=self.home)

    def tearDown(self):
        self.tmp.cleanup()

    def test_cli_list_text_and_json(self):
        captured = io.StringIO()
        sys.stdout = captured
        try:
            exit_code = cli_list(self.registry)
        finally:
            sys.stdout = sys.__stdout__

        out = captured.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("sample-skill", out)
        self.assertIn("GEMINI.md", out)

        # JSON mode
        captured_json = io.StringIO()
        sys.stdout = captured_json
        try:
            exit_json = cli_list(self.registry, as_json=True)
        finally:
            sys.stdout = sys.__stdout__

        self.assertEqual(exit_json, 0)
        data = json.loads(captured_json.getvalue())
        self.assertIn("skills", data)
        self.assertIn("rules", data)
        self.assertEqual(data["skills"][0]["name"], "sample-skill")

    def test_cli_status_text_and_json(self):
        captured = io.StringIO()
        sys.stdout = captured
        try:
            exit_code = cli_status(self.registry)
        finally:
            sys.stdout = sys.__stdout__

        out = captured.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("Context Gauge:", out)
        self.assertIn("20,000", out)

        # JSON mode
        captured_json = io.StringIO()
        sys.stdout = captured_json
        try:
            exit_json = cli_status(self.registry, as_json=True)
        finally:
            sys.stdout = sys.__stdout__

        self.assertEqual(exit_json, 0)
        data = json.loads(captured_json.getvalue())
        self.assertEqual(data["token_budget"], 20000)
        self.assertIn("counts", data)
        self.assertIn("compliance", data)

    def test_cli_enable_and_disable(self):
        captured = io.StringIO()
        sys.stdout = captured
        try:
            # Disable
            ret_dis = cli_disable(self.registry, "sample-skill")
            self.assertEqual(ret_dis, 0)
            self.registry.discover_all()
            skill = self.registry.find_item("sample-skill")
            self.assertFalse(skill.is_active)

            # Re-enable
            ret_en = cli_enable(self.registry, "sample-skill")
            self.assertEqual(ret_en, 0)
            self.registry.discover_all()
            skill = self.registry.find_item("sample-skill")
            self.assertTrue(skill.is_active)
        finally:
            sys.stdout = sys.__stdout__

    def test_cli_info_text_and_json(self):
        captured = io.StringIO()
        sys.stdout = captured
        try:
            exit_code = cli_info(self.registry, "sample-skill")
        finally:
            sys.stdout = sys.__stdout__

        self.assertEqual(exit_code, 0)
        out = captured.getvalue()
        self.assertIn("sample-skill", out)
        self.assertIn("WORKSPACE", out)

        # JSON mode
        captured_json = io.StringIO()
        sys.stdout = captured_json
        try:
            exit_json = cli_info(self.registry, "sample-skill", as_json=True)
        finally:
            sys.stdout = sys.__stdout__

        self.assertEqual(exit_json, 0)
        data = json.loads(captured_json.getvalue())
        self.assertEqual(data["name"], "sample-skill")
        self.assertEqual(data["scope"], "workspace")

    def test_cli_lint(self):
        captured = io.StringIO()
        sys.stdout = captured
        try:
            exit_code = cli_lint(self.registry)
        finally:
            sys.stdout = sys.__stdout__

        self.assertEqual(exit_code, 0)
        out = captured.getvalue()
        self.assertIn("adhere to Antigravity specifications", out)


if __name__ == "__main__":
    unittest.main()
