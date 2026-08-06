from __future__ import annotations

import importlib
import json
import sys
import types
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
ADDON = ROOT / "addon"

# dependencies.py imports bpy and uses a relative import, so load it through a
# synthetic package with bpy stubbed out.
sys.modules.setdefault("bpy", types.ModuleType("bpy"))
_package = types.ModuleType("smc_dependency_platform_host")
_package.__path__ = [str(ADDON)]
sys.modules.setdefault("smc_dependency_platform_host", _package)
dependencies = importlib.import_module(
    "smc_dependency_platform_host.dependencies"
)

LOCK = json.loads(
    (ADDON / "dependencies.lock.json").read_text(encoding="utf-8")
)
MANIFEST = (ADDON / "blender_manifest.toml").read_text(encoding="utf-8")


class CurrentPlatformTests(unittest.TestCase):
    def test_supported_platforms_resolve(self):
        cases = [
            ("win32", "AMD64", "windows-x64"),
            ("win32", "x86_64", "windows-x64"),
            ("linux", "x86_64", "linux-x64"),
        ]
        for platform_name, machine, expected in cases:
            with self.subTest(platform=platform_name, machine=machine):
                with mock.patch.object(sys, "platform", platform_name), \
                        mock.patch.object(
                            dependencies.platform, "machine",
                            return_value=machine):
                    self.assertEqual(
                        expected, dependencies._current_platform()
                    )

    def test_unsupported_platform_and_architecture(self):
        cases = [("darwin", "arm64"), ("linux", "aarch64"), ("win32", "arm64")]
        for platform_name, machine in cases:
            with self.subTest(platform=platform_name, machine=machine):
                with mock.patch.object(sys, "platform", platform_name), \
                        mock.patch.object(
                            dependencies.platform, "machine",
                            return_value=machine):
                    self.assertIsNone(dependencies._current_platform())


class LockSelectionTests(unittest.TestCase):
    def test_lock_entry_selected_per_platform(self):
        for platform_name, machine, expected in [
            ("win32", "AMD64", "windows-x64"),
            ("linux", "x86_64", "linux-x64"),
        ]:
            with self.subTest(platform=expected):
                with mock.patch.object(sys, "platform", platform_name), \
                        mock.patch.object(
                            dependencies.platform, "machine",
                            return_value=machine):
                    dependency, error = dependencies._load_lock()
                self.assertIsNone(error)
                self.assertEqual(expected, dependency["platform"])

    def test_unsupported_platform_reports_no_dependency(self):
        with mock.patch.object(sys, "platform", "darwin"), \
                mock.patch.object(
                    dependencies.platform, "machine", return_value="arm64"):
            dependency, error = dependencies._load_lock()
        self.assertIsNone(dependency)
        self.assertIn("No bundled dependency", error)


class LockManifestAgreementTests(unittest.TestCase):
    """Every declared platform must ship exactly one reviewed wheel."""

    def test_lock_platforms_are_unique(self):
        platforms = [entry["platform"] for entry in LOCK["dependencies"]]
        self.assertEqual(sorted(platforms), sorted(set(platforms)))

    def test_lock_platforms_match_manifest(self):
        declared = {
            name
            for name in ("windows-x64", "linux-x64", "macos-arm64")
            if f'"{name}"' in MANIFEST
        }
        locked = {entry["platform"] for entry in LOCK["dependencies"]}
        self.assertEqual(declared, locked)

    def test_every_locked_wheel_exists_and_is_referenced(self):
        for entry in LOCK["dependencies"]:
            with self.subTest(platform=entry["platform"]):
                wheel = ADDON / entry["wheel"]
                self.assertTrue(wheel.is_file(), wheel)
                self.assertIn(wheel.name, MANIFEST)


if __name__ == "__main__":
    unittest.main()
