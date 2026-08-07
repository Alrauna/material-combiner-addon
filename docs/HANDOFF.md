# Handoff

## State

The CI/CD and hardening milestone is complete. `master` carries the `addon/`
layout, Linux x64 runtime support, `tests/run_tests.py`, `tools/fetch_cats.py`,
and a validating CI workflow with a verified release job.

Version 3.1.0 is in the manifest. **Nothing is tagged and no GitHub release
exists yet.**

## Releasing 3.1.0

Run the CI workflow from the Actions tab with the `release` input set to
`3.1.0`, on `master`. Leaving that input empty runs validation only.

The release job refuses to publish unless validation passed on the same
commit, the manifest declares the requested version, and the tag and release
do not already exist. It creates a draft, uploads three archives and
`SHA256SUMS.txt`, downloads what the release actually stored, verifies every
hash, and only then publishes. A draft that fails verification stays a draft.

## Branch protection

`master` requires four status checks: `CI / Windows — Blender 5.2`,
`CI / Linux — Blender 5.2`, `Analyze (python)`, and `Analyze (actions)`.
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

- The release job has never executed, because running it publishes a real
  release. Every command it runs was exercised locally, and the gate, identity,
  checksum, and verification logic have unit tests.
- The `_load_lock` long-path defect is not proven to reproduce on a Windows
  runner. The long-path suite passes there with the fix in place, but nothing
  has shown it would fail without it. Only the `_inside` defect has a
  demonstrated regression.
- The atlas undo and repeatability check runs on Linux only. A Windows runner
  has no interactive desktop, so foreground Blender blocks there.
- CATS drift warns rather than fails for local runs. CI passes `--strict`.
  Flip `HASH_MISMATCH_IS_FATAL` in `tools/fetch_cats.py` once the CATS
  repository adopts matching release automation.

## Maintenance notes

- The hand-rolled DNS-over-TLS client in `tools/ci.py` is deliberate. Three
  independent resolution paths only mean something if they do not all share one
  resolver implementation. Do not replace it with curl's DoH client.
- Atlas goldens assert decoded pixel content, not PNG bytes, because Pillow
  links zlib-ng on Windows and stock zlib on Linux.
- The milestone plan that produced this work was deleted on completion, as
  AGENTS.md requires. It is recoverable from git history if the reasoning
  behind any of the above is ever needed:
  `git log --diff-filter=D -- docs/superpowers/plans/ci-cd-hardening.md`
