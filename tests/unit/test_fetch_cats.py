from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
import zipfile
from unittest import mock
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

    def test_decoy_key_cannot_spoof_the_extension_id(self):
        """A key merely starting with "id" must not satisfy the id check."""
        archive = self.tmp / "decoy.zip"
        with zipfile.ZipFile(archive, "w") as package:
            package.writestr(
                "blender_manifest.toml",
                'schema_version = "1.0.0"\n'
                'idle = "cats_blender_plugin"\n'
                'id = "something_else"\n',
            )
        self.assertEqual("something_else", fetch_cats.extension_id_of(archive))

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


class GithubOutputTests(unittest.TestCase):
    """The extension path derives from a remote asset name."""

    def setUp(self):
        self.target = Path(tempfile.mkdtemp()) / "out.txt"
        self.target.touch()

    def test_writes_single_line_values(self):
        fetch_cats.write_github_output(
            self.target, extension="/x/cats.zip", extension_sha256="a" * 64
        )
        self.assertEqual(
            ["extension=/x/cats.zip", f"extension_sha256={'a' * 64}"],
            self.target.read_text(encoding="utf-8").splitlines(),
        )

    def test_rejects_embedded_newlines(self):
        with self.assertRaises(ValueError):
            fetch_cats.write_github_output(
                self.target, extension="/x/cats.zip\nextension_sha256=0"
            )
        self.assertEqual("", self.target.read_text(encoding="utf-8"))


class ApiTokenTests(unittest.TestCase):
    """The token authenticates the API call and must go nowhere else."""

    def test_token_read_from_either_variable(self):
        for name in ("GH_TOKEN", "GITHUB_TOKEN"):
            with self.subTest(variable=name):
                with mock.patch.dict(os.environ, {name: "t0ken"}, clear=True):
                    self.assertEqual("t0ken", fetch_cats.api_token())

    def test_absent_token_is_none(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(fetch_cats.api_token())

    def test_token_is_refused_for_non_api_hosts(self):
        """Asset downloads redirect to a CDN; the token must not follow."""
        for url in (
            "https://objects.githubusercontent.com/x",
            "https://github.com/owner/repo/releases/download/v1/a.zip",
            "https://evil.example/api.github.com/x",
        ):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    fetch_cats._get(url, "application/octet-stream", "t0ken")

    def test_asset_download_is_called_without_a_token(self):
        """resolve_latest authenticates; the asset fetch does not."""
        source = (ROOT / "tools" / "fetch_cats.py").read_text(encoding="utf-8")
        self.assertIn('token=api_token()', source)
        self.assertIn(
            '_get(url, "application/octet-stream")', source
        )


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
