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
TEST_VERSION = "99.4.7"


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
    version: str = TEST_VERSION,
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


class ReleaseMetadataTests(unittest.TestCase):
    def payload(self, **changes):
        payload = {
            "tag_name": "v99.4.7",
            "draft": False,
            "prerelease": False,
            "target_commitish": "a" * 40,
            "assets": [
                {
                    "name": "cats_blender_plugin-99.4.7.zip",
                    "browser_download_url": "https://example.test/cats.zip",
                    "size": 123,
                }
            ],
        }
        payload.update(changes)
        return json.dumps(payload).encode()

    def resolve(self, **changes):
        with mock.patch.object(
            fetch_cats, "_get", return_value=self.payload(**changes)
        ):
            return fetch_cats.resolve_latest(REFERENCE["repository"])

    def test_latest_release_returns_dynamic_source_commit(self):
        self.assertEqual(
            (
                "v99.4.7",
                "cats_blender_plugin-99.4.7.zip",
                "https://example.test/cats.zip",
                123,
                "a" * 40,
            ),
            self.resolve(),
        )

    def test_draft_and_prerelease_metadata_are_rejected(self):
        for changes in ({"draft": True}, {"prerelease": True}):
            with self.subTest(changes=changes):
                with self.assertRaises(RuntimeError):
                    self.resolve(**changes)

    def test_release_target_must_be_an_exact_commit(self):
        for target in ("main", "a" * 39, "g" * 40, None):
            with self.subTest(target=target):
                with self.assertRaisesRegex(RuntimeError, "exact commit"):
                    self.resolve(target_commitish=target)

    def test_release_requires_exactly_one_zip_asset(self):
        zip_asset = {
            "name": "cats.zip",
            "browser_download_url": "https://example.test/cats.zip",
            "size": 123,
        }
        for assets in ([], [zip_asset, dict(zip_asset)]):
            with self.subTest(count=len(assets)):
                with self.assertRaisesRegex(RuntimeError, "exactly one ZIP"):
                    self.resolve(assets=assets)


class AttestationTests(unittest.TestCase):
    def setUp(self):
        self.archive = Path(tempfile.mkdtemp()) / "cats.zip"
        self.archive.write_bytes(b"attested bytes")

    def test_verifier_constrains_every_approved_identity(self):
        self.assertTrue(hasattr(fetch_cats, "verify_attestation"))
        completed = mock.Mock()
        with mock.patch.object(
            fetch_cats.shutil, "which", return_value="/usr/bin/gh"
        ):
            with mock.patch.object(
                fetch_cats.subprocess, "run", return_value=completed
            ) as run:
                fetch_cats.verify_attestation(
                    self.archive,
                    repository="Alrauna/Cats-Blender-Plugin",
                    certificate_identity=(
                        "https://github.com/Alrauna/Cats-Blender-Plugin/"
                        ".github/workflows/Cats%20Tests.yml@refs/heads/main"
                    ),
                    source_ref="refs/heads/main",
                    source_digest="a" * 40,
                )

        run.assert_called_once_with(
            [
                "/usr/bin/gh",
                "attestation",
                "verify",
                str(self.archive),
                "--repo",
                "Alrauna/Cats-Blender-Plugin",
                "--cert-identity",
                (
                    "https://github.com/Alrauna/Cats-Blender-Plugin/"
                    ".github/workflows/Cats%20Tests.yml@refs/heads/main"
                ),
                "--source-ref",
                "refs/heads/main",
                "--source-digest",
                "a" * 40,
                "--deny-self-hosted-runners",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=fetch_cats.ATTESTATION_TIMEOUT_SECONDS,
        )

    def test_missing_github_cli_fails_closed(self):
        with mock.patch.object(fetch_cats.shutil, "which", return_value=None):
            with mock.patch.object(fetch_cats.subprocess, "run") as run:
                with self.assertRaisesRegex(RuntimeError, "GitHub CLI"):
                    fetch_cats.verify_attestation(
                        self.archive,
                        repository="Alrauna/Cats-Blender-Plugin",
                        certificate_identity="https://example.test/workflow.yml",
                        source_ref="refs/heads/main",
                        source_digest="a" * 40,
                    )
        run.assert_not_called()

    def test_verification_failure_is_wrapped_without_process_output(self):
        failure = fetch_cats.subprocess.CalledProcessError(
            1,
            ["gh", "attestation", "verify"],
            output="sensitive stdout",
            stderr="sensitive stderr",
        )
        with mock.patch.object(
            fetch_cats.shutil, "which", return_value="/usr/bin/gh"
        ):
            with mock.patch.object(
                fetch_cats.subprocess, "run", side_effect=failure
            ):
                try:
                    fetch_cats.verify_attestation(
                        self.archive,
                        repository="Alrauna/Cats-Blender-Plugin",
                        certificate_identity="https://example.test/workflow.yml",
                        source_ref="refs/heads/main",
                        source_digest="a" * 40,
                    )
                except Exception as error:
                    self.assertIs(type(error), RuntimeError)
                    self.assertEqual(
                        "CATS build-provenance verification failed", str(error)
                    )
                    self.assertNotIn("sensitive", str(error))
                else:
                    self.fail("verification failure was accepted")


class DynamicIdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.archive = make_extension_zip(
            self.tmp / "cats_blender_plugin-99.4.7.zip",
            version="99.4.7",
        )

    def remote_fetch(
        self,
        *,
        tag="v99.4.7",
        asset_name="cats_blender_plugin-99.4.7.zip",
        archive=None,
        allow_drift=False,
        verifier=None,
    ):
        source = archive or self.archive

        def download(_url, output, maximum=fetch_cats.ASSET_MAX_BYTES):
            del maximum
            output.write_bytes(source.read_bytes())
            return output.stat().st_size

        verifier = verifier or mock.Mock()
        with mock.patch.object(
            fetch_cats,
            "resolve_latest",
            return_value=(
                tag,
                asset_name,
                "https://example.test/cats.zip",
                source.stat().st_size,
                "a" * 40,
            ),
        ):
            with mock.patch.object(fetch_cats, "_download", side_effect=download):
                with mock.patch.object(
                    fetch_cats, "verify_attestation", side_effect=verifier
                ):
                    return fetch_cats.fetch(
                        self.tmp / f"out-{len(list(self.tmp.iterdir()))}",
                        None,
                        allow_drift=allow_drift,
                    )

    def test_arbitrary_future_version_passes_without_policy_update(self):
        try:
            report, exit_code = self.remote_fetch()
        except Exception as error:
            self.fail(f"future attested release was not accepted: {error}")
        self.assertEqual(0, exit_code)
        self.assertEqual("99.4.7", report["extension_version"])
        self.assertTrue(report["attestation_verified"])

    def test_attestation_failure_happens_before_untrusted_zip_parsing(self):
        untrusted = self.tmp / "untrusted.zip"
        untrusted.write_bytes(b"not a zip")

        def reject(*_args, **_kwargs):
            raise RuntimeError("untrusted provenance")

        with self.assertRaisesRegex(RuntimeError, "untrusted provenance"):
            self.remote_fetch(archive=untrusted, verifier=reject)

    def test_allow_drift_cannot_bypass_attestation_failure(self):
        def reject(*_args, **_kwargs):
            raise RuntimeError("untrusted provenance")

        with self.assertRaisesRegex(RuntimeError, "untrusted provenance"):
            self.remote_fetch(allow_drift=True, verifier=reject)

    def test_manifest_tag_and_asset_versions_must_agree(self):
        for changes in (
            {"tag": "v99.4.8"},
            {"asset_name": "cats_blender_plugin-99.4.8.zip"},
        ):
            with self.subTest(changes=changes):
                _, exit_code = self.remote_fetch(**changes)
                self.assertEqual(1, exit_code)

    def test_remote_manifest_requires_a_nonempty_string_version(self):
        missing = make_extension_zip(self.tmp / "missing.zip", version="")
        non_string = self.tmp / "non-string.zip"
        with zipfile.ZipFile(non_string, "w") as package:
            package.writestr(
                "blender_manifest.toml",
                MANIFEST + "version = 7\n",
            )
        for archive in (missing, non_string):
            with self.subTest(archive=archive.name):
                report, exit_code = self.remote_fetch(archive=archive)
                self.assertEqual(1, exit_code)
                self.assertTrue(
                    any("valid version" in item for item in report["drift"])
                )

    def test_wrong_extension_id_always_fails(self):
        wrong = make_extension_zip(
            self.tmp / "wrong.zip",
            extension_id="something_else",
            version="99.4.7",
        )
        _, exit_code = self.remote_fetch(archive=wrong)
        self.assertEqual(1, exit_code)


class LocalArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.archive = make_extension_zip(self.tmp / "cats.zip")

    def test_explicit_local_archive_is_inspected_without_provenance_claim(self):
        try:
            report, exit_code = fetch_cats.fetch(self.tmp / "out", self.archive)
        except Exception as error:
            self.fail(f"explicit local archive could not be inspected: {error}")
        self.assertEqual(0, exit_code)
        self.assertFalse(report["attestation_verified"])
        self.assertEqual("cats_blender_plugin", report["extension_id"])


class DriftPolicyTests(unittest.TestCase):
    """Local files retain integrity facts without becoming trust pins."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.archive = make_extension_zip(self.tmp / "cats.zip")

    def test_local_hash_is_reported_without_being_a_trust_pin(self):
        report, exit_code = fetch_cats.fetch(self.tmp / "o1", self.archive)
        self.assertEqual(0, exit_code)
        self.assertEqual(
            hashlib.sha256(self.archive.read_bytes()).hexdigest(),
            report["extension_sha256"],
        )
        self.assertFalse(report["drift"])
        self.assertTrue(report["drift_is_fatal"])

    def test_allow_drift_does_not_change_local_integrity_facts(self):
        report, exit_code = fetch_cats.fetch(
            self.tmp / "o2", self.archive, allow_drift=True
        )
        self.assertEqual(0, exit_code)
        self.assertEqual(
            hashlib.sha256(self.archive.read_bytes()).hexdigest(),
            report["extension_sha256"],
        )
        self.assertFalse(report["attestation_verified"])

    def test_wrong_extension_id_always_fails(self):
        wrong = make_extension_zip(
            self.tmp / "wrong.zip", extension_id="something_else"
        )
        _, exit_code = fetch_cats.fetch(
            self.tmp / "o3", wrong, allow_drift=True
        )
        self.assertEqual(1, exit_code)


class DynamicIntegrityFactsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.inner = make_extension_zip(self.tmp / "cats_blender_plugin.zip")
        self.wrapper = make_wrapper_zip(
            self.tmp / "release.zip", self.inner.name, self.inner
        )

    def test_extension_size_hash_and_version_are_reported(self):
        report, exit_code = fetch_cats.fetch(
            self.tmp / "local-output", self.inner
        )
        self.assertEqual(0, exit_code)
        self.assertEqual(self.inner.stat().st_size, report["extension_size"])
        self.assertEqual(
            hashlib.sha256(self.inner.read_bytes()).hexdigest(),
            report["extension_sha256"],
        )
        self.assertEqual(TEST_VERSION, report["extension_version"])

    def remote_fetch(self, *, published_size, allow_drift=False):
        asset = self.wrapper.read_bytes()
        with mock.patch.object(
            fetch_cats,
            "resolve_latest",
            return_value=(
                f"v{TEST_VERSION}",
                f"cats_blender_plugin-{TEST_VERSION}.zip",
                "https://cdn.example/release.zip",
                published_size,
                "a" * 40,
            ),
        ):
            with mock.patch.object(fetch_cats, "_download") as download:
                download.side_effect = lambda _url, path: path.write_bytes(asset)
                with mock.patch.object(fetch_cats, "verify_attestation"):
                    return fetch_cats.fetch(
                        self.tmp / f"remote-{allow_drift}",
                        None,
                        allow_drift=allow_drift,
                    )

    def test_published_and_downloaded_asset_sizes_are_verified(self):
        asset_size = self.wrapper.stat().st_size
        report, exit_code = self.remote_fetch(published_size=asset_size + 1)

        self.assertEqual(1, exit_code)
        self.assertEqual(asset_size, report["asset_size"])
        self.assertTrue(
            any(
                "does not match published size" in item
                for item in report["drift"]
            )
        )
        self.assertTrue(report["drift"])
        self.assertTrue(report["drift_is_fatal"])

    def test_allow_drift_cannot_bypass_size_mismatch(self):
        report, exit_code = self.remote_fetch(
            published_size=self.wrapper.stat().st_size + 1,
            allow_drift=True,
        )
        self.assertEqual(1, exit_code)
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
            package.writestr(
                "blender_manifest.toml",
                MANIFEST + f'version = "{TEST_VERSION}"\n',
            )
            package.writestr("payload.bin", os.urandom(1 * 1024 * 1024 + 1))
        wrapper = make_wrapper_zip(tmp / "release.zip", inner.name, inner)
        asset = wrapper.read_bytes()
        api_payload = json.dumps(
            {
                "tag_name": f"v{TEST_VERSION}",
                "draft": False,
                "prerelease": False,
                "target_commitish": "a" * 40,
                "assets": [
                    {
                        "name": f"cats_blender_plugin-{TEST_VERSION}.zip",
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
                with mock.patch.object(fetch_cats, "verify_attestation"):
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

    def test_policy_contains_identity_but_no_release_pin(self):
        self.assertEqual(
            "Alrauna/Cats-Blender-Plugin", REFERENCE["repository"]
        )
        self.assertEqual(
            (
                "https://github.com/Alrauna/Cats-Blender-Plugin/"
                ".github/workflows/Cats%20Tests.yml@refs/heads/main"
            ),
            REFERENCE.get("certificate_identity"),
        )
        self.assertEqual("refs/heads/main", REFERENCE.get("source_ref"))
        self.assertEqual("cats_blender_plugin", REFERENCE["extension_id"])
        release_pin_keys = {
            "release_tag",
            "asset_name",
            "asset_sha256",
            "asset_size",
            "extension_sha256",
            "extension_size",
            "extension_version",
            "source_digest",
            "signer_digest",
        }
        self.assertTrue(release_pin_keys.isdisjoint(REFERENCE))

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
