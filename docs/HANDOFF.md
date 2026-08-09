# Handoff

## Active Windows release checksum fix

`codex/windows-release-checksum-path` starts from current `master` at
`5cc7534`. Release run 31317909983 built and uploaded the exact five-file
3.1.1 handoff, then failed safely before attestation with `release checksum
manifest digest mismatch`; publication was skipped and no `v3.1.1` tag or
release exists.

The downloaded manifest is intact and hashes to the expected
`cef974c759a85c44a9d99d8f03408089e05cf053047060f31bf57017585d0b87`.
Git Bash reproduces the root cause: GNU `sha256sum` prefixes `\` when printing
an absolute Windows filename containing backslashes, so `awk` returns a
65-character escaped field. The same defect affects both artifact-consumer
checks and stored-release ZIP verification.

The implemented fix hashes from each containing directory with relative
filenames in both artifact consumers and stored-release ZIP verification. It
preserves the exact inventory, checksum, permission, attestation,
publication-order, and stored-byte gates. A focused regression failed twice
against the absolute-path commands and all seven workflow contracts pass after
the three substitutions.

Fresh validation: 110 unit tests pass with the three existing platform skips;
Ruff, bundled-wheel verification, and `git diff --check` pass. A Git Bash
reproduction against the failed run's downloaded artifact proves both old
absolute-path commands return a leading `\` and length 65, while both new
relative-path commands return the unchanged 64-hex manifest and ZIP digests.

After merge, start a new non-dry-run 3.1.1 dispatch from protected `master`.
That is the hosted acceptance test for the corrected attestation and
publication jobs; rerunning 31317909983 would execute its old commit. The
design and plan remain in `docs/superpowers/` only until this milestone's final
commit, then Git history retains them.

## Completed release-attestation branch

`codex/cats-update-policy-3.1.1` starts from merged `master` at `441a93c`.
The requested scope is to make normal CI consume new upstream CATS releases
through attestation rather than release pinning, make Material Combiner publish
only attested release archives, then bump Material Combiner to 3.1.1. The
approved combined design and test-first implementation plan were committed as
`be69387` and expanded in `8045189`; the final-tree copies are removed at the
completed milestone boundary and remain recoverable from Git history.
Production implementation and hosted acceptance are complete.

Post-merge CI run 31284931104 failed on Windows, Linux, and macOS only at
`Fetch and verify CATS`; every preceding source, package, atlas, wheel, and
static check passed. The committed CATS reference describes
`v5.2.0-alpha.1`, while GitHub's mutable latest-release endpoint began serving
the published, non-prerelease `v5.2.1` release during the merge. GitHub's
reported asset size and SHA-256 match the values downloaded by all three CI
jobs. The 5.2.1 asset is the installable extension ZIP directly rather than a
wrapper, a shape the current fetcher already supports.

Root cause: normal CI combines an immutable strict reference with a mutable
`releases/latest` lookup. CATS 5.2.2 now has a successful public release whose
workflow generated a GitHub/Sigstore provenance bundle for the exact extension
ZIP. Alpha Material Separator 1.3.1 independently demonstrates the same
producer-side build/attest/publish pattern.

The approved consumer policy commits no CATS version, tag, commit, size, hash,
minimum version, or signer-workflow digest. Material Combiner accepts the
latest final release only when `gh attestation verify` proves the exact CATS
repository, workflow certificate identity, `main` ref, dynamically resolved
release commit, and GitHub-hosted runner origin. Existing bounded acquisition and manifest
identity checks remain, and the unchanged Blender checkpoint decides API
compatibility. CATS and Alpha Material Separator receive no changes because
Material Combiner is optional and neither producer should depend on it.

The approved producer policy adapts Alpha Material Separator's demonstrated
least-privilege handoff to Material Combiner's four release ZIPs. A read-only
package job builds and validates the exact release files once and uploads them
with `SHA256SUMS.txt`; an isolated OIDC job downloads and verifies that exact
current-run artifact and attests all four ZIPs; only a dependent protected job
may write the draft release, re-download and rehash its stored bytes, and make
it public. Dry runs preserve build, validation, checksum, and inspectable
artifact coverage but deliberately create neither public attestations nor
releases. CATS and Alpha Material Separator workflows remain unchanged.

Draft PR 18 is open at
`https://github.com/Alrauna/material-combiner-addon/pull/18`. Hosted run
31316520767 passed every pre-CATS step on all three platforms, then failed at
the CATS fetch with `Error: verifying with issuer "sigstore.dev"`. The same
failure reproduced locally only when `--signer-workflow` was present; repository,
source-ref, source-digest, and hosted-runner constraints each passed alone.
Verified JSON shows GitHub issued the exact certificate SAN with the workflow
space percent-encoded as `Cats%20Tests.yml`. Replacing the brittle matcher with
`--cert-identity` for that exact SAN preserves the official verifier and all
other approved constraints. Corrected PR run 31317137520 then passed the full
Windows, Linux, and macOS matrix; both CodeQL analyses also passed.

Planning artifacts were committed as `be69387` and expanded for producer-side
attestation in `8045189`. The no-pin CATS consumer is committed as `06c4d45`:
36 focused tests pass for moving release metadata, the exact official
`gh attestation verify` argument policy, arbitrary future versions,
attestation-before-ZIP parsing, non-bypassable provenance and transport-size
failures, dynamic tag/name/manifest agreement, bounds, token isolation,
same-file hashes, and explicitly unattested local archives. Obsolete snapshot
assertions were replaced only where a committed release pin no longer exists.

The Material Combiner producer pipeline is committed as `f30733d`. A new
workflow contract suite proves the package/attestation/publish dependency,
least-privilege permissions, exact five-file current-run handoff, checksum
manifest binding, SHA-pinned official action, dry-run boundary, and publication
ordering. Those contracts plus the existing release, DNS-parser, three-resolver
consensus, and committed Blender checksum-pin tests pass: 42 tests total.
Focused Ruff checks pass. The manifest and development target are now 3.1.1;
local and hosted preservation validation is recorded below.

Fresh local validation after all implementation commits:

- `python -m unittest discover -s tests/unit -p "test_*.py"`: 109 tests
  passed with the same three expected Windows skips for POSIX display handling.
- Repository-wide Ruff and `git diff --check` passed. All three bundled Pillow
  wheels passed hash, platform, metadata, license, and manifest verification.
- Blender 5.2 validated `addon/` and a newly built
  `shotariyas_material_combiner-3.1.1.zip`. The ignored package contains 62
  entries, required runtime metadata and icons, all three reviewed wheels, and
  no tests, caches, local references, assessment output, logs, or bytecode.
- Seven isolated source suites passed: public API, UI, atomic lifecycle,
  preflight failures, dependency absence, atlas workflows, and Windows
  long-path atlas workflows. Three installed-package suites passed: bundled
  dependency, public API, and atlas workflows.
- The corrected live strict CATS 5.2.2 fetch verified the exact certificate
  identity and release commit `a35128c74e39ad0d81890af084d7cf56c5e38f58`
  before ZIP parsing. The attested asset and normalized extension both hash to
  `b837de71f944cc6a78be315058096588d7c337ea5472b8d732d5b3ec6822e189`.
  The unchanged Blender 5.2 CATS integration, restart, and uninstall checkpoint
  passed against those exact bytes.
- Corrected PR run 31317137520 passed Windows, Linux, and macOS, including the
  attested CATS fetch and unchanged checkpoint on every platform. Linux also
  passed the foreground atlas undo/repeatability suite. CodeQL passed for both
  Python and Actions.
- Non-publishing release dry run 31317244348 passed all three platform gates,
  built and validated the four 3.1.1 ZIPs, generated `SHA256SUMS.txt`, and
  uploaded the exact five-file handoff. An independent download confirmed the
  inventory and all four checksums. Attestation and publication stayed skipped
  as required for dry runs.
- GitHub reports Node.js 20 deprecation warnings for the currently SHA-pinned
  `actions/upload-artifact` revision. This did not affect validation and is a
  future action-maintenance topic, not part of this security branch.

The complete branch diff contains
only the approved attestation policy, workflow, tests, version metadata, and
documentation. No extension public API, operator, RNA, registration, package
layout, platform, wheel, atlas, or CATS checkpoint contract changed.

Recommended next action: review and merge draft PR 18. Do not dispatch the real
3.1.1 release until this branch lands on protected `master`; the public release
dispatch is the first authorized execution of the attestation and publication
jobs.

## Completed security-hardening branch

`codex/security-hardening` is complete and ready for review/PR preparation.
It preserves the hand-written Quad9 DNS-over-TLS parser as an intentional
security control alongside the runner resolver, Cloudflare DNS-over-HTTPS,
three-way checksum consensus, and the committed checksum pin. `AGENTS.md` now
protects that design from compatibility-neutral cleanup.

The branch also:

- makes CATS tag, name, size, hash, extension ID, and extension version drift
  fail closed by default while retaining `--strict` and adding the explicit
  local-only `--allow-drift` escape hatch;
- bounds CATS API responses, release downloads, and extracted inner archives,
  streams downloads without forwarding the API token, and removes partial
  output on failure;
- requires the existing `smc.browser` operator to receive a complete HTTPS URL
  without credentials, whitespace, control characters, a missing host, or an
  invalid port; and
- preserves extension API contracts, manifest and dependency metadata, CATS
  integration identifiers, atlas behavior, packer behavior, updater
  properties, and the CI resolver implementation.

Validation on Windows with Blender 5.2.0 LTS:

- 90 unit tests passed with 3 expected skips; repository-wide Ruff and
  `git diff --check` passed.
- All three bundled Pillow wheels passed hash, platform, metadata, license,
  and manifest verification.
- Seven isolated source suites passed: public API, UI/browser, atomic
  lifecycle, preflight failures, dependency absence, atlas workflows, and
  Windows long-path atlas workflows.
- Blender validated the source and a newly built package. Inspection found 62
  package entries, all three pinned wheels, all required runtime metadata, and
  no tests, caches, local references, assessment output, logs, or bytecode.
- Three installed-package suites passed: bundled dependency, public API, and
  atlas workflows.
- A live strict CATS fetch matched the pinned release tag, asset name, both
  sizes, both SHA-256 hashes, extension ID, and extension version. The CATS
  integration, restart, and uninstall checkpoint passed.
- The complete branch received an inline correctness and overengineering
  review with no accepted findings. Protected contracts, behavioral evidence,
  manifest, dependency lock, packer, updater properties, and resolver code
  have no diff.

Windows cannot supply the foreground atlas undo/repeatability gate. Linux
foreground coverage and the Windows/Linux/macOS CI matrix remain required
before merge. No push or pull request has been performed.

Recommended next action: review and publish this branch. After it merges,
start a new chat and a separate branch for compatibility-safe simplification;
do not mix that work into this completed security branch.

## State

The CI/CD and hardening milestone is complete. `master` carries the `addon/`
layout, runtime support for Windows x64, Linux x64 and macOS arm64,
`tests/run_tests.py`, `tools/fetch_cats.py`, and a three-platform CI workflow
with a verified release job.

**v3.1.0 is released.** It was published by the release workflow, which
created the tag, uploaded four archives and `SHA256SUMS.txt`, re-downloaded
them, verified every hash, and only then undrafted. The full publishing path
is therefore proven, not theoretical.

## Releasing the next version

Bump `version` in `addon/blender_manifest.toml` first; the gate refuses a
version the manifest does not declare, and the tag check refuses one that
already exists.

Then rehearse. Run the CI workflow with `release` set to the new version and
`dry_run` ticked. The read-only package job fetches the exact commit, rebuilds,
validates every archive, computes checksums, and uploads the exact five-file
handoff artifact while printing its hashes in the run summary. No attestation,
tag, or release is created. A dry run may be started from any branch, so the
packaging path can be exercised without cutting anything.

Then run it again with `dry_run` unticked, on `master`, to publish.

The predecessor workflow's dry-run and publishing paths produced v3.1.0. The
new privilege-separated attestation path still requires hosted acceptance for
3.1.1 before it can be described as proven.

Leaving `release` empty runs validation only.

For a real public-master dispatch, an isolated OIDC job downloads the current-
run artifact, rejects missing or extra files, verifies the checksum manifest
and all four ZIPs, and attests the ZIPs with the pinned official GitHub action.
Only the dependent protected publish job has release-write permission. It
independently verifies the same artifact, refuses an existing tag or release,
creates a draft, uploads the four ZIPs and `SHA256SUMS.txt`, downloads what the
release actually stored, verifies every hash, and only then publishes. A failed
attestation prevents publication; a draft that fails stored-byte verification
stays a draft.

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
- Remote CATS downloads require the approved GitHub attestation and dynamic
  tag/name/manifest agreement. `--allow-drift` cannot bypass those checks.
  Local `--archive` inspection is explicitly unattested, and strict local mode
  fails rather than claiming provenance.

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
