# Handoff

## State

The CI/CD and hardening milestone is complete. `master` carries the `addon/`
layout, runtime support for Windows x64, Linux x64 and macOS arm64,
`tests/run_tests.py`, `tools/fetch_cats.py`, and a three-platform CI workflow
with a verified release job.

Version 3.1.0 is in the manifest. **Nothing is tagged and no GitHub release
exists yet.**

## Releasing 3.1.0

Rehearse first. Run the CI workflow with `release` set to `3.1.0` and
`dry_run` ticked. That performs the entire release except the four steps that
touch the repository: it fetches the exact commit, rebuilds, validates every
archive, computes checksums, and confirms the tag is still free, then uploads
the archives it would have published as an artefact and prints their hashes
in the run summary. No tag, no release. A dry run may be started from any
branch, so the release path can be exercised without cutting anything.

Then run it again with `dry_run` unticked, on `master`, to publish.

Leaving `release` empty runs validation only.

The release job refuses to publish unless validation passed on the same
commit, the manifest declares the requested version, and the tag and release
do not already exist. It creates a draft, uploads four archives and
`SHA256SUMS.txt`, downloads what the release actually stored, verifies every
hash, and only then publishes. A draft that fails verification stays a draft.

## Branch protection

`master` requires five status checks: `CI / Windows — Blender 5.2`,
`CI / Linux — Blender 5.2`, `CI / macOS — Blender 5.2`, `Analyze (python)`,
and `Analyze (actions)`.
Admins are included, force pushes and deletions are refused, and no
pull-request review is required, so a solo maintainer can still merge once the
checks pass. Verified by demonstration: a direct push to `master` is rejected
with `GH006`.

Do not require a context named `CodeQL`. Default setup reports per language
under the analysis name, and `CodeQL` appears only in the pull-request rollup,
not as a check run on branch commits, so requiring it would block every merge.

CodeQL default setup currently analyses `actions` and `python`. The `actions`
language was enabled automatically when the workflow files were added, which
is also why `Analyze (actions)` is required: it is what scans the workflows
for injection. **Each new analysed language adds a check that must be added to
the required list deliberately**, and this already happened once within an
hour of protection being applied.

## Known gaps

- The publishing half of the release job has never executed, because running
  it publishes a real release. Everything before it is covered by the dry run
  above. What remains unexercised is creating the draft, uploading,
  re-downloading, verifying the stored copies, and undrafting.
- The `_load_lock` long-path defect is not proven to reproduce on a Windows
  runner. The long-path suite passes there with the fix in place, but nothing
  has shown it would fail without it. Only the `_inside` defect has a
  demonstrated regression.
- The atlas undo and repeatability check runs on Linux only. Neither a
  Windows nor a macOS runner has a window server for foreground Blender, and
  macOS has no xvfb equivalent.
- macOS means Apple Silicon. Blender 5.2 publishes no macOS Intel build, so
  there is nothing for an Intel Mac to run and no Intel wheel is packaged.
  Blender does publish windows-arm64, which this package does not target.
- CATS drift warns rather than fails for local runs. CI passes `--strict`.
  Flip `HASH_MISMATCH_IS_FATAL` in `tools/fetch_cats.py` once the CATS
  repository adopts matching release automation.

## Maintenance notes

- The hand-rolled DNS-over-TLS client in `tools/ci.py` is deliberate. Three
  independent resolution paths only mean something if they do not all share one
  resolver implementation. Do not replace it with curl's DoH client.
- Atlas goldens assert decoded pixel content, not PNG bytes, because Pillow
  links zlib-ng on Windows and macOS but stock zlib on Linux. Adding macOS
  required no new golden, which is the clearest evidence that asserting
  pixels rather than file bytes was correct.
- `SPLIT_PLATFORMS` in `tools/ci.py` must match the manifest's platform list.
  `prepare_release` refuses a release directory containing anything it did
  not expect, so a platform added to one and not the other fails the release.
  A test now enforces the agreement.
- The milestone plan that produced this work was deleted on completion, as
  AGENTS.md requires. It is recoverable from git history if the reasoning
  behind any of the above is ever needed:
  `git log --diff-filter=D -- docs/superpowers/plans/ci-cd-hardening.md`
