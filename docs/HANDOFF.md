# Handoff

## State

`master` at `e87aab8` has the `addon/` layout. Version 3.1.0 is in the
manifest; nothing is tagged and no GitHub release exists.

Branch `feat/linux-support` is the runtime half of workstream 2. The milestone
plan is in `docs/superpowers/plans/ci-cd-hardening.md`.

## This turn

Linux x64 is now a supported runtime platform, validated on real Linux
(WSL Ubuntu 24.04, Blender 5.2.0 LTS downloaded and hash-verified against the
value the separator repository pins).

- The manylinux Pillow 12.3.0 wheel is committed and hash-verified.
- `dependencies.lock.json` is schema 2: one entry per platform, each carrying
  its own `platform_tag`, `native_module`, and license hash. The two wheels'
  license files genuinely differ, because each bundles the notices of the
  native libraries built into it.
- `dependencies.py` resolves the current platform from a table instead of
  testing `sys.platform == "win32"`, and `_load_lock` selects the entry for
  that platform.
- `tools/verify_dependency_wheel.py` verifies every wheel in the lock and
  expands compressed tag sets such as
  `manylinux_2_27_x86_64.manylinux_2_28_x86_64` into one expected `Tag:` row
  each.

### Atlas goldens now assert pixel content

Measured on both platforms: dimensions and decoded pixels are identical, PNG
file bytes are not. Windows Pillow links zlib-ng 1.3.1, Linux links stock zlib
1.3.1, so the same image compresses differently.

The suite now asserts a hash of `Image.tobytes()`. The previous Windows file
hashes are retained in the contracts as evidence, the Linux file hash is
recorded alongside, and `corrected_behavior.json` carries an
`atlas_golden_comparison` block explaining why. Approved before the change;
the contracts were not silently rewritten to make Linux pass.

## Next

- **Workstream 2 is not finished.** The cross-platform Python test runner is
  still missing. Linux was validated with throwaway scratchpad scripts that
  are not committed, so there is currently no reproducible way to run the
  suites on Linux. `subst` has no POSIX equivalent, so the three PowerShell
  runners need replacing rather than translating. CI cannot cover Linux until
  this exists.
- The universal ZIP is now 14.2 MB because it carries both wheels. Blender
  supports `--split-platforms` to emit one archive per platform at roughly
  7 MB each. That changes the release artifact naming, so it is a decision for
  the release workstream, not an assumption.
- `undo_repeatability` still needs foreground Blender and self-skips in
  background mode on both platforms.
- Nothing is tagged at 3.1.0.
- The CATS archive published at `Alrauna/Cats-Blender-Plugin` is a different
  artifact from the one `tests/run_checkpoint_test.ps1` hash-pins. Re-pinning
  is workstream 3.
