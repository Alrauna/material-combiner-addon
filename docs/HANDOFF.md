# Handoff

## State

`master` at `fcf3a1a` has the `addon/` layout and Linux x64 runtime support.
Version 3.1.0 is in the manifest; nothing is tagged and no GitHub release
exists.

Branch `feat/python-test-runner` is workstream 2b. The milestone plan is in
`docs/superpowers/plans/ci-cd-hardening.md`.

## This turn

`tests/run_tests.py` replaces `run_blender_tests.ps1`, `run_package_test.ps1`,
and `run_checkpoint_test.ps1` with one cross-platform runner. Stdlib only, no
dependencies.

Three modes: `source` copies `addon/` into an isolated profile, `package`
installs a built ZIP, `checkpoint` installs Material Combiner beside CATS and
runs the integration, restart, and uninstall sequence.

Behaviour preserved from the PowerShell runners: isolated profile with every
Blender, HOME, APPDATA, cache, and temp path redirected; `PYTHONNOUSERSITE`
set and `PYTHONPATH` dropped; per-step stdout and stderr logs; failure when a
suite produces no result file; the Windows `subst` alias, now optional and
skipped on other platforms; and `--exclude-wheel`, `--foreground`, and
`--pillow-root`.

The CATS hash check became `--cats-sha256`. It was a hardcoded constant in the
PowerShell script; it is now supplied by the caller and still refuses to run
on mismatch.

`tests/unit/test_run_tests.py` asserts that every redirected path stays inside
the work directory, that user site is disabled and `PYTHONPATH` dropped, and
that a bad CATS hash refuses to run.

Verified on both platforms. Windows: unit 24/24, all six source suites
including foreground undo, three package suites, full CATS checkpoint. Linux:
unit 24/24 with 4 Windows-only path tests skipped, all six source suites, plus
a Linux build, validate, and package run.

## Next

- Workstream 3: CATS download. The archive published at
  `Alrauna/Cats-Blender-Plugin` (`v5.2.0-alpha.1`,
  `cats-blender-plugin-5.2.0-alpha.1.zip`, 1,282,884 bytes) is a different
  artifact from the locally pinned `Cats-Blender-Plugin-5.2.0-795d323.zip`
  (1,304,732 bytes, `14EBB594...`). Re-pinning means re-baselining CATS
  evidence against a build never tested here. Approved behaviour: verify the
  hash but warn rather than fail, written so promoting it to a hard failure is
  a one-line change.
- Workstream 4: CI. Both platforms are now runnable, so the matrix can be real.
  Runner temp paths are short, so the MAX_PATH defect class is still not
  exercised; covering it needs a deliberately long work directory.
- Workstream 5: release workflow and branch protection.
- The universal ZIP is 14.2 MB because it carries both wheels.
  `--split-platforms` would produce roughly 7 MB per platform but changes
  release artifact naming. Decide during the release workstream.
- Nothing is tagged at 3.1.0.
