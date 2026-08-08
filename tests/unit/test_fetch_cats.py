from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

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


class FakeResponse:
    def __init__(self, data: bytes, url: str = "https://example.test/file"):
        self._stream = io.BytesIO(data)
        self.status = 200
        self.url = url

    def read(self, size=-1):
        return self._stream.read(size)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def make_extension_zip(
    path: Path,
    extension_id: str = "cats_blender_plugin",
    version: str = REFERENCE["extension_version"],
):
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "blender_manifest.toml",
            'schema_version = "1.0.0"\n'
            f'id = "{extension_id}"\n'
            f'version = "{version}"\n',
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

    def test_inner_zip_member_over_limit_is_rejected(self):
        inner = self.tmp / "inner.zip"
        inner.write_bytes(b"x" * 17)
        wrapper = make_wrapper_zip(self.tmp / "wrapper.zip", "cats.zip", inner)
        out = self.tmp / "bounded"
        out.mkdir()
        with mock.patch.object(
            fetch_cats, "EXTENSION_MAX_BYTES", 16, create=True
        ):
            with self.assertRaisesRegex(
                RuntimeError, "extension archive exceeds"
            ):
                fetch_cats.unwrap(wrapper, "cats.zip", out)


class BoundedInputTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_api_response_over_limit_is_rejected(self):
        response = FakeResponse(b"x" * (1 * 1024 * 1024 + 1))
        with mock.patch.object(
            fetch_cats.urllib.request, "urlopen", return_value=response
        ):
            with self.assertRaisesRegex(RuntimeError, "API response exceeds"):
                fetch_cats._get(
                    "https://api.github.com/x", "application/json"
                )

    def test_download_over_limit_removes_partial_file(self):
        target = self.tmp / "asset.zip"
        response = FakeResponse(b"x" * 17)
        with mock.patch.object(
            fetch_cats.urllib.request, "urlopen", return_value=response
        ):
            with self.assertRaisesRegex(
                RuntimeError, "release asset exceeds"
            ):
                fetch_cats._download(
                    "https://example.test/asset.zip", target, maximum=16
                )
        self.assertFalse(target.exists())


class DriftPolicyTests(unittest.TestCase):
    """Drift fails by default and requires an explicit local override."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.archive = make_extension_zip(self.tmp / "cats.zip")

    def test_hash_drift_fails_by_default(self):
        report, exit_code = fetch_cats.fetch(self.tmp / "o1", self.archive)
        self.assertEqual(1, exit_code)
        self.assertTrue(report["drift"])
        self.assertTrue(report["drift_is_fatal"])

    def test_hash_drift_requires_explicit_allowance(self):
        report, exit_code = fetch_cats.fetch(
            self.tmp / "o2", self.archive, allow_drift=True
        )
        self.assertEqual(0, exit_code)
        self.assertTrue(report["drift"])
        self.assertFalse(report["drift_is_fatal"])

    def test_wrong_extension_id_always_fails(self):
        wrong = make_extension_zip(
            self.tmp / "wrong.zip", extension_id="something_else"
        )
        _, exit_code = fetch_cats.fetch(
            self.tmp / "o3", wrong, allow_drift=True
        )
        self.assertEqual(1, exit_code)


class IntegrityFactsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.inner = make_extension_zip(self.tmp / "cats_blender_plugin.zip")
        self.wrapper = make_wrapper_zip(
            self.tmp / "release.zip", self.inner.name, self.inner
        )
        self.reference = {
            **REFERENCE,
            "release_tag": "test-release",
            "asset_name": self.wrapper.name,
            "asset_sha256": hashlib.sha256(
                self.wrapper.read_bytes()
            ).hexdigest(),
            "asset_size": self.wrapper.stat().st_size,
            "extension_sha256": hashlib.sha256(
                self.inner.read_bytes()
            ).hexdigest(),
            "extension_size": self.inner.stat().st_size,
            "extension_version": REFERENCE["extension_version"],
        }
        self.reference_path = self.tmp / "reference.json"

    def fetch_local(self, *, allow_drift=False, **changes):
        reference = {**self.reference, **changes}
        self.reference_path.write_text(json.dumps(reference), encoding="utf-8")
        with mock.patch.object(
            fetch_cats, "REFERENCE_PATH", self.reference_path
        ):
            return fetch_cats.fetch(
                self.tmp / "local-output",
                self.inner,
                allow_drift=allow_drift,
            )

    def test_exact_extension_size_and_version_pass(self):
        report, exit_code = self.fetch_local()
        self.assertEqual(0, exit_code)
        self.assertEqual(self.inner.stat().st_size, report["extension_size"])
        self.assertEqual(
            REFERENCE["extension_version"], report["extension_version"]
        )

    def test_extension_size_drift_fails_by_default(self):
        report, exit_code = self.fetch_local(
            extension_size=self.inner.stat().st_size + 1
        )
        self.assertEqual(1, exit_code)
        self.assertTrue(
            any("extension size changed" in item for item in report["drift"])
        )

    def test_extension_size_drift_requires_explicit_allowance(self):
        report, exit_code = self.fetch_local(
            allow_drift=True,
            extension_size=self.inner.stat().st_size + 1,
        )
        self.assertEqual(0, exit_code)
        self.assertFalse(report["drift_is_fatal"])

    def test_extension_version_drift_fails_by_default(self):
        report, exit_code = self.fetch_local(extension_version="0.0.0")
        self.assertEqual(1, exit_code)
        self.assertTrue(
            any(
                "extension version changed" in item
                for item in report["drift"]
            )
        )

    def test_published_and_downloaded_asset_sizes_are_verified(self):
        asset = self.wrapper.read_bytes()
        published_size = len(asset) + 1
        reference = {**self.reference, "asset_size": published_size}
        self.reference_path.write_text(json.dumps(reference), encoding="utf-8")
        api_payload = json.dumps(
            {
                "tag_name": reference["release_tag"],
                "assets": [
                    {
                        "name": reference["asset_name"],
                        "browser_download_url": "https://cdn.example/release.zip",
                        "size": published_size,
                    }
                ],
            }
        ).encode()
        responses = iter(
            (
                FakeResponse(api_payload, "https://api.github.com/release"),
                FakeResponse(asset, "https://cdn.example/release.zip"),
            )
        )
        with mock.patch.object(
            fetch_cats, "REFERENCE_PATH", self.reference_path
        ):
            with mock.patch.object(
                fetch_cats.urllib.request,
                "urlopen",
                side_effect=lambda *_args, **_kwargs: next(responses),
            ):
                report, exit_code = fetch_cats.fetch(
                    self.tmp / "remote-output", None
                )

        self.assertEqual(1, exit_code)
        self.assertEqual(len(asset), report["asset_size"])
        self.assertTrue(
            any(
                "downloaded asset size changed" in item
                for item in report["drift"]
            )
        )
        self.assertTrue(report["drift"])
        self.assertTrue(report["drift_is_fatal"])

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

    def test_asset_download_streams_without_forwarding_api_token(self):
        """A large asset bypasses the API cap and never receives the token."""
        tmp = Path(tempfile.mkdtemp())
        inner = tmp / "cats_blender_plugin.zip"
        with zipfile.ZipFile(inner, "w") as package:
            package.writestr("blender_manifest.toml", MANIFEST)
            package.writestr("payload.bin", os.urandom(1 * 1024 * 1024 + 1))
        wrapper = make_wrapper_zip(tmp / "release.zip", inner.name, inner)
        asset = wrapper.read_bytes()
        api_payload = json.dumps(
            {
                "tag_name": "test-release",
                "assets": [
                    {
                        "name": "release.zip",
                        "browser_download_url": "https://cdn.example/release.zip",
                        "size": len(asset),
                    }
                ],
            }
        ).encode()
        requests = []

        def open_request(request, timeout):
            self.assertEqual(fetch_cats.TIMEOUT_SECONDS, timeout)
            requests.append(request)
            if request.full_url.startswith("https://api.github.com/"):
                return FakeResponse(api_payload, request.full_url)
            return FakeResponse(asset, request.full_url)

        with mock.patch.dict(os.environ, {"GH_TOKEN": "t0ken"}, clear=True):
            with mock.patch.object(
                fetch_cats.urllib.request,
                "urlopen",
                side_effect=open_request,
            ):
                _, exit_code = fetch_cats.fetch(
                    tmp / "out", None, allow_drift=True
                )

        self.assertEqual(0, exit_code)
        self.assertEqual("Bearer t0ken", requests[0].get_header("Authorization"))
        self.assertIsNone(requests[1].get_header("Authorization"))


class ReferenceFileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.archive = make_extension_zip(self.tmp / "cats.zip")

    def test_reference_records_integrity_facts(self):
        for key in (
            "repository",
            "release_tag",
            "asset_name",
            "asset_sha256",
            "asset_size",
            "extension_id",
            "extension_zip_name",
            "extension_sha256",
            "extension_size",
            "extension_version",
        ):
            self.assertIn(key, REFERENCE)
        for key in ("asset_sha256", "extension_sha256"):
            self.assertRegex(REFERENCE[key], r"\A[0-9a-f]{64}\Z")
        for key in ("asset_size", "extension_size"):
            self.assertIsInstance(REFERENCE[key], int)
            self.assertGreater(REFERENCE[key], 0)

    def test_legacy_strict_flag_is_still_accepted(self):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(
                1,
                fetch_cats.main(
                    [
                        "--output-dir",
                        str(self.tmp / "strict"),
                        "--archive",
                        str(self.archive),
                        "--strict",
                    ]
                ),
            )

    def test_conflicting_policy_flags_are_rejected(self):
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                fetch_cats.main(
                    [
                        "--output-dir",
                        str(self.tmp / "conflict"),
                        "--archive",
                        str(self.archive),
                        "--strict",
                        "--allow-drift",
                    ]
                )

if __name__ == "__main__":
    unittest.main()
