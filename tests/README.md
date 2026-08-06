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

`tools/fetch_cats.py` produces that archive:

```
python tools/fetch_cats.py --output-dir /tmp/cats
```

It resolves the latest release of the repository recorded in
`tools/cats_reference.json`, downloads the asset, and unwraps it. The
published asset is a wrapper whose single entry is the installable extension
ZIP, which Blender cannot install directly. The tool prints the unwrapped
archive path and its SHA-256 for the runner to consume.

Hash or tag drift is reported as a warning and does not fail, because the CATS
repository has not yet adopted the same release automation. Pass `--strict`,
or set `HASH_MISMATCH_IS_FATAL` in the tool, to make drift blocking. An
unexpected extension id always fails, since the checkpoint could not enable it
anyway. Use `--archive` to run offline from a local copy.

## Options

- `--exclude-wheel` (source) drops the bundled wheels, for the
  dependency-absent checks.
- `--foreground` (source) runs Blender with a window, which the atlas undo and
  repeatability check requires. Ordinary suites stay in background mode, where
  that check reports that it needs a foreground context instead of running.
  On Linux without a display the runner wraps Blender in `xvfb-run`; if xvfb
  is not installed it refuses to start rather than quietly skipping the check.
- `--long-path` (source) nests the work directory so that files inside the
  profile exceed the Windows MAX_PATH limit while the extension root stays
  below it. That mix is what the dependency-trust regression needs; see below.
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

## Long-path coverage

`--long-path` exists to regression-test the Windows extended-length path
handling in `addon/dependencies.py`. The window is narrow. `Path.resolve()`
keeps the `\\?\` prefix only when its result exceeds MAX_PATH, so the
extension root must stay below 260 characters, resolving to a plain path,
while files inside it exceed 260 and resolve with the prefix. Comparing those
two forms is what the dependency-trust check gets wrong without the fix.

Padding past 260 defeats the test: every path then carries the prefix, they
all agree, and the suite passes even with the fix reverted. This was confirmed
by reverting `_plain_path` and observing the run fail with "Pillow was loaded
from outside Material Combiner's managed extension environment" only in
long-path mode, and pass on a short path.

The companion defect in `_load_lock` does not reproduce on a machine with the
`LongPathsEnabled` registry setting, because plain reads past MAX_PATH succeed
there. It should reproduce on a runner without that setting. Do not assume a
green long-path run has covered it.
