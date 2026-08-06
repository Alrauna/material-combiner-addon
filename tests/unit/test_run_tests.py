from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "smc_run_tests", ROOT / "tests" / "run_tests.py"
)
run_tests = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = run_tests
SPEC.loader.exec_module(run_tests)


class ProfileIsolationTests(unittest.TestCase):
    """Every redirected path must stay inside the work directory."""

    def setUp(self):
        self.profile = run_tests.Profile(Path("work").resolve(), None)
        self.profile.runtime = self.profile.root

    def test_all_redirected_paths_are_inside_the_profile(self):
        env = self.profile.environment()
        redirected = [
            "BLENDER_USER_CONFIG",
            "BLENDER_USER_SCRIPTS",
            "BLENDER_USER_DATAFILES",
            "BLENDER_USER_EXTENSIONS",
            "HOME",
            "USERPROFILE",
            "APPDATA",
            "LOCALAPPDATA",
            "XDG_CACHE_HOME",
            "TEMP",
            "TMP",
            "TMPDIR",
        ]
        for key in redirected:
            with self.subTest(variable=key):
                self.assertIn(key, env)
                value = Path(env[key]).resolve()
                self.assertTrue(
                    value == self.profile.root
                    or self.profile.root in value.parents,
                    f"{key} escaped the profile: {value}",
                )

    def test_user_site_disabled_and_pythonpath_dropped(self):
        os.environ["PYTHONPATH"] = "/should/not/leak"
        try:
            env = self.profile.environment()
        finally:
            os.environ.pop("PYTHONPATH", None)
        self.assertEqual("1", env["PYTHONNOUSERSITE"])
        self.assertNotIn("PYTHONPATH", env)

    def test_contract_points_at_the_repository(self):
        env = self.profile.environment()
        self.assertTrue(Path(env["SMC_TEST_CONTRACT"]).is_file())

    def test_drive_alias_is_windows_only(self):
        profile = run_tests.Profile(Path("work").resolve(), "Q")
        expected = "Q" if os.name == "nt" else None
        self.assertEqual(expected, profile._drive)


class CatsHashGuardTests(unittest.TestCase):
    def test_mismatched_cats_hash_refuses_to_run(self):
        import argparse
        import contextlib
        import io

        args = argparse.Namespace(
            blender=Path("blender"),
            work=Path("work"),
            drive_letter=None,
            package=Path("package.zip"),
            cats=ROOT / "tests" / "run_tests.py",  # any real file
            cats_sha256="0" * 64,
        )
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            exit_code = run_tests.command_checkpoint(args)
        self.assertEqual(1, exit_code)
        self.assertIn("CATS reference hash mismatch", stream.getvalue())


if __name__ == "__main__":
    unittest.main()
