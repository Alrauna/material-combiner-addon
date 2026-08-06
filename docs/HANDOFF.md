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

The separator's `ci.py` hand-rolls a DNS-over-TLS client against Quad9, about
150 lines of DNS wire-format parsing. This uses curl's `--doh-url` against two
DoH providers for the same property. Quad9 was tried first and could not
resolve through curl's DoH client on this network, so Google DNS is the third
resolver; only endpoints confirmed reachable belong there, because an
unreachable resolver fails the build.

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

## Next

- **The revised workflow has not been observed yet.** Windows in particular
  got no further than the atlas suite on the first run, so everything after
  it on that platform — long-path, build, package suites, CATS checkpoint —
  is still unproven there. Watch the next run.
- Still unknown on Windows: whether `subst` works on the runner, and whether
  the `_load_lock` long-path defect reproduces there, since it does not on a
  machine with `LongPathsEnabled` set.
- Workstream 5: release workflow and branch protection. Protection must come
  last, because required status checks reference the job names this workflow
  introduces: `CI / Windows — Blender 5.2` and `CI / Linux — Blender 5.2`.
- The universal ZIP is 14.2 MB because it carries both wheels.
  `--split-platforms` would give roughly 7 MB per platform but changes release
  artifact naming. Decide during the release workstream.
- Nothing is tagged at 3.1.0.
