from __future__ import annotations

import importlib.util
import sys
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
        import tempfile

        target = Path(tempfile.mkdtemp()) / "out.txt"
        target.touch()
        ci.write_github_output(target, blender="/x/blender", python="/x/py")
        self.assertEqual(
            ["blender=/x/blender", "python=/x/py"],
            target.read_text(encoding="utf-8").splitlines(),
        )

    def test_rejects_embedded_newlines(self):
        import tempfile

        target = Path(tempfile.mkdtemp()) / "out.txt"
        target.touch()
        for payload in ("a\nevil=1", "a\revil=1"):
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    ci.write_github_output(target, blender=payload)
        self.assertEqual("", target.read_text(encoding="utf-8"))


class PlatformTableTests(unittest.TestCase):
    def test_three_independent_resolvers_are_configured(self):
        self.assertEqual(3, len(ci.RESOLVERS))
        self.assertIsNone(ci.RESOLVERS[0])
        hosts = {r.split("/")[2] for r in ci.RESOLVERS if r}
        self.assertEqual(2, len(hosts))

    def test_every_platform_pins_a_full_hash(self):
        for name, entry in ci.PLATFORMS.items():
            with self.subTest(platform=name):
                self.assertRegex(entry["sha256"], r"\A[0-9a-f]{64}\Z")
                self.assertIn(ci.BLENDER_VERSION, entry["filename"])


if __name__ == "__main__":
    unittest.main()
