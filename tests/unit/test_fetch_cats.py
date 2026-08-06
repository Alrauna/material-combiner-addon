from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "smc_fetch_cats", ROOT / "tools" / "fetch_cats.py"
)
fetch_cats = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = fetch_cats
SPEC.loader.exec_module(fetch_cats)

REFERENCE = json.loads(
    (ROOT / "tools" / "cats_reference.json").read_text(encoding="utf-8")
)
MANIFEST = 'schema_version = "1.0.0"\nid = "cats_blender_plugin"\n'


def make_extension_zip(path: Path, extension_id: str = "cats_blender_plugin"):
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "blender_manifest.toml",
            f'schema_version = "1.0.0"\nid = "{extension_id}"\n',
        )
        archive.writestr("__init__.py", "")
    return path


def make_wrapper_zip(path: Path, inner_name: str, inner: Path) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        archive.write(inner, inner_name)
    return path


class UnwrapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_wrapper_archive_yields_inner_extension(self):
        inner = make_extension_zip(self.tmp / "cats_blender_plugin.zip")
        wrapper = make_wrapper_zip(
            self.tmp / "release-asset.zip", "cats_blender_plugin.zip", inner
        )
        out = self.tmp / "out"
        out.mkdir()
        result = fetch_cats.unwrap(wrapper, "cats_blender_plugin.zip", out)
        self.assertEqual("cats_blender_plugin.zip", result.name)
        self.assertEqual(
            "cats_blender_plugin", fetch_cats.extension_id_of(result)
        )

    def test_plain_extension_archive_is_passed_through(self):
        plain = make_extension_zip(self.tmp / "already-an-extension.zip")
        out = self.tmp / "out2"
        out.mkdir()
        result = fetch_cats.unwrap(plain, "cats_blender_plugin.zip", out)
        self.assertEqual(
            "cats_blender_plugin", fetch_cats.extension_id_of(result)
        )

    def test_unrelated_archive_is_rejected(self):
        junk = self.tmp / "junk.zip"
        with zipfile.ZipFile(junk, "w") as archive:
            archive.writestr("readme.txt", "nothing useful")
        out = self.tmp / "out3"
        out.mkdir()
        with self.assertRaises(RuntimeError):
            fetch_cats.unwrap(junk, "cats_blender_plugin.zip", out)


class DriftPolicyTests(unittest.TestCase):
    """Drift warns by default and fails under --strict."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.archive = make_extension_zip(self.tmp / "cats.zip")

    def test_hash_drift_warns_by_default(self):
        report, exit_code = fetch_cats.fetch(
            self.tmp / "o1", self.archive, strict=False
        )
        self.assertEqual(0, exit_code)
        self.assertTrue(report["drift"])
        self.assertFalse(report["drift_is_fatal"])

    def test_hash_drift_fails_under_strict(self):
        report, exit_code = fetch_cats.fetch(
            self.tmp / "o2", self.archive, strict=True
        )
        self.assertEqual(1, exit_code)
        self.assertTrue(report["drift_is_fatal"])

    def test_wrong_extension_id_always_fails(self):
        wrong = make_extension_zip(
            self.tmp / "wrong.zip", extension_id="something_else"
        )
        _, exit_code = fetch_cats.fetch(
            self.tmp / "o3", wrong, strict=False
        )
        self.assertEqual(1, exit_code)


class ReferenceFileTests(unittest.TestCase):
    def test_reference_records_both_hashes_and_the_extension_id(self):
        for key in (
            "repository",
            "release_tag",
            "asset_name",
            "asset_sha256",
            "extension_id",
            "extension_zip_name",
            "extension_sha256",
        ):
            self.assertIn(key, REFERENCE)
        for key in ("asset_sha256", "extension_sha256"):
            self.assertRegex(REFERENCE[key], r"\A[0-9a-f]{64}\Z")

    def test_default_policy_is_warn(self):
        self.assertFalse(fetch_cats.HASH_MISMATCH_IS_FATAL)


if __name__ == "__main__":
    unittest.main()
