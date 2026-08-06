from __future__ import annotations

import importlib.util
import os
import sys
import unittest
import unittest.mock
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


class LongPathTests(unittest.TestCase):
    """Padding must land inside the defect window, not past it.

    Path.resolve() keeps the \\\\?\\ prefix only when its result exceeds
    MAX_PATH. If the extension root itself goes past 260 then every path is
    prefixed, they all agree, and the dependency-trust regression passes even
    with the fix reverted. Verified by reverting the fix: the run fails only
    while the extension root stays under 260.
    """

    def _extension_length(self, work: Path) -> int:
        padded = run_tests.pad_to_long_path(work)
        profile = run_tests.Profile(padded, None)
        return len(str(profile.extension_dir))

    def test_padding_lands_below_max_path(self):
        for base in (r"C:\w", r"C:\Users\User\AppData\Local\Temp\smc\lp"):
            with self.subTest(base=base):
                length = self._extension_length(Path(base))
                self.assertLess(length, 260)
                self.assertGreaterEqual(length, 235)

    def test_files_inside_the_profile_exceed_max_path(self):
        padded = run_tests.pad_to_long_path(Path(r"C:\w"))
        profile = run_tests.Profile(padded, None)
        lock = profile.extension_dir / "dependencies.lock.json"
        native = (
            profile.root
            / "extensions"
            / ".local"
            / "lib"
            / "python3.13"
            / "site-packages"
            / "PIL"
            / "_imaging.cp313-win_amd64.pyd"
        )
        self.assertGreater(len(str(lock)), 260)
        self.assertGreater(len(str(native)), 260)

    def test_padding_is_skipped_when_already_long(self):
        work = Path("C:/" + "x" * 300)
        self.assertEqual(work, run_tests.pad_to_long_path(work))


class DisplayPrefixTests(unittest.TestCase):
    """Foreground mode must never silently degrade to a skipped check."""

    def test_no_prefix_when_not_foreground(self):
        self.assertEqual([], run_tests.display_prefix(False))

    @unittest.skipIf(os.name == "nt", "POSIX display handling")
    def test_existing_display_needs_no_wrapper(self):
        with unittest.mock.patch.dict(os.environ, {"DISPLAY": ":0"}):
            self.assertEqual([], run_tests.display_prefix(True))

    @unittest.skipIf(os.name == "nt", "POSIX display handling")
    def test_headless_uses_xvfb_when_available(self):
        with unittest.mock.patch.dict(os.environ, {}, clear=True), \
                unittest.mock.patch.object(
                    run_tests.shutil, "which", return_value="/usr/bin/xvfb-run"
                ):
            prefix = run_tests.display_prefix(True)
        self.assertEqual("/usr/bin/xvfb-run", prefix[0])
        self.assertIn("-a", prefix)

    @unittest.skipIf(os.name == "nt", "POSIX display handling")
    def test_headless_without_xvfb_refuses_rather_than_skipping(self):
        with unittest.mock.patch.dict(os.environ, {}, clear=True), \
                unittest.mock.patch.object(
                    run_tests.shutil, "which", return_value=None
                ):
            with self.assertRaises(SystemExit):
                run_tests.display_prefix(True)


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
