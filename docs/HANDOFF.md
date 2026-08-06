# Handoff

## State

`master` at `d1f00bd` has the `addon/` layout, Linux x64 runtime support, and
`tests/run_tests.py`. Version 3.1.0 is in the manifest; nothing is tagged and
no GitHub release exists.

Branch `feat/cats-fetch` is workstream 3. The milestone plan is in
`docs/superpowers/plans/ci-cd-hardening.md`.

## This turn

`tools/fetch_cats.py` resolves the latest release of the repository recorded
in `tools/cats_reference.json`, downloads the asset, unwraps it, and reports
drift.

The discrepancy flagged in earlier turns is resolved, and it was not a content
difference. **The published release asset is a wrapper: a ZIP whose single
entry is `cats_blender_plugin.zip`.** Blender installs the wrapper without
error but no `cats_blender_plugin` module ever exists, so the checkpoint
failed at `addon_enable` with "No module named". Unwrapped, the published
build passes the full checkpoint, so no CATS behavioural evidence needed
re-baselining.

Drift policy, as approved: hash or tag drift is a warning and does not fail.
`--strict`, or the `HASH_MISMATCH_IS_FATAL` constant, makes it blocking. An
unexpected extension id always fails, because the checkpoint could not enable
it anyway. `--archive` runs offline from a local copy, so
`.local-references` still works.

Verified: live fetch on Windows and Linux with no drift; the old locally
pinned archive correctly reported as drift and still exiting 0, then exiting 1
under `--strict`; and an end-to-end fetch feeding straight into a passing
checkpoint. Unit 32/32 on Windows, 32/32 on Linux with 4 Windows-only path
tests skipped.

## Next

- Workstream 4: CI. Everything it depends on now exists. Port `scripts/ci.py`
  from the separator repository, keeping the three-resolver checksum
  consensus. Jobs: unit, source suites, `extension validate` on `addon/`,
  build, package suites, and the CATS checkpoint via `tools/fetch_cats.py`.
- Workstream 5: release workflow and branch protection. Protection must come
  last, because required status checks reference job names that do not exist
  until CI is merged.
- Both previously open CI gaps are closed in the runner. `source --long-path`
  covers the extended-length path handling, proven by reverting `_plain_path`
  and watching only the long-path run fail. `source --foreground` now uses
  `xvfb-run` on display-less Linux and refuses to start if xvfb is missing,
  so the undo check cannot silently skip.
- Two residual limits, both stated in `tests/README.md`: the `_load_lock`
  defect does not reproduce on a machine with `LongPathsEnabled` set, so a
  green long-path run there does not cover it; and the xvfb wrapper itself
  could not be executed locally because installing xvfb needs sudo. Its logic
  is unit-tested and the no-display refusal is verified, but the first real
  xvfb run will happen on CI.
- The universal ZIP is 14.2 MB because it carries both wheels.
  `--split-platforms` would give roughly 7 MB per platform but changes release
  artifact naming. Decide during the release workstream.
- Nothing is tagged at 3.1.0.
