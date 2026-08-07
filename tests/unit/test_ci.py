from __future__ import annotations

import contextlib
import importlib.util
import io
import socket
import struct
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("smc_ci", ROOT / "tools" / "ci.py")
ci = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = ci
SPEC.loader.exec_module(ci)

MANIFEST = (
    b"96f6c181a30f4950607839dc84d42a354b250d8a0231b098b59b7bc69c351c48"
    b"  blender-5.2.0-linux-x64.tar.xz\n"
    b"2d184b626c001692c362291911293b6a297179d618d95e9e9192c3a80318adc4"
    b"  blender-5.2.0-windows-x64.zip\n"
)


class ChecksumManifestTests(unittest.TestCase):
    def test_parses_rows(self):
        parsed = ci.parse_checksum_manifest(MANIFEST)
        self.assertEqual(2, len(parsed))
        self.assertEqual(
            ci.PLATFORMS["linux"]["sha256"],
            parsed["blender-5.2.0-linux-x64.tar.xz"],
        )

    def test_rejects_malformed_and_empty(self):
        for payload in (b"", b"not-a-hash  file.zip\n", b"deadbeef\n"):
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    ci.parse_checksum_manifest(payload)

    def test_rejects_duplicate_entries(self):
        with self.assertRaises(ValueError):
            ci.parse_checksum_manifest(MANIFEST + MANIFEST)


class ConsensusTests(unittest.TestCase):
    """A single dissenting or poisoned resolver must stop the build."""

    def _expected(self, platform: str) -> tuple[str, str]:
        entry = ci.PLATFORMS[platform]
        return entry["filename"], entry["sha256"]

    def test_unanimous_and_matching_passes(self):
        filename, digest = self._expected("linux")
        ci.require_consensus([MANIFEST] * 3, filename, digest)

    def test_one_dissenting_resolver_fails(self):
        filename, digest = self._expected("linux")
        poisoned = MANIFEST.replace(b"96f6c181", b"00000000")
        with self.assertRaises(ValueError):
            ci.require_consensus(
                [MANIFEST, MANIFEST, poisoned], filename, digest
            )

    def test_unanimous_but_unexpected_hash_fails(self):
        """All resolvers agreeing is not enough; the pin still rules."""
        filename, _ = self._expected("linux")
        with self.assertRaises(ValueError):
            ci.require_consensus([MANIFEST] * 3, filename, "0" * 64)

    def test_missing_entry_fails(self):
        _, digest = self._expected("linux")
        with self.assertRaises(ValueError):
            ci.require_consensus([MANIFEST] * 3, "absent.zip", digest)


class DownloadCommandTests(unittest.TestCase):
    def test_plain_http_is_refused(self):
        with self.assertRaises(ValueError):
            ci.download("http://example.com/x", Path("out"))

    def test_plain_http_doh_is_refused(self):
        with self.assertRaises(ValueError):
            ci.download(
                "https://example.com/x", Path("out"), "http://dns.example"
            )


class GithubOutputTests(unittest.TestCase):
    """A newline in a value would let it declare further step outputs."""

    def test_writes_single_line_values(self):
        target = Path(tempfile.mkdtemp()) / "out.txt"
        target.touch()
        ci.write_github_output(target, blender="/x/blender", python="/x/py")
        self.assertEqual(
            ["blender=/x/blender", "python=/x/py"],
            target.read_text(encoding="utf-8").splitlines(),
        )

    def test_rejects_embedded_newlines(self):
        target = Path(tempfile.mkdtemp()) / "out.txt"
        target.touch()
        for payload in ("a\nevil=1", "a\revil=1"):
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    ci.write_github_output(target, blender=payload)
        self.assertEqual("", target.read_text(encoding="utf-8"))


def dns_response(
    transaction_id: int,
    question: bytes,
    answers: list[bytes],
    *,
    flags: int = 0x8180,
) -> bytes:
    header = struct.pack(
        "!HHHHHH", transaction_id, flags, 1, len(answers), 0, 0
    )
    return header + question + b"".join(answers)


def a_record(name_offset: int, address: str) -> bytes:
    pointer = struct.pack("!H", 0xC000 | name_offset)
    return pointer + struct.pack("!HHIH", 1, 1, 60, 4) + socket.inet_aton(
        address
    )


class DnsParsingTests(unittest.TestCase):
    """The DNS wire parser is hand-rolled, so its rejections are load-bearing."""

    def setUp(self):
        self.transaction_id = 0x1234
        self.question = (
            b"\x08download\x07blender\x03org\x00" + struct.pack("!HH", 1, 1)
        )

    def test_parses_a_records(self):
        message = dns_response(
            self.transaction_id,
            self.question,
            [a_record(12, "1.2.3.4"), a_record(12, "5.6.7.8")],
        )
        self.assertEqual(
            ("1.2.3.4", "5.6.7.8"),
            ci._parse_dns_a_response(
                message, self.transaction_id, self.question
            ),
        )

    def test_rejects_mismatched_transaction_id(self):
        message = dns_response(
            0xBEEF, self.question, [a_record(12, "1.2.3.4")]
        )
        with self.assertRaises(ValueError):
            ci._parse_dns_a_response(
                message, self.transaction_id, self.question
            )

    def test_rejects_a_different_question(self):
        other = b"\x04evil\x03com\x00" + struct.pack("!HH", 1, 1)
        message = dns_response(
            self.transaction_id, other, [a_record(12, "1.2.3.4")]
        )
        with self.assertRaises(ValueError):
            ci._parse_dns_a_response(
                message, self.transaction_id, self.question
            )

    def test_rejects_error_rcode_and_truncation(self):
        for flags in (0x8183, 0x8380):
            with self.subTest(flags=hex(flags)):
                message = dns_response(
                    self.transaction_id,
                    self.question,
                    [a_record(12, "1.2.3.4")],
                    flags=flags,
                )
                with self.assertRaises(ValueError):
                    ci._parse_dns_a_response(
                        message, self.transaction_id, self.question
                    )

    def test_rejects_answer_for_another_owner(self):
        """An answer must belong to the name that was asked about."""
        foreign = b"\x04evil\x03com\x00"
        record = foreign + struct.pack("!HHIH", 1, 1, 60, 4)
        record += socket.inet_aton("6.6.6.6")
        message = dns_response(self.transaction_id, self.question, [record])
        with self.assertRaises(ValueError):
            ci._parse_dns_a_response(
                message, self.transaction_id, self.question
            )

    def test_rejects_pointer_to_an_unknown_offset(self):
        record = struct.pack("!H", 0xC000 | 200)
        record += struct.pack("!HHIH", 1, 1, 60, 4)
        record += socket.inet_aton("1.2.3.4")
        message = dns_response(self.transaction_id, self.question, [record])
        with self.assertRaises(ValueError):
            ci._parse_dns_a_response(
                message, self.transaction_id, self.question
            )

    def test_rejects_truncated_message(self):
        with self.assertRaises(ValueError):
            ci._parse_dns_a_response(b"\x00\x01", self.transaction_id, b"")

    def test_rejects_response_without_an_address(self):
        message = dns_response(self.transaction_id, self.question, [])
        with self.assertRaises(ValueError):
            ci._parse_dns_a_response(
                message, self.transaction_id, self.question
            )


class ResolverConfigurationTests(unittest.TestCase):
    def test_doh_and_resolved_addresses_are_mutually_exclusive(self):
        with self.assertRaises(ValueError):
            ci.download(
                "https://example.com/x",
                Path("out"),
                doh_url=ci.CLOUDFLARE_DOH_URL,
                resolved_addresses=("1.2.3.4",),
            )

    def test_resolved_addresses_are_bounded(self):
        too_many = tuple(f"10.0.0.{n}" for n in range(20))
        with self.assertRaises(ValueError):
            ci.download(
                "https://example.com/x", Path("out"),
                resolved_addresses=too_many,
            )

    def test_dns_over_tls_uses_the_dedicated_port(self):
        self.assertEqual(853, ci.QUAD9_DOT_PORT)
        self.assertEqual("dns.quad9.net", ci.QUAD9_DOT_HOST)


MANIFEST_TOML = 'schema_version = "1.0.0"\nid = "smc"\nversion = "3.1.0"\n'


class ReleaseIdentityTests(unittest.TestCase):
    """The manifest is the authority for what may be released."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.manifest = self.tmp / "blender_manifest.toml"
        self.manifest.write_text(MANIFEST_TOML, encoding="utf-8")

    def test_returns_tag_and_every_archive_name(self):
        tag, names = ci.release_identity("3.1.0", self.manifest)
        self.assertEqual("v3.1.0", tag)
        # Derived from SPLIT_PLATFORMS so adding a platform does not need this
        # list edited, only the platform table.
        expected = ["smc-3.1.0.zip"] + [
            f"smc-3.1.0-{platform}.zip" for platform in ci.SPLIT_PLATFORMS
        ]
        self.assertEqual(expected, names)
        self.assertIn("smc-3.1.0-macos_arm64.zip", names)

    def test_rejects_a_version_the_manifest_does_not_declare(self):
        with self.assertRaises(ValueError):
            ci.release_identity("9.9.9", self.manifest)

    def test_rejects_non_release_versions(self):
        for version in ("3.1.0-alpha.1", "3.1", "v3.1.0", "3.1.0.1", ""):
            with self.subTest(version=version):
                with self.assertRaises(ValueError):
                    ci.release_identity(version, self.manifest)


class PrepareReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.manifest = self.tmp / "blender_manifest.toml"
        self.manifest.write_text(MANIFEST_TOML, encoding="utf-8")
        self.release = self.tmp / "release"
        self.release.mkdir()
        self.checksums = self.release / "SHA256SUMS.txt"

    def _write_all(self):
        for name in ci.release_identity("3.1.0", self.manifest)[1]:
            (self.release / name).write_bytes(name.encode())

    def _prepare(self):
        """Run prepare_release without its progress output reaching the log."""
        with contextlib.redirect_stdout(io.StringIO()):
            return ci.prepare_release(
                "3.1.0", self.manifest, self.release, self.checksums, None
            )

    def test_checksums_cover_every_archive(self):
        self._write_all()
        digests = self._prepare()
        expected_count = 1 + len(ci.SPLIT_PLATFORMS)
        self.assertEqual(expected_count, len(digests))
        rows = self.checksums.read_text(encoding="utf-8").splitlines()
        self.assertEqual(expected_count, len(rows))
        for row in rows:
            digest, name = row.split("  ")
            self.assertRegex(digest, r"\A[0-9a-f]{64}\Z")
            self.assertEqual(
                digest, ci.sha256_file(self.release / name)
            )

    def test_missing_archive_fails(self):
        self._write_all()
        next(self.release.glob("*-linux_x64.zip")).unlink()
        with self.assertRaises(ValueError):
            self._prepare()

    def test_unexpected_archive_fails(self):
        """An extra file would otherwise be published without a checksum."""
        self._write_all()
        (self.release / "smuggled.zip").write_bytes(b"x")
        with self.assertRaises(ValueError):
            self._prepare()


class VerifyFileTests(unittest.TestCase):
    def setUp(self):
        self.path = Path(tempfile.mkdtemp()) / "asset.zip"
        self.path.write_bytes(b"payload")

    def test_matching_hash_passes(self):
        ci.require_file_sha256(self.path, ci.sha256_file(self.path))

    def test_mismatched_hash_fails(self):
        with self.assertRaises(ValueError):
            ci.require_file_sha256(self.path, "0" * 64)

    def test_malformed_expectation_fails(self):
        for expected in ("", "abc", "Z" * 64, ci.sha256_file(self.path)[:-1]):
            with self.subTest(expected=expected):
                with self.assertRaises(ValueError):
                    ci.require_file_sha256(self.path, expected)


class SplitPlatformAgreementTests(unittest.TestCase):
    """A platform added to the manifest must also be expected at release.

    prepare_release refuses a release directory containing anything it did
    not expect, so adding a platform to the manifest without adding it here
    fails the release rather than silently publishing an unchecksummed file.
    """

    def test_split_platforms_match_the_manifest(self):
        import tomllib as _tomllib

        manifest = _tomllib.loads(
            (ROOT / "addon" / "blender_manifest.toml").read_text(
                encoding="utf-8"
            )
        )
        expected = {name.replace("-", "_") for name in manifest["platforms"]}
        self.assertEqual(expected, set(ci.SPLIT_PLATFORMS))


class MacosExtractionTests(unittest.TestCase):
    """macOS carries an app bundle in a disk image, not a named directory."""

    def test_macos_entry_describes_the_bundle_layout(self):
        entry = ci.PLATFORMS["macos"]
        self.assertTrue(entry["filename"].endswith(".dmg"))
        self.assertEqual("Blender.app", entry["root"])
        self.assertEqual("Contents/MacOS/Blender", entry["executable"])
        self.assertIn("Contents/Resources", entry["python_dir"])

    def test_only_macos_uses_a_disk_image(self):
        for name, entry in ci.PLATFORMS.items():
            with self.subTest(platform=name):
                is_dmg = entry["filename"].endswith(".dmg")
                self.assertEqual(name == "macos", is_dmg)


class PlatformTableTests(unittest.TestCase):
    def test_every_platform_pins_a_full_hash(self):
        for name, entry in ci.PLATFORMS.items():
            with self.subTest(platform=name):
                self.assertRegex(entry["sha256"], r"\A[0-9a-f]{64}\Z")
                self.assertIn(ci.BLENDER_VERSION, entry["filename"])


if __name__ == "__main__":
    unittest.main()
