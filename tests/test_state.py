"""Unit tests for deterministic JSON configuration state management."""

import json
from pathlib import Path
import tempfile
import unittest

from agy_skills.models import Scope
from agy_skills.state import (
    get_global_config_path,
    get_workspace_config_path,
    is_rule_enabled,
    is_skill_enabled,
    load_config_for_scope,
    read_config,
    save_config_for_scope,
    set_rule_enabled,
    set_skill_enabled,
    write_config,
)


class TestState(unittest.TestCase):
    def test_workspace_config_path_resolution(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            ws_root = Path(tmp_dir)

            # Case 1: Default to .agents/config.json when neither exists
            p1 = get_workspace_config_path(ws_root)
            self.assertEqual(p1, ws_root / ".agents" / "config.json")

            # Case 2: .gemini exists
            (ws_root / ".gemini").mkdir()
            p2 = get_workspace_config_path(ws_root)
            self.assertEqual(p2, ws_root / ".gemini" / "config.json")

            # Case 3: .agents exists (takes precedence)
            (ws_root / ".agents").mkdir()
            p3 = get_workspace_config_path(ws_root)
            self.assertEqual(p3, ws_root / ".agents" / "config.json")

    def test_read_missing_config_returns_empty_dict(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            p = Path(tmp_dir) / "config.json"
            data = read_config(p)
            self.assertEqual(data, {})

    def test_read_corrupt_config_raises_json_decode_error(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            p = Path(tmp_dir) / "config.json"
            p.write_text("{invalid json", encoding="utf-8")
            with self.assertRaises(json.JSONDecodeError):
                read_config(p)

    def test_read_directory_as_config_raises_io_error(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            p = Path(tmp_dir) / "dir_config"
            p.mkdir()
            with self.assertRaises(IOError):
                read_config(p)

    def test_atomic_write_and_read(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            p = Path(tmp_dir) / "nested" / "config.json"
            test_data = {
                "skills": {"test-skill": {"enabled": True}},
                "rules": {"GEMINI.md": {"enabled": False}},
            }
            write_config(p, test_data)
            self.assertTrue(p.is_file())

            loaded = read_config(p)
            self.assertEqual(loaded, test_data)

    def test_skill_and_rule_state_helpers(self):
        config = {}

        # Default is True
        self.assertTrue(is_skill_enabled(config, "sample-skill"))
        self.assertTrue(is_rule_enabled(config, "GEMINI.md"))

        # Disable
        set_skill_enabled(config, "sample-skill", False)
        set_rule_enabled(config, "GEMINI.md", False)

        self.assertFalse(is_skill_enabled(config, "sample-skill"))
        self.assertFalse(is_rule_enabled(config, "GEMINI.md"))
        self.assertEqual(config["skills"]["sample-skill"]["enabled"], False)
        self.assertEqual(config["rules"]["GEMINI.md"]["enabled"], False)

        # Re-enable
        set_skill_enabled(config, "sample-skill", True)
        set_rule_enabled(config, "GEMINI.md", True)
        self.assertTrue(is_skill_enabled(config, "sample-skill"))
        self.assertTrue(is_rule_enabled(config, "GEMINI.md"))

    def test_load_and_save_for_scope(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            home = root / "fake_home"
            home.mkdir()

            # Workspace save
            data = {"skills": {"my-skill": {"enabled": True}}}
            saved_p = save_config_for_scope(Scope.WORKSPACE, data, root, home)
            self.assertTrue(saved_p.is_file())

            _, loaded_ws = load_config_for_scope(Scope.WORKSPACE, root, home)
            self.assertEqual(loaded_ws, data)

            # Global save
            gl_data = {"rules": {"GEMINI.md": {"enabled": False}}}
            gl_p = save_config_for_scope(Scope.GLOBAL, gl_data, root, home)
            self.assertTrue(gl_p.is_file())

            _, loaded_gl = load_config_for_scope(Scope.GLOBAL, root, home)
            self.assertEqual(loaded_gl, gl_data)


if __name__ == "__main__":
    unittest.main()
