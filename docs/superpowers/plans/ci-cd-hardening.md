# CI/CD and hardening milestone

Approved plan. One workstream per pull request, in dependency order. Delete
this file from `master` once the milestone is complete.

The reference implementation is `Alrauna/blender-alpha-material-separator`
(`.github/workflows/ci.yml` and `scripts/ci.py`). It is a starting point, not
a template to copy: the layout, platform support, and test harness all differ.

## Approved decisions

- Linux gets full runtime support: a second Pillow wheel and a cross-platform
  Python test runner, not a CI-only column.
- CATS is downloaded from the latest release of `Alrauna/Cats-Blender-Plugin`
  and its SHA-256 is recorded and checked, but a mismatch is a **warning, not
  a build failure**. The check must be written so that promoting it to a hard
  failure is a one-line change, because the CATS repository needs the same
  CI/CD work and the two will move together.
- `LICENSE` and `README.md` are not packaged. The manifest declares the
  license with an SPDX expression.
- `THIRD_PARTY.md` **is** packaged, so the distributed extension carries its
  own attribution notice for the bundled Pillow wheel.

## Sequence

### 1. `addon/` subdirectory (this PR)

Move the extension package under `addon/`. Everything else becomes
development material. Rework `run_blender_tests.ps1`, which copied the whole
repository into the isolated profile and ran tests from inside that copy;
tests now run from the repository against a copy of `addon/` only.

### 2. Linux support

Split into two pull requests. 2a (runtime support) is done; 2b (the runner)
is not.

**2a — runtime support (complete).** Measured outcome: dimensions and decoded
pixels are identical across platforms; PNG file bytes are not, because Pillow
links zlib-ng on Windows and stock zlib on Linux. Goldens now assert pixel
content, with the file hashes retained as evidence. `linux-x64` is declared
in the manifest on the strength of a full atlas-suite pass on real Linux.

**2b — cross-platform Python test runner (complete).** `tests/run_tests.py`
replaces the three PowerShell runners with `source`, `package`, and
`checkpoint` modes. Verified on Windows and Linux. CI can now cover both.

Original scope, for reference:

- Add the manylinux Pillow 12.3.0 wheel with provenance, license, and hash.
- Make `dependencies.lock.json` multi-wheel.
- Generalize `EXPECTED_PLATFORM` and the `sys.platform == "win32"` check in
  `addon/dependencies.py`.
- Generalize the hardcoded `win_amd64` and `.pyd` names in
  `tools/verify_dependency_wheel.py`.
- Replace the PowerShell runners with a cross-platform Python runner. `subst`
  has no POSIX equivalent, so this is a rewrite rather than a translation.
- Declare `linux-x64` in the manifest only after atlas goldens are confirmed
  on Linux. Cross-platform PNG output matching the existing `sha256` goldens
  is not a given and must be measured, not assumed.
- Update `THIRD_PARTY.md` and the README platform statements.

### 3. CATS download (complete)

`tools/fetch_cats.py` plus `tools/cats_reference.json`. The published asset
turned out to be a wrapper ZIP containing the installable extension ZIP, which
Blender cannot install directly; the tool unwraps it. The unwrapped build
passes the full checkpoint, so no CATS evidence needed re-baselining after all.
Drift warns by default; `--strict` or `HASH_MISMATCH_IS_FATAL` makes it fail.

Original scope, for reference:

- Resolve the latest release of `Alrauna/Cats-Blender-Plugin`, download the
  asset, and verify its SHA-256 against a recorded value.
- The published asset is **not** the archive currently pinned by
  `tests/run_checkpoint_test.ps1` (`14EBB594...`, 1,304,732 bytes). The
  release asset is 1,282,884 bytes, so the pin must be re-baselined and the
  CATS behavioral evidence regenerated against the published build.
- Keep the local `.local-references` path working for offline runs.

### 4. CI workflow

**CI must fetch CATS with `--strict`.** Drift warns locally so developers are
not blocked, but on a runner the archive is executed with a privileged token,
and the pin is the only integrity control. Local runs stay lenient; CI does
not.

Port `scripts/ci.py` from the separator, keeping the three-resolver checksum
consensus intact; change only the platform table, archive name, and release
identity. Jobs: unit tests, source-tree Blender suites, `extension validate`
on `addon/`, build, package suites.

Known CI gaps to state explicitly in the workflow rather than omit silently:

- The atlas undo check needs `-Foreground` and a real window. Run background
  in CI, where it self-skips, and keep foreground as a local gate.
- Runner temp paths are short, so the MAX_PATH defect class fixed in
  `dependencies.py` is not exercised. Covering it needs the runner to force a
  deliberately long work directory.

### 5. Release workflow and branch protection

Release: `workflow_dispatch` with a version input, manifest-match gate, clean
re-fetch of the exact SHA, rebuild, refuse existing tag or release, draft,
upload, re-download, verify hash, publish.

Branch protection on `master` mirroring the separator's `main`: required
status checks, `enforce_admins`, no force pushes, no deletions. This must come
last, because required status checks reference job names that do not exist
until the CI workflow is merged.
