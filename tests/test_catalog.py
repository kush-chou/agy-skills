"""Unit tests for catalog search, verification, and turnkey installation."""

from pathlib import Path
import tempfile
import unittest

from agy_skills.catalog import (
    CURATED_CATALOG,
    check_installed_status,
    install_catalog_pack,
    search_catalog,
)
from agy_skills.models import Skill


class TestCatalog(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.workspace_root = Path(self.tmp_dir.name)
        self.home_dir = self.workspace_root / "fake_home"
        self.home_dir.mkdir(parents=True)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_search_catalog_empty_and_matching(self):
        # Empty query should return full catalog
        all_packs = search_catalog("")
        self.assertEqual(len(all_packs), len(CURATED_CATALOG))
        self.assertGreater(len(all_packs), 10)

        # Match specific pack
        results = search_catalog("superpowers")
        self.assertTrue(any(p.name == "superpowers" for p in results))

        # Match by category / keyword
        results_db = search_catalog("supabase")
        self.assertTrue(any("supabase" in p.name for p in results_db))

        # Non-matching
        no_results = search_catalog("xyz-absolutely-unknown-pack-999")
        self.assertEqual(len(no_results), 0)

    def test_install_catalog_pack(self):
        target_dir = self.workspace_root / ".agents" / "skills"
        target_dir.mkdir(parents=True)

        success, msg = install_catalog_pack("superpowers", target_dir, "workspace")
        self.assertTrue(success)
        self.assertIn("Successfully installed", msg)

        installed_dir = target_dir / "superpowers"
        self.assertTrue(installed_dir.is_dir())
        skill_file = installed_dir / "SKILL.md"
        self.assertTrue(skill_file.is_file())

        # Verify parsed skill from installed directory
        skill = Skill.from_directory(installed_dir, scope=None)
        self.assertIsNotNone(skill)
        self.assertEqual(skill.name, "superpowers")

    def test_check_installed_status(self):
        target_dir = self.workspace_root / ".agents" / "skills"
        target_dir.mkdir(parents=True)

        # Before installation
        check_installed_status(self.workspace_root, self.home_dir)
        pack = next(p for p in CURATED_CATALOG if p.name == "superpowers")

        # Install
        install_catalog_pack("superpowers", target_dir, "workspace")
        check_installed_status(self.workspace_root, self.home_dir)
        self.assertTrue(pack.is_installed)
        self.assertEqual(pack.install_path, target_dir / "superpowers")

    def test_install_unknown_pack(self):
        target_dir = self.workspace_root / ".agents" / "skills"
        success, msg = install_catalog_pack("totally-invalid-pack-name", target_dir, "workspace")
        self.assertFalse(success)
        self.assertIn("Unknown skill pack", msg)


if __name__ == "__main__":
    unittest.main()
