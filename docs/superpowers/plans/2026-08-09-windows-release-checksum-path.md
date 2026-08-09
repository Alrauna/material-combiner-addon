# Windows Release Checksum Path Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Repository policy forbids subagent execution unless the user separately requests it.

**Goal:** Prevent false checksum mismatches in Windows release jobs without weakening artifact, attestation, or publication verification.

**Architecture:** Keep the existing Git Bash/coreutils checks and hash the same files using relative filenames from their containing directories. Protect all three affected commands with the existing workflow contract suite.

**Tech Stack:** GitHub Actions YAML, Git Bash, GNU `sha256sum`, Python `unittest`.

## Global Constraints

- Change only `.github/workflows/ci.yml`, its focused contract test, and milestone documentation.
- Preserve exact five-file inventory checks, checksum-manifest binding, four-ZIP checks, least-privilege permissions, attestation-before-publication, protected publication, and stored-byte verification.
- Do not change release artifacts, normalize digests, strip arbitrary characters, change runners, or weaken tests.
- Make no extension API, manifest, dependency, packaging, CATS, DNS resolver, or version changes.

---

### Task 1: Hash release files by relative path on Windows

**Files:**
- Modify: `tests/unit/test_ci_workflow_contract.py`
- Modify: `.github/workflows/ci.yml`
- Modify: `docs/HANDOFF.md`
- Delete at milestone completion: `docs/superpowers/specs/2026-08-09-windows-release-checksum-path.md`
- Delete at milestone completion: `docs/superpowers/plans/2026-08-09-windows-release-checksum-path.md`

**Interfaces:**
- Consumes: `$download`, `$stored`, `EXPECTED_CHECKSUMS_SHA256`, `ARCHIVES`, and existing checksum files.
- Produces: unchanged 64-hex comparisons derived from the same file bytes.

- [ ] **Step 1: Write the failing workflow regression contract**

Extend `test_consumers_verify_the_current_run_artifact` to require this command
in both consumer job sections:

```bash
actual=$(cd "$download" && sha256sum SHA256SUMS.txt | awk '{print $1}')
```

Add a stored-release assertion requiring:

```bash
actual=$(cd "$stored" && sha256sum "$name" | awk '{print $1}')
```

Also reject the three current absolute-path forms.

- [ ] **Step 2: Run the focused contract and verify RED**

Run:

```powershell
python -m unittest tests.unit.test_ci_workflow_contract
```

Expected: failure because the workflow still passes absolute Windows paths to
`sha256sum`.

- [ ] **Step 3: Apply the minimal workflow fix**

Replace only the two manifest digest commands and the stored ZIP digest command
with the relative-path forms from Step 1. Leave all surrounding inventory,
checksum, permission, attestation, and publication logic unchanged.

- [ ] **Step 4: Verify GREEN and reproduce the shell behavior**

Run:

```powershell
python -m unittest tests.unit.test_ci_workflow_contract
```

Then run Git Bash against a checksum file under an absolute Windows path and
confirm the old command parses a leading `\`, while the relative command from
inside its directory returns exactly 64 hex characters.

- [ ] **Step 5: Run preservation gates**

Run:

```powershell
python -m unittest discover -s tests/unit -p "test_*.py"
python -m ruff check .
python tools/verify_dependency_wheel.py
git diff --check
```

Expected: 109 tests plus the new regression pass with the three existing
platform skips; Ruff, wheel verification, and diff checks pass.

- [ ] **Step 6: Review and commit the fix**

Inspect the complete diff, update `docs/HANDOFF.md` with run 31317909983,
validation, and the required post-merge release retry, then commit:

```powershell
git add .github/workflows/ci.yml tests/unit/test_ci_workflow_contract.py docs/HANDOFF.md
git commit -m "fix: hash release files by relative path"
```

- [ ] **Step 7: Close the milestone**

After verification, remove this in-flight spec and plan from the final tree,
commit the handoff state, push the branch, and open a pull request against
`master`. The next authorized non-dry-run 3.1.1 dispatch after merge is the
hosted acceptance test; rerunning run 31317909983 would execute its old commit.

