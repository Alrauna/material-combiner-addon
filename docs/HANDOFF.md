# Handoff

## State

`master` at `ec9d604` carries the Blender 5.2 migration and the 3.1.0 release.
Version 3.1.0 is in the manifest but nothing is tagged and no GitHub release
exists.

Branch `refactor/addon-subdir` is workstream 1 of the CI/CD and hardening
milestone. The approved plan for the whole milestone is in
`docs/superpowers/plans/ci-cd-hardening.md`.

## This turn

Moved the extension package under `addon/`, which is now the only directory
that ships. Everything else is development material.

The substantive change is `tests/run_blender_tests.ps1`. It used to copy the
entire repository into the isolated profile and run the test script from
inside that copy. With `tests/` outside `addon/` that no longer works, so it
now copies only `addon/` and runs tests from the repository, matching what
`run_package_test.ps1` already did. `SMC_TEST_CONTRACT` points at the
repository contracts. The local-only exclusion list added earlier is gone;
those directories are no longer inside the copied tree.

`paths_exclude_pattern` shrank from 44 entries to 5. Most of it existed to
keep development material out of a package rooted at the repository.

Package contents changed deliberately. `LICENSE`, `README.md`,
`pyproject.toml`, and `tools/verify_dependency_wheel.py` no longer ship.
`THIRD_PARTY.md` moved into `addon/` so the distributed extension keeps its
Pillow attribution notice.

## Next

- Workstream 2: Linux support. See the plan. The riskiest unknown is whether
  atlas PNG output on Linux matches the existing `sha256` goldens.
- Nothing is tagged at 3.1.0.
- `AGENTS.md` still carries trailing whitespace on one line from an earlier
  maintainer edit, which makes repo-wide `git diff --check` return non-zero.
- The CATS archive published at `Alrauna/Cats-Blender-Plugin` is a different
  artifact from the one `tests/run_checkpoint_test.ps1` hash-pins. Re-pinning
  is part of workstream 3.
