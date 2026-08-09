# CATS Consumption and Material Combiner Release Attestation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Repository policy forbids subagent execution unless the user separately requests it.

**Goal:** Make Material Combiner 3.1.1 consume the latest final CATS release only after strict GitHub build-provenance verification, with no committed CATS release pin, and publish Material Combiner releases only after all four ZIPs receive GitHub provenance attestations.

**Architecture:** Keep `tools/fetch_cats.py` as the single CATS acquisition boundary. Replace its immutable release snapshot with repository/workflow policy, invoke the installed GitHub CLI for cryptographic verification before ZIP parsing, retain existing safety bounds and archive normalization, then let the unchanged Blender checkpoint decide compatibility. Split Material Combiner release handling into least-privilege package, attestation, and publish jobs connected by an exact current-run workflow artifact and checksum manifest.

**Tech Stack:** Python 3.13 standard library, GitHub CLI artifact attestations, GitHub Actions, Blender 5.2 extension tooling, `unittest`.

## Global Constraints

- Change only `Alrauna/material-combiner-addon`; do not modify CATS or Alpha Material Separator.
- Commit no CATS version, tag, release commit, size, or SHA-256 pin.
- Trust remote CATS bytes only after `gh attestation verify` constrains the repository, signer workflow, `refs/heads/main`, dynamically resolved release commit, and GitHub-hosted runner origin.
- Do not pin the signer workflow digest and do not implement a custom Sigstore verifier.
- Preserve bounded downloads/extraction, API-token host isolation, HTTPS enforcement, extension-ID validation, GitHub-output injection protection, and checkpoint SHA-256 handoff.
- Preserve the extension API, imports, operators, RNA properties, registration/lifecycle behavior, bundled Pillow model, package layout, supported platforms, atlas behavior, and all valid existing tests.
- Keep `--archive`, `--strict`, and `--allow-drift` accepted; no remote option may bypass attestation.
- Set Material Combiner's manifest version and development target to `3.1.1`.
- Attest every published universal and platform-specific Material Combiner ZIP
  with the SHA-pinned official `actions/attest` action before publication.
- Keep package jobs read-only, isolate OIDC/attestation writes from release
  content writes, and retain the protected release environment on publication.
- Preserve dry-run packaging and inspection without creating public
  attestations or releases for rehearsal artifacts.

---

### Task 0: Preserve the approved design and plan

**Files:**
- Add: `docs/superpowers/specs/2026-08-09-cats-attestation-policy.md`
- Add: `docs/superpowers/plans/2026-08-09-cats-attestation-policy.md`
- Modify: `docs/HANDOFF.md`

**Interfaces:**
- Consumes: the user's approved no-pin attestation design.
- Produces: a reviewable planning commit that every implementation task follows.

- [ ] **Step 1: Recheck branch scope and planning-only diff**

```powershell
git branch --show-current
git status --short --untracked-files=all
git diff --check
git diff -- docs/HANDOFF.md docs/superpowers/specs/2026-08-09-cats-attestation-policy.md docs/superpowers/plans/2026-08-09-cats-attestation-policy.md
```

Expected: branch `codex/cats-update-policy-3.1.1`; only the handoff, approved
specification, and implementation plan differ; diff check reports no errors.

- [ ] **Step 2: Commit the approved planning artifacts**

```powershell
git add docs/HANDOFF.md docs/superpowers/specs/2026-08-09-cats-attestation-policy.md docs/superpowers/plans/2026-08-09-cats-attestation-policy.md
git diff --cached --check
git commit -m "docs: plan CATS attestation policy"
```

### Task 1: Replace the release snapshot with an attestation policy

**Files:**
- Modify: `tools/cats_reference.json`
- Modify: `tests/unit/test_fetch_cats.py`
- Modify: `tools/fetch_cats.py`

**Interfaces:**
- Consumes: the existing bounded `_get`, `_download`, `api_token`, and `sha256_file` helpers.
- Produces: `resolve_latest(repository: str) -> tuple[str, str, str, int, str]` and `verify_attestation(archive: Path, *, repository: str, signer_workflow: str, source_ref: str, source_digest: str) -> None`.

- [ ] **Step 1: Write failing policy and release-metadata tests**

Replace pin-oriented fixtures and `ReferenceFileTests.test_reference_records_integrity_facts` with assertions equivalent to:

```python
RELEASE_PIN_KEYS = {
    "release_tag", "asset_name", "asset_sha256", "asset_size",
    "extension_sha256", "extension_size", "extension_version",
    "source_digest", "signer_digest",
}

def test_policy_contains_identity_but_no_release_pin(self):
    self.assertEqual("Alrauna/Cats-Blender-Plugin", REFERENCE["repository"])
    self.assertEqual(
        "Alrauna/Cats-Blender-Plugin/.github/workflows/Cats Tests.yml",
        REFERENCE["signer_workflow"],
    )
    self.assertEqual("refs/heads/main", REFERENCE["source_ref"])
    self.assertEqual("cats_blender_plugin", REFERENCE["extension_id"])
    self.assertTrue(RELEASE_PIN_KEYS.isdisjoint(REFERENCE))

def test_latest_release_returns_dynamic_source_commit(self):
    payload = {
        "tag_name": "v99.4.7",
        "draft": False,
        "prerelease": False,
        "target_commitish": "a" * 40,
        "assets": [{
            "name": "cats_blender_plugin-99.4.7.zip",
            "browser_download_url": "https://example.test/cats.zip",
            "size": 123,
        }],
    }
    with mock.patch.object(
        fetch_cats, "_get", return_value=json.dumps(payload).encode()
    ):
        self.assertEqual(
            ("v99.4.7", "cats_blender_plugin-99.4.7.zip",
             "https://example.test/cats.zip", 123, "a" * 40),
            fetch_cats.resolve_latest(REFERENCE["repository"]),
        )
```

Add cases rejecting `draft=True`, `prerelease=True`, non-40-hex
`target_commitish`, and zero or multiple ZIP assets.

- [ ] **Step 2: Run the focused tests and confirm RED**

Run:

```powershell
python -m unittest tests.unit.test_fetch_cats.ReferenceFileTests tests.unit.test_fetch_cats.ReleaseMetadataTests -v
```

Expected: failures because the reference still contains immutable release facts and `resolve_latest` does not return or validate the source commit.

- [ ] **Step 3: Convert the reference JSON to moving policy**

Set its complete functional content to:

```json
{
  "schema_version": 2,
  "repository": "Alrauna/Cats-Blender-Plugin",
  "signer_workflow": "Alrauna/Cats-Blender-Plugin/.github/workflows/Cats Tests.yml",
  "source_ref": "refs/heads/main",
  "extension_id": "cats_blender_plugin",
  "extension_zip_name": "cats_blender_plugin.zip"
}
```

Do not add a version, tag, hash, size, release commit, minimum version, asset
template, or signer digest.

- [ ] **Step 4: Implement strict dynamic release metadata parsing**

Update `resolve_latest` to return `(tag, asset_name, download_url,
published_size, source_digest)`, require `draft is False`, `prerelease is
False`, exactly one `.zip` asset, a nonnegative integer size, HTTPS download
URL, and a lowercase-or-uppercase 40-hex source digest normalized to lowercase:

```python
source_digest = payload.get("target_commitish")
if not isinstance(source_digest, str) or re.fullmatch(
    r"[0-9a-fA-F]{40}", source_digest
) is None:
    raise RuntimeError("Latest release target is not an exact commit")
```

Retain the bounded authenticated API request and single-ZIP rule.

- [ ] **Step 5: Run the focused tests and confirm GREEN**

Run:

```powershell
python -m unittest tests.unit.test_fetch_cats.ReferenceFileTests tests.unit.test_fetch_cats.ReleaseMetadataTests -v
```

Expected: all policy and metadata tests pass.

- [ ] **Step 6: Commit the verified policy unit**

```powershell
git add tools/cats_reference.json tools/fetch_cats.py tests/unit/test_fetch_cats.py
git diff --cached --check
git commit -m "test: define moving CATS provenance policy"
```

### Task 2: Require official attestation verification before archive inspection

**Files:**
- Modify: `tests/unit/test_fetch_cats.py`
- Modify: `tools/fetch_cats.py`

**Interfaces:**
- Consumes: `resolve_latest(...)` from Task 1 and policy keys `repository`, `signer_workflow`, and `source_ref`.
- Produces: `verify_attestation(...) -> None`; remote `fetch(...)` reports `attestation_verified: true`, while local archive mode reports `false`.

- [ ] **Step 1: Write failing verifier-process tests**

Add `AttestationTests` using `mock.patch.object(shutil, "which")` and
`mock.patch.object(subprocess, "run")`. Assert the exact invocation:

```python
[
    "/usr/bin/gh", "attestation", "verify", str(archive),
    "--repo", "Alrauna/Cats-Blender-Plugin",
    "--signer-workflow",
    "Alrauna/Cats-Blender-Plugin/.github/workflows/Cats Tests.yml",
    "--source-ref", "refs/heads/main",
    "--source-digest", "a" * 40,
    "--deny-self-hosted-runners",
]
```

Require `check=True`, `capture_output=True`, `text=True`, and a finite timeout.
Add tests that a missing `gh` executable raises `RuntimeError`, a nonzero
`subprocess.CalledProcessError` raises `RuntimeError` without including tokens,
and `allow_drift=True` does not suppress the failure.

- [ ] **Step 2: Write the failing ordering and future-version tests**

Mock `_download`, `verify_attestation`, and `unwrap` and record their call
order. Require `download`, then `attestation`, then `unwrap`. Build a direct
extension ZIP with manifest version `99.4.7`, mock release tag
`v99.4.7`, asset name `cats_blender_plugin-99.4.7.zip`, and a successful
attestation; require exit code zero without changing policy data.

Add mismatch cases requiring exit code one for:

```text
manifest id differs from `cats_blender_plugin`
release tag differs from the manifest-derived `v` plus version
asset name differs from the manifest-derived `cats_blender_plugin-` name
missing or non-string manifest version
```

- [ ] **Step 3: Run the focused tests and confirm RED**

Run:

```powershell
python -m unittest tests.unit.test_fetch_cats.AttestationTests tests.unit.test_fetch_cats.DynamicIdentityTests -v
```

Expected: failures because no verifier exists and fetch still compares against immutable pins.

- [ ] **Step 4: Implement the minimum official verifier wrapper**

Import `re` and `subprocess`, reuse the existing `shutil` import, add a finite
`ATTESTATION_TIMEOUT_SECONDS`, and implement:

```python
def verify_attestation(
    archive: Path,
    *,
    repository: str,
    signer_workflow: str,
    source_ref: str,
    source_digest: str,
) -> None:
    executable = shutil.which("gh")
    if executable is None:
        raise RuntimeError("GitHub CLI is required to verify CATS provenance")
    command = [
        executable, "attestation", "verify", str(archive),
        "--repo", repository,
        "--signer-workflow", signer_workflow,
        "--source-ref", source_ref,
        "--source-digest", source_digest,
        "--deny-self-hosted-runners",
    ]
    try:
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=ATTESTATION_TIMEOUT_SECONDS,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        raise RuntimeError("CATS build-provenance verification failed") from error
```

Do not invoke a shell, parse untrusted output, install a verifier, or create a
fallback cryptographic implementation.

- [ ] **Step 5: Replace pin drift with attestation and dynamic identity**

For remote mode, verify the downloaded release asset before `unwrap`. Remove
all comparisons to committed tag, asset name, sizes, hashes, and extension
version. After unwrapping, require the expected extension ID and derive:

```python
expected_tag = f"v{actual_version}"
expected_asset_name = f"cats_blender_plugin-{actual_version}.zip"
```

Reject disagreement with the resolved tag or asset name. Keep computing and
reporting actual/published sizes and SHA-256 values, and keep emitting the
extension SHA-256 for the checkpoint. Preserve archive bounds, token isolation,
and direct/wrapper support.

Remote operation must always require attestation regardless of `allow_drift`.
Local `--archive` operation validates structure and ID, reports
`attestation_verified: false`, and never calls `gh`. `--strict --archive` must
return failure in `main` before calling `fetch` because provenance is
unavailable; plain local mode remains an explicit offline inspection path.

- [ ] **Step 6: Run focused and complete fetcher tests and confirm GREEN**

Run:

```powershell
python -m unittest tests.unit.test_fetch_cats -v
```

Expected: all attestation, future-version, metadata, bounds, token-isolation,
archive, ID, CLI, and GitHub-output tests pass. No valid prior safety test is
deleted without an equivalent policy assertion.

- [ ] **Step 7: Commit the verified acquisition behavior**

```powershell
git add tools/fetch_cats.py tests/unit/test_fetch_cats.py
git diff --cached --check
git commit -m "feat: trust attested CATS releases"
```

### Task 3: Require attestation before publishing Material Combiner releases

**Files:**
- Modify: `.github/workflows/ci.yml`
- Add: `tests/unit/test_ci_workflow_contract.py`

**Interfaces:**
- Consumes: the existing `release_gate`, exact-source checkout, four-archive build, Blender validation, `tools/ci.py prepare-release`, protected `release` environment, and dry-run input.
- Produces: `release_package -> release_attestation -> release_publish`, connected only by current-run artifact identity, job outputs, and checksums.

- [ ] **Step 1: Write failing release-workflow contract tests**

Using only `pathlib`, `re`, and `unittest`, load `.github/workflows/ci.yml` as
text and assert:

- the three named release jobs and dependency order exist;
- package has only `contents: read`, attestation has exactly `actions: read`,
  `contents: read`, `id-token: write`, and `attestations: write`, and publish has
  `actions: read` plus `contents: write` and `environment: release`;
- package uploads one fixed-name artifact containing exactly four ZIPs and
  `SHA256SUMS.txt`, with `if-no-files-found: error`, one-day retention, and
  compression level zero;
- both consumers run `gh run download $GITHUB_RUN_ID` with the explicit
  repository and artifact name, reject extra/missing files, and verify every
  checksum;
- a single SHA-pinned
  `actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6` invocation uses
  only the verified `*.zip` subjects;
- publish depends on attestation and keeps the existing draft/upload/download/
  rehash/publish order; and
- dry runs reach package upload and summary but cannot reach attestation or
  publication.

Retain `tests/unit/test_ci.py` release identity, exact archive set, checksum,
and manifest/platform agreement tests unchanged.

- [ ] **Step 2: Run the contract tests and confirm RED**

```powershell
python -m unittest tests.unit.test_ci_workflow_contract -v
```

Expected: failures because the workflow still has one combined release job and
does not invoke `actions/attest`.

- [ ] **Step 3: Split the package job with a bounded artifact handoff**

Rename the existing job to `release_package`. Keep exact public-source checkout,
all four builds, Blender validation, and `prepare-release`. Give it only
`contents: read`. Emit the tag, archive list, and a SHA-256 of
`SHA256SUMS.txt` as job outputs. Upload the four ZIPs and checksum file under a
fixed artifact name with the proven pinned `actions/upload-artifact` version,
`if-no-files-found: error`, `retention-days: 1`, and `compression-level: 0`.

For a dry run, retain the inspectable artifact and summary. Do not request OIDC,
write repository contents, check or mutate tags/releases, or attest rehearsal
bytes in this job.

- [ ] **Step 4: Add the isolated attestation job**

Run only for real release dispatches from the protected release branch in a
public repository. Depend on `release_package`, use no checkout, grant exactly
`actions: read`, `contents: read`, `id-token: write`, and `attestations: write`,
and download the fixed artifact from `GITHUB_RUN_ID` with explicit `--repo` and
`--name` arguments.

Require exactly the four expected ZIP names plus `SHA256SUMS.txt`, require the
checksum file's digest to equal the package output, and verify all four ZIP
digests. Then invoke the pinned official action once with:

```yaml
subject-path: '${{ runner.temp }}/downloaded-release/*.zip'
```

The job must have neither `contents: write`, a protected environment, checkout,
nor release mutation commands.

- [ ] **Step 5: Add the protected publish job**

Depend on both `release_package` and `release_attestation`, use no checkout,
grant `actions: read` and `contents: write`, and retain `environment: release`.
Independently download the same current-run artifact and repeat the exact-set,
checksum-file digest, and per-ZIP checksum validation. Only then retain the
existing refusal of an existing tag/release, draft creation, upload of the four
ZIPs and checksum file, download and hash verification of stored ZIPs, and
final publication. A failed attestation or any byte mismatch must prevent this
job from starting or publishing.

- [ ] **Step 6: Run workflow contracts and existing release tests GREEN**

```powershell
python -m unittest tests.unit.test_ci_workflow_contract tests.unit.test_ci -v
python -m ruff check tests/unit/test_ci_workflow_contract.py
```

Expected: all workflow security contracts and existing release identity tests
pass.

- [ ] **Step 7: Commit the release-provenance unit**

```powershell
git add .github/workflows/ci.yml tests/unit/test_ci_workflow_contract.py
git diff --cached --check
git commit -m "ci: attest Material Combiner releases"
```

### Task 4: Wire CATS CI policy, documentation, and Material Combiner 3.1.1

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `addon/blender_manifest.toml`
- Modify: `AGENTS.md`
- Modify: `tests/README.md`
- Modify: `docs/HANDOFF.md`

**Interfaces:**
- Consumes: unchanged `tools/fetch_cats.py --strict --github-output ...` CLI and unchanged checkpoint `--cats`/`--cats-sha256` inputs.
- Produces: Material Combiner manifest version `3.1.1` and accurate operator documentation for both attestation-backed CATS testing and attested release publication.

- [ ] **Step 1: Update CATS CI comments and step naming without changing test scope**

Rename the existing step to `Fetch and attest CATS`. Keep `GH_TOKEN`,
`--strict`, `--github-output`, the environment-based path handoff, and the full
checkpoint command. Explain that the fetcher verifies repository/workflow/main/
exact-release-commit/hosted-runner provenance before outputting the archive.

- [ ] **Step 2: Bump only authoritative project version metadata**

Change `addon/blender_manifest.toml` to `version = "3.1.1"` and the development
target in `AGENTS.md` from 3.1.0 to 3.1.1. Do not rewrite generic 3.1.0 unit-test
fixtures.

- [ ] **Step 3: Replace pin-oriented testing and release documentation**

Update `tests/README.md` for the no-pin CATS consumer policy, non-bypassable
remote attestation, explicitly unattested offline archives, exact checkpoint
hash handoff, and the package/attest/publish release sequence. Update
`docs/HANDOFF.md` with RED/GREEN evidence, the local Sigstore limitation if it
persists, dry-run behavior, and hosted acceptance requirements.

- [ ] **Step 4: Run metadata and documentation checks**

```powershell
python -m unittest tests.unit.test_fetch_cats tests.unit.test_run_tests tests.unit.test_ci tests.unit.test_ci_workflow_contract -v
python -m ruff check .
git diff --check
```

- [ ] **Step 5: Commit the version and documentation unit**

```powershell
git add .github/workflows/ci.yml addon/blender_manifest.toml AGENTS.md tests/README.md docs/HANDOFF.md
git diff --cached --check
git commit -m "chore: prepare Material Combiner 3.1.1"
```

### Task 5: Run complete preservation and hosted acceptance gates

**Files:**
- Modify during closeout only: `docs/HANDOFF.md`
- Delete after the milestone is fully committed: `docs/superpowers/specs/2026-08-09-cats-attestation-policy.md`
- Delete after the milestone is fully committed: `docs/superpowers/plans/2026-08-09-cats-attestation-policy.md`

**Interfaces:**
- Consumes: the complete branch and installed Blender 5.2 at `C:\Program Files\Blender Foundation\Blender 5.2\blender.exe`.
- Produces: final validation evidence and a branch ready for authorized publication.

- [ ] **Step 1: Run baseline repository gates**

```powershell
python -m unittest discover -s tests/unit -p "test_*.py"
python -m ruff check .
python tools/verify_dependency_wheel.py
git diff --check
```

Expected: all unit tests pass with only documented skips, Ruff and wheel
verification pass, and diff check prints nothing.

- [ ] **Step 2: Run a live strict attestation fetch**

```powershell
$catsWork = Join-Path $env:TEMP 'material-combiner-cats-attestation'
python tools/fetch_cats.py --output-dir $catsWork --strict
```

Expected: exit zero, `attestation_verified` is true, the resolved release is
not compared to committed release facts, and the report identifies a valid
`cats_blender_plugin` extension. If GitHub CLI still reports
`Error: verifying with issuer "sigstore.dev"`, record the exact failure and do
not substitute API-presence checks or a custom verifier; hosted CI remains
blocking.

- [ ] **Step 3: Validate source and build the required release archive**

```powershell
$blender52 = 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
& $blender52 --command extension validate addon
$releaseDir = Join-Path (Get-Location) '.packaged-releases'
& $blender52 --command extension build --source-dir addon --output-dir $releaseDir
& $blender52 --command extension validate (Join-Path $releaseDir 'shotariyas_material_combiner-3.1.1.zip')
```

Expected: source and package validation pass; the archive is written only to
`.packaged-releases/` with the manifest-derived ID and version.

- [ ] **Step 4: Run affected Blender source and package preservation suites**

```powershell
$blender52 = 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
$releaseZip = Join-Path (Get-Location) '.packaged-releases\shotariyas_material_combiner-3.1.1.zip'
python tests/run_tests.py --blender $blender52 --work (Join-Path $env:TEMP 'smc-311-source') source
python tests/run_tests.py --blender $blender52 --work (Join-Path $env:TEMP 'smc-311-package') package --package $releaseZip
```

Expected: all unattended source and installed-package suites pass. The Windows
foreground atlas undo/repeatability limitation remains documented rather than
silently treated as covered.

- [ ] **Step 5: Run the existing CATS checkpoint with the attested archive**

After Step 2 succeeds, use its reported `extension` and `extension_sha256`:

```powershell
python tests/run_tests.py --blender $blender52 --work (Join-Path $env:TEMP 'smc-311-checkpoint') checkpoint --package $releaseZip --cats $catsExtension --cats-sha256 $catsSha256
```

Expected: integration, restart, uninstall, and exact-file hash checks pass with
the unchanged checkpoint assertions.

- [ ] **Step 6: Review the complete branch before any publication**

```powershell
git diff master...HEAD --stat
git diff master...HEAD
git log --oneline master..HEAD
git status --short --untracked-files=all
```

Confirm no local references, assessment output, credentials, absolute machine
paths, generated release ZIPs, caches, logs, or unrelated changes are tracked.
Review specifically that CATS and AMS repositories have no changes and that
the extension public contracts have no diff.

- [ ] **Step 7: Obtain hosted attestation acceptance**

After publication is separately authorized, push this topic branch and open a
pull request to `master`. Require all three `Fetch and attest CATS` matrix
steps and their unchanged checkpoints to pass on GitHub-hosted Windows, Linux,
and macOS runners. Exercise a 3.1.1 dry run and require the package artifact to
contain exactly four ZIPs plus `SHA256SUMS.txt`, with no tag, release, or public
attestation. For the separately authorized real release, require the
attestation job to succeed before publication and verify each published ZIP
with `gh attestation verify --repo Alrauna/material-combiner-addon`. A hosted
verifier or producer-attestation failure blocks completion and is debugged
without weakening permissions, flags, or tests.

- [ ] **Step 8: Close the completed milestone**

Once local and hosted gates pass, update `docs/HANDOFF.md` with exact commands,
results, PR/run links, and any genuine limitation. Commit that evidence, then
remove the in-flight spec and plan as required by `AGENTS.md` and commit the
deletion:

```powershell
git add docs/HANDOFF.md
git commit -m "docs: record CATS attestation validation"
git add docs/superpowers/specs/2026-08-09-cats-attestation-policy.md docs/superpowers/plans/2026-08-09-cats-attestation-policy.md
git commit -m "docs: close CATS attestation milestone"
```

Do not begin another objective on this completed branch.
