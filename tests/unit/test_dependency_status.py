from __future__ import annotations

import importlib.util
import sys
import unittest
from dataclasses import replace
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "dependency_status.py"
SPEC = importlib.util.spec_from_file_location("smc_dependency_status", MODULE_PATH)
dependency_status = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = dependency_status
SPEC.loader.exec_module(dependency_status)


class DependencyStatusTests(unittest.TestCase):
    def setUp(self):
        self.healthy = dependency_status.DependencyFacts()

    def assert_category(self, expected, **changes):
        facts = replace(self.healthy, **changes)
        category, _ = dependency_status.classify_dependency(facts)
        self.assertEqual(expected, category)

    def test_all_dependency_categories(self):
        cases = [
            (dependency_status.HEALTHY, {}),
            (
                dependency_status.PILLOW_ABSENT,
                {"pillow_present": False},
            ),
            (
                dependency_status.WHEEL_MISSING,
                {"wheel_present": False},
            ),
            (
                dependency_status.WRONG_PLATFORM,
                {"platform_supported": False},
            ),
            (
                dependency_status.ABI_MISMATCH,
                {"abi_supported": False},
            ),
            (
                dependency_status.NATIVE_IMPORT_FAILED,
                {"native_imported": False},
            ),
            (
                dependency_status.COMPONENT_VERSION_MISMATCH,
                {"versions_match": False},
            ),
            (
                dependency_status.FILES_CORRUPT_OR_INCOMPLETE,
                {"files_complete": False},
            ),
            (
                dependency_status.DEPENDENCY_CONFLICT,
                {"dependency_path_trusted": False},
            ),
            (
                dependency_status.UNSUPPORTED_SOURCE_LAYOUT,
                {"source_layout_supported": False},
            ),
            (
                dependency_status.APPROVED_DEVELOPER_PATH,
                {"developer_path_approved": True},
            ),
            (
                dependency_status.NATIVE_RESTART_REQUIRED,
                {"restart_required": True},
            ),
            (
                dependency_status.STALE_NATIVE_AFTER_UPDATE,
                {"stale_native_loaded": True},
            ),
        ]
        for expected, changes in cases:
            with self.subTest(expected=expected):
                self.assert_category(expected, **changes)

    def test_cats_unavailable_preserves_cause(self):
        category, cause = dependency_status.classify_dependency(
            replace(
                self.healthy,
                pillow_present=False,
                cats_invocation=True,
            )
        )
        self.assertEqual(
            dependency_status.CATS_DEPENDENCY_UNAVAILABLE,
            category,
        )
        self.assertEqual(dependency_status.PILLOW_ABSENT, cause)

    def test_sanitized_status_omits_parent_directories(self):
        status = dependency_status.DependencyStatus(
            category=dependency_status.HEALTHY,
            healthy=True,
            summary="ok",
            recovery="none",
            expected_version="12.3.0",
            detected_version="12.3.0",
            native_version="12.3.0",
            blender_version="5.2.0 LTS",
            python_version="3.13.13",
            python_abi="cpython-313",
            operating_system="Windows",
            architecture="AMD64",
            expected_platform="windows-x64",
            paths={"PIL": r"C:\Users\Example\PIL\__init__.py"},
        )
        self.assertEqual(
            {"PIL": "__init__.py"},
            status.as_dict(include_paths=False)["paths"],
        )


if __name__ == "__main__":
    unittest.main()
