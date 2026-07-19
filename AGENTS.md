# Project purpose

This repository contains Shotariya's Material Combiner, a Blender extension
for combining material textures into atlases to reduce draw calls.

The current development target is the alpha release for Blender 5.2 LTS on
Windows x64. The extension bundles Pillow through Blender's extension wheel
mechanism. Other Blender versions or platforms are not supported unless they
are separately validated and the manifest, dependency metadata, tests, and
documentation are updated.

Prepare changes for continued development and eventual GitHub publication.
Favor conservative, reviewable changes and preserve existing behavior unless
the task explicitly authorizes a change.

## Intended repository layout

The flat repository root is intentional. It is also the Blender extension
package root.

- `__init__.py`, `registration.py`, `dependencies*.py`, `extend_*.py`,
  `globs.py`, and `type_annotations.py`: root package and registration
  infrastructure.
- `operators/`: Blender operators. Its `combiner/` and `ui/` subpackages are
  intentional.
- `ui/`: Blender panels and menus. Do not merge it with `operators/ui/`; they
  serve different roles.
- `utils/`: image, material, object, texture, and atlas-packing utilities.
- `icons/`: runtime UI assets.
- `wheels/`: reviewed runtime wheels referenced by the Blender manifest.
- `tests/`: unit tests, Blender integration tests, behavioral evidence, and
  compatibility contracts.
- `tools/`: developer and dependency-validation utilities.
- `README.md`, `THIRD_PARTY.md`, and `tests/README.md`: project, dependency,
  and testing documentation.
- `blender_manifest.toml`, `dependencies.lock.json`, and `pyproject.toml`:
  package, dependency, and development metadata.
- `.github/`: GitHub issue and funding metadata.
- `.local-references/`: ignored, local-only external references.
- `.packaged-releases/`: ignored, local-only release packages and build
  output.
- `.codex-assessment/`, when present: generated migration and validation
  output. It is not source code and must not be committed unless the user
  explicitly selects a curated artifact.

Do not introduce another source wrapper or move runtime files under `src/`
unless a demonstrated Blender, import, packaging, or test failure requires it.

## Protected and local-only material

- Keep `.local-references`, `.packaged-releases`, and `.codex-assessment`
  protected by `.gitignore`.
- Do not read, publish, commit, quote, inventory, or otherwise reference the
  contents of `.local-references` without explicit user instruction.
- Do not treat external archives, extracted upstream projects, old builds,
  Blender assets, or packaged ZIP files as source-of-truth code unless
  explicitly instructed.
- Do not commit generated profiles, logs, atlases, temporary test output,
  caches, or `.codex-assessment` material.
- Do not replace or add bundled wheels without explicit scope. Any dependency
  change requires provenance, license, hash, ABI/platform, package, and
  runtime validation.
- Do not edit `.git/`, rewrite history, delete files, or remove branches.
- Do not change licensing, attribution, funding links, repository ownership
  metadata, or third-party notices without explicit approval.

If the origin or publication rights of an artifact are uncertain, keep it
local and ask before using or publishing it.

## Compatibility contracts

Preserve these interfaces unless the task explicitly authorizes a
compatibility change:

- Extension ID, name, version policy, platform declarations, and other public
  manifest metadata.
- Blender operator `bl_idname` values and registered class identifiers.
- RNA scene/material properties and saved-file identifiers.
- Importable module paths recorded in
  `tests/contracts/public_api_contract.json`.
- CATS-facing modules, symbols, UI integration, and operator calls in that
  contract.
- Registration, unregistration, reload, restart, and uninstall behavior.
- Existing behavioral evidence and golden outputs in
  `tests/contracts/stage0_behavior.json`.
- The bundled Pillow dependency model: no runtime downloads, pip installation,
  normal user-site injection, or modification of Blender's bundled Python.

A known defect may be corrected, but retain the earlier evidence and add a
regression test for the corrected behavior. Do not silently rewrite contracts
to make a failing change pass.

## Safe working procedure

1. Run `git status --short --untracked-files=all` before editing. Existing
   modifications belong to the user; preserve them and avoid unrelated files.
2. Inspect the relevant entry points, imports, tests, contracts, and manifest
   before changing code.
3. Make the smallest change that satisfies the task. Do not reorganize
   adjacent code or rename public symbols for neatness.
4. Keep imports, manifests, scripts, tests, documentation, and package paths
   synchronized when an authorized path change is unavoidable.
5. Use Git-aware moves for approved renames or moves. Never delete or discard
   material without explicit approval.
6. Keep tests isolated from the user's normal Blender profile. Use the supplied
   PowerShell runners and an external temporary work directory.
7. Review `git diff` and `git diff --check`, then rerun `git status --short`.
8. Do not commit, push, publish, tag, or create a release unless explicitly
   requested.

Do not overwrite a dirty file merely because its current contents differ from
`HEAD`.

## Validation

Choose tests proportionate to the change. Consult `tests/README.md` and the
runner parameters rather than assuming paths.

Baseline non-Blender checks:

```powershell
python -m unittest discover -s tests/unit -p "test_*.py"
python tools/verify_dependency_wheel.py
git diff --check
```

For add-on code, registration, UI, dependency, atlas, or compatibility
changes, use Blender 5.2 with the applicable scripts under `tests/`:

- `run_blender_tests.ps1` for source-tree public API, UI, lifecycle, preflight,
  dependency, and atlas checks.
- `run_package_test.ps1` for an installed extension package.
- `run_checkpoint_test.ps1` for approved CATS integration, restart, and
  uninstall checks.

Put test work directories outside tracked source, such as under the
operating-system temporary directory. Put intentional release ZIPs in
`.packaged-releases/`.

Every Blender extension build must be written to `.packaged-releases/` and
named `<id>-<version>-<git-short-hash>.zip`. Read `id` and `version` from
`blender_manifest.toml`; obtain `git-short-hash` from the local repository with
`git rev-parse --short HEAD`. Do not hardcode these values. If the worktree is
dirty, report that the hash identifies the base commit and that the archive
also contains uncommitted changes.

For packaging changes, validate both the source directory and built archive
with Blender's extension validation command. Inspect the resulting ZIP to
ensure required runtime files, the manifest, licenses, icons, dependency
metadata, and the pinned wheel are present and that tests, caches, local
references, and generated output are absent.

If Blender 5.2, an approved integration package, or another required
dependency is unavailable, report the unrun validation explicitly instead of
claiming success.

## Commit and publication safety

Commit only source, tests, intentional fixtures, project documentation,
reviewed metadata, and explicitly approved runtime dependencies.

Before any GitHub publication:

- Confirm `git status` does not include local references, generated assessment
  output, logs, profiles, atlases, or release ZIPs.
- Check changed documentation and configuration for absolute paths, usernames,
  credentials, tokens, and machine-specific settings.
- Revalidate third-party notices and dependency hashes.
- Confirm the package targets declared in `blender_manifest.toml` match what
  was actually tested.
- Treat claims about unvalidated platforms, Blender versions, or external
  integrations as uncertain and mark them "verify before changing."
