import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
UPLOAD_ARTIFACT_SHA = "ea165f8d65b6e75b540449e92b4886f43607fa02"
ATTEST_SHA = "1e69f48acb82d1966a394da916b4c1698aa569d6"


class ReleaseWorkflowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def section(self, name, next_name=None):
        marker = f"\n  {name}:\n"
        self.assertIn(marker, self.text)
        section = self.text.split(marker, 1)[1]
        if next_name is not None:
            section = section.split(f"\n  {next_name}:\n", 1)[0]
        return section

    def test_release_jobs_have_an_attestation_dependency(self):
        package = self.section("release_package", "release_attestation")
        attestation = self.section("release_attestation", "release_publish")
        publish = self.section("release_publish")

        self.assertIn("needs: [validate, release_gate]", package)
        self.assertIn("needs: [release_package]", attestation)
        self.assertIn(
            "needs: [release_package, release_attestation]", publish
        )
        self.assertIn("!inputs.dry_run", attestation)
        self.assertIn("!inputs.dry_run", publish)

    def test_release_permissions_are_least_privilege(self):
        package = self.section("release_package", "release_attestation")
        attestation = self.section("release_attestation", "release_publish")
        publish = self.section("release_publish")

        self.assertIn("permissions:\n      contents: read", package)
        self.assertNotIn("contents: write", package)
        self.assertNotIn("id-token: write", package)
        self.assertNotIn("attestations: write", package)
        self.assertIn(
            "permissions:\n"
            "      actions: read\n"
            "      contents: read\n"
            "      id-token: write\n"
            "      attestations: write",
            attestation,
        )
        self.assertNotIn("contents: write", attestation)
        self.assertNotIn("environment: release", attestation)
        self.assertIn("environment: release", publish)
        self.assertIn(
            "permissions:\n      actions: read\n      contents: write",
            publish,
        )
        self.assertNotIn("id-token: write", publish)

    def test_package_uploads_the_exact_short_lived_handoff(self):
        package = self.section("release_package", "release_attestation")
        self.assertIn(
            f"actions/upload-artifact@{UPLOAD_ARTIFACT_SHA}", package
        )
        self.assertIn("name: material-combiner-release-package", package)
        self.assertIn("${{ runner.temp }}/release/*.zip", package)
        self.assertIn("${{ runner.temp }}/release/SHA256SUMS.txt", package)
        self.assertIn("if-no-files-found: error", package)
        self.assertIn("retention-days: 1", package)
        self.assertIn("compression-level: 0", package)
        for command in ("gh release create", "gh release upload", "gh release edit"):
            self.assertNotIn(command, package)

    def test_consumers_verify_the_current_run_artifact(self):
        attestation = self.section("release_attestation", "release_publish")
        publish = self.section("release_publish")
        for section in (attestation, publish):
            self.assertIn('gh run download "$GITHUB_RUN_ID"', section)
            self.assertIn('--repo "${{ github.repository }}"', section)
            self.assertIn('--name "$RELEASE_ARTIFACT_NAME"', section)
            self.assertIn("SHA256SUMS.txt", section)
            self.assertIn("sha256sum --check", section)
            self.assertIn("expected exactly five release package files", section)
            self.assertIn("EXPECTED_CHECKSUMS_SHA256", section)
            self.assertIn("release checksum manifest digest mismatch", section)

    def test_verified_zips_are_attested_before_publication(self):
        attestation = self.section("release_attestation", "release_publish")
        publish = self.section("release_publish")
        self.assertEqual(
            [f"actions/attest@{ATTEST_SHA}"],
            re.findall(r"^\s*uses:\s*(actions/attest@\S+)", self.text, re.MULTILINE),
        )
        self.assertIn(
            "subject-path: '${{ runner.temp }}/downloaded-release/*.zip'",
            attestation,
        )
        self.assertNotIn("actions/checkout@", attestation)
        self.assertNotIn("actions/checkout@", publish)
        for section in (attestation, publish):
            self.assertIn("github.ref == 'refs/heads/master'", section)
            self.assertIn(
                "github.event.repository.visibility == 'public'", section
            )
        positions = [
            self.text.index(f"actions/attest@{ATTEST_SHA}"),
            self.text.index("gh release create"),
            self.text.index("gh release upload"),
            self.text.index("gh release download", self.text.index("gh release upload")),
            self.text.index("gh release edit"),
        ]
        self.assertEqual(positions, sorted(positions))

    def test_dry_run_stops_after_packaging(self):
        package = self.section("release_package", "release_attestation")
        attestation = self.section("release_attestation", "release_publish")
        publish = self.section("release_publish")
        self.assertIn("inputs.dry_run", package)
        self.assertIn("Summarise the dry run", package)
        self.assertIn("!inputs.dry_run", attestation)
        self.assertIn("!inputs.dry_run", publish)


if __name__ == "__main__":
    unittest.main()
