# Handoff

## Active agent-policy simplification branch

`codex/simplify-agents-policy` starts from merged `master` at `5cc7534`.
Its objective is to replace the contradictory, framework-coupled root
`AGENTS.md` with a compact, portable policy without changing product behavior.

The isolated baseline was clean: 109 unit tests passed with the same three
expected skips. The RED policy check then demonstrated the original file's
24,852-byte size, mandatory framework coupling, implicit commit requirement,
conflicting deletion/history rules, missing Codex-managed worktree guidance,
and missing CATS rolling-checkpoint exception.

The approved rewrite is complete and reviewed. `AGENTS.md` is 11,722 bytes,
down from 24,852, and preserves the checksum security design, package
boundary, dependency model, compatibility contracts, validation requirements,
protected material, and publication controls. Workflow, Git authorization,
and handoff rules are now risk-based and unambiguous.

The GREEN policy gate, focused invariant/scope/secret-path review, and
`git diff --check` pass. The post-change unit run passed all 109 tests with the
same three expected skips. Blender, package, wheel, and CATS runs were not
repeated because no runtime, test, manifest, dependency, contract, licensing,
attribution, or release input changed.

The approved implementation plan is retained in branch history at `0779411`
and removed from the completed tree. Draft PR 20 is open at
`https://github.com/Alrauna/material-combiner-addon/pull/20`. Recommended next
action: review the PR and its hosted checks.

## Repository and release state

`master` carries the `addon/` package layout, Material Combiner 3.1.1
development metadata, Blender 5.2 support for Windows x64, Linux x64, and
macOS arm64, the isolated test runner, dynamic attested CATS acquisition, and
the privilege-separated release workflow.

Version 3.1.0 is the latest published Material Combiner release. The 3.1.1
release must not be dispatched until its intended source is on protected
`master` and the release authorization is explicit.

The hosted 3.1.1 acceptance evidence on the merged attestation work includes:

- CI run 31317137520 passed Windows, Linux, and macOS plus both CodeQL
  analyses, including attested CATS acquisition and the unchanged checkpoint.
- Dry run 31317244348 built and validated the four 3.1.1 archives, generated
  `SHA256SUMS.txt`, and verified the exact five-file handoff without creating
  an attestation, tag, or release.
- Local validation passed 109 unit tests, all three reviewed Pillow wheel
  checks, Blender source/package validation, source and installed-package
  suites, Windows long-path coverage, and the live CATS 5.2.2 checkpoint.

`master` requires these status checks:

- `CI / Windows — Blender 5.2`
- `CI / Linux — Blender 5.2`
- `CI / macOS — Blender 5.2`
- `Analyze (python)`
- `Analyze (actions)`

Admins are included; force pushes, branch deletion, and direct pushes are
blocked. Do not require a context named `CodeQL`: GitHub reports the required
checks by analyzed language.

## Release procedure

1. Bump `version` in `addon/blender_manifest.toml`; the release gate rejects a
   different, missing, or already published version.
2. Dispatch the release workflow with that version and `dry_run` enabled. The
   read-only package job builds, validates, hashes, and uploads the exact four
   archives plus `SHA256SUMS.txt`. It creates no public attestation, tag, or
   release.
3. After reviewing the dry run, dispatch the same version from protected
   `master` with `dry_run` disabled. The isolated OIDC job verifies the handoff
   and attests all four archives before the protected publish job can create a
   draft, upload, re-download, rehash, and publish it.

Leaving the release version empty runs validation only.

## Known validation gaps

- The `_load_lock` long-path defect has not been proven to reproduce on a
  Windows runner with long paths enabled. The `_inside` regression is proven.
- Atlas undo and repeatability runs in a foreground Blender context on Linux
  under xvfb. Windows and macOS hosted runners have no supported foreground
  window-server path for this gate.
- macOS means Apple Silicon. Blender 5.2 has no macOS Intel build; the package
  also does not target windows-arm64.
- Remote CATS acquisition intentionally follows the latest final release after
  exact GitHub attestation, tag/name/manifest agreement, and transport bounds.
  It is a rolling compatibility checkpoint, not a pinned deterministic input.

## Maintenance invariants

- The hand-written Quad9 DNS-over-TLS client in `tools/ci.py` is deliberate.
  Keep it independent from the runner resolver and Cloudflare DNS-over-HTTPS;
  all three manifests must agree with the committed checksum pin.
- Atlas goldens compare decoded pixels rather than PNG bytes because platform
  zlib implementations produce different compressed files.
- `SPLIT_PLATFORMS` in `tools/ci.py` must match the manifest platform list.
  Release preparation rejects missing or unexpected platform archives.
- Remote CATS downloads require approved GitHub attestation. Local `--archive`
  inspection is explicitly unattested, and strict local mode fails rather than
  claiming provenance.
