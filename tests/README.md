# Material Combiner compatibility tests

These tests preserve the public and behavioral contract characterized before
the Blender 5.2 implementation work began.

`tests/run_tests.py` runs every Blender suite on Windows and Linux. It builds
an isolated Blender profile under a caller-supplied work directory, copies the
extension source or installs a built package into it, disables the normal
Python user site, and invokes Blender with factory startup and auto-execution
disabled. The user's real Blender configuration is never touched.

Put work directories outside the tracked source, such as under the operating
system temporary directory.

## Modes

Run the suites against the `addon/` source:

```
python tests/run_tests.py \
  --blender /path/to/blender --work /tmp/smc-work \
  source --script tests/blender/verify_public_api.py --result public_api.json
```

Run them against a built package:

```
python tests/run_tests.py \
  --blender /path/to/blender --work /tmp/smc-work \
  package --package .packaged-releases/<id>-<version>.zip \
  --script tests/blender/verify_packaged_dependency.py --result dep.json
```

Run the CATS integration, restart, and uninstall checkpoint:

```
python tests/run_tests.py \
  --blender /path/to/blender --work /tmp/smc-work \
  checkpoint --package .packaged-releases/<id>-<version>.zip \
  --cats /path/to/cats.zip --cats-sha256 <sha256>
```

`--cats-sha256` is optional but should always be supplied; the run is refused
if the archive does not match.

## Options

- `--exclude-wheel` (source) drops the bundled wheels, for the
  dependency-absent checks.
- `--foreground` (source) runs Blender with a window, which the atlas undo and
  repeatability check requires. Ordinary suites stay in background mode, where
  that check reports that it needs a foreground context.
- `--pillow-root` (source) is only for the approved Stage 0 controlled
  dependency path. Package runs must omit it and exercise Blender's
  extension-managed wheel path instead.
- `--drive-letter` / `--no-drive-alias` control the Windows `subst` alias that
  keeps runtime paths short. Ignored on other platforms.

## Contracts

`public_api_contract.json` is the compatibility gate for registered classes,
operators, RNA properties, CATS-facing Python symbols, naming behavior, and
saved-file identifiers. `stage0_behavior.json` records golden outputs and
confirmed historical defects. Corrected expectations belong in
`corrected_behavior.json`; retain the old evidence and add a regression test
for every corrected behavior.

Atlas goldens assert decoded pixel content rather than PNG file bytes. Pillow
links zlib-ng on Windows and stock zlib on Linux, so identical images produce
different files. The per-platform file hashes are recorded as evidence only.
