# Handoff

## State

`master` at `89469d0` has the `addon/` layout, Linux x64 runtime support,
`tests/run_tests.py`, and `tools/fetch_cats.py`. Version 3.1.0 is in the
manifest; nothing is tagged and no GitHub release exists.

Branch `feat/ci-workflow` is workstream 4. The milestone plan is in
`docs/superpowers/plans/ci-cd-hardening.md`.

## This turn

`.github/workflows/ci.yml` and `tools/ci.py`. Windows and Linux matrix,
`fail-fast: false`, `permissions: contents: read`, both actions pinned by
commit and confirmed to be release tags (checkout v7.0.1, upload-artifact
v4.6.2).

Blender is downloaded rather than trusted. The official checksum manifest is
fetched over three independent resolvers, all three must return byte-identical
content, and the agreed manifest must match a hash committed in `tools/ci.py`.
Both committed hashes were verified against the published manifest.

Three resolution paths, matching the separator: system DNS, Cloudflare over
DoH through curl, and Quad9 over DNS-over-TLS spoken directly and handed to
curl with `--resolve`.

The hand-rolled DNS-over-TLS client is an intentional security decision and
must not be replaced with curl's DoH client. Routing all three paths through
one resolver implementation would defeat the point of having three. A revision
did replace it, wrongly concluding Quad9 was unreachable after testing its DoH
endpoint rather than DNS-over-TLS on port 853; the DoT path resolves fine. The
parser now has unit tests covering its rejection paths.

Both former CI gaps are covered: Linux installs xvfb so the foreground atlas
undo check really runs, and Windows runs the long-path suite.

### First CI run

Linux passed end to end on the first attempt, including xvfb carrying the
foreground atlas suite and the `--strict` CATS checkpoint.

Windows hung. `--foreground` on a `windows-2025` runner blocks forever,
because the runner has no interactive desktop for Blender's window; the job
sat on the atlas suite for 25 minutes until it was cancelled. CI now runs the
atlas suite in foreground on Linux and in background on Windows, so the undo
and repeatability check is covered on Linux only. Step timeouts were added so
a future hang fails in 20 minutes instead of 60, and results now upload on
success as well as failure, because a green run otherwise cannot show whether
the undo check ran or reported itself skipped.

The second run passed on both platforms. The uploaded artifacts confirm what
a green tick alone could not:

- Linux `work-atlas` recorded a real `undo_repeatability` result, so xvfb
  genuinely carried the foreground check rather than it skipping quietly.
- Windows `work-atlas` recorded `requires foreground Blender context`, which
  is the intended behaviour there.
- The Windows long-path suite produced results under a padded directory, so
  `subst` does work on a `windows-2025` runner.

## Next

- Workstream 5: release workflow and branch protection. The status check
  names to require are `CI / Windows — Blender 5.2` and
  `CI / Linux — Blender 5.2`.
- Still unknown: whether the `_load_lock` long-path defect reproduces on the
  Windows runner. The long-path suite passes there with the fix in place, but
  nothing has shown it would fail without it, so treat that half as
  uncovered. Only the `_inside` defect has a demonstrated regression.
- Workstream 5: release workflow and branch protection. Protection must come
  last, because required status checks reference the job names this workflow
  introduces: `CI / Windows — Blender 5.2` and `CI / Linux — Blender 5.2`.
- The universal ZIP is 14.2 MB because it carries both wheels.
  `--split-platforms` would give roughly 7 MB per platform but changes release
  artifact naming. Decide during the release workstream.
- Nothing is tagged at 3.1.0.
