# Project purpose

This repository contains Shotariya's Material Combiner, a Blender extension
for combining material textures into atlases to reduce draw calls.

The current development target is the 3.1.0 release for Blender 5.2 LTS on
Windows x64 and Linux x64. The extension bundles one reviewed Pillow wheel per
platform through Blender's extension wheel mechanism. Other Blender versions
or platforms are not supported unless they are separately validated and the
manifest, dependency metadata, tests, and documentation are updated.

Atlas goldens assert decoded pixel content, not PNG file bytes. Pillow links
zlib-ng on Windows and stock zlib on Linux, so identical images compress to
different files. Do not reintroduce file-hash assertions for atlas output.

Prepare changes for continued development and eventual GitHub publication.
Favor conservative, reviewable changes and preserve existing behavior unless
the task explicitly authorizes a change.

## Intended repository layout

`addon/` is the Blender extension package root and the only directory that
ships to users. Everything outside it is development material.

Inside `addon/`:

- `__init__.py`, `registration.py`, `dependencies*.py`, `extend_*.py`,
  `globs.py`, and `type_annotations.py`: package and registration
  infrastructure.
- `operators/`: Blender operators. Its `combiner/` and `ui/` subpackages are
  intentional.
- `ui/`: Blender panels and menus. Do not merge it with `operators/ui/`; they
  serve different roles.
- `utils/`: image, material, object, texture, and atlas-packing utilities.
- `icons/`: runtime UI assets.
- `wheels/`: reviewed runtime wheels referenced by the Blender manifest.
- `blender_manifest.toml` and `dependencies.lock.json`: package and dependency
  metadata.
- `THIRD_PARTY.md`: bundled-dependency attribution. It is packaged
  deliberately, so the distributed extension carries its own notice for the
  bundled wheel.

Outside `addon/`:

- `tests/`: unit tests, Blender integration tests, behavioral evidence, and
  compatibility contracts.
- `tools/`: developer and dependency-validation utilities.
- `docs/`: project documentation and handoff notes.
- `README.md`, `LICENSE`, and `tests/README.md`: project, licensing, and
  testing documentation. Neither is packaged; the manifest declares the
  license with an SPDX expression.
- `pyproject.toml`: development tooling metadata.
- `.github/`: GitHub issue metadata and workflows.
- `.local-references/`: ignored, local-only external references.
- `.packaged-releases/`: ignored, local-only release packages and build
  output.
- `.codex-assessment/`, when present: generated migration and validation
  output. It is not source code and must not be committed unless the user
  explicitly selects a curated artifact.

Do not move runtime files back to the repository root or introduce a further
wrapper inside `addon/` unless a demonstrated Blender, import, packaging, or
test failure requires it. Build the package from `addon/`, never from the
repository root.

## Development approach

- Superpowers owns the development lifecycle. Use its phases in this order when
  they apply: investigate, design, obtain design approval, write a test-first
  plan, obtain plan approval, implement, review, verify, and commit.
- Begin every defect or unexpected result with systematic debugging. Establish
  a reproduction and root cause before proposing or editing production code.
- Treat new or changed behavior—including UX, API, architecture, cache,
  assignment, material resolution, and performance behavior—as design work.
  Use brainstorming, present the design, and obtain user approval before
  production edits.
- Convert an approved design or other multi-step production request into a
  written implementation plan with explicit files, RED/GREEN tests, validation,
  preservation checks, and commit boundaries. Obtain user approval before
  execution. A plan may be concise for a narrow change, but a small expected
  diff is not a reason to omit it.
- Design specs and implementation plans live in `docs/superpowers/specs/` and
  `docs/superpowers/plans/` while the work is in flight, and are committed so
  the approved wording is reviewable. Delete them from `main` once the milestone
  they describe is complete and committed. Git history retains them, so a
  completed milestone leaves its rationale recoverable without carrying
  superseded documents in the working tree. Do not treat that deletion as
  optional cleanup; it is the last step of the milestone.
- Execute approved plans with `executing-plans` by default.
  `subagent-driven-development` or parallel dispatch requires an explicit user
  request and independent work that can be safely isolated.
- Use test-driven development for every production behavior change: demonstrate
  the generated or synthetic regression before the production edit, implement
  the smallest fix, and run the applicable change gate. Track plan progress and
  record any material deviation; stop for approval when findings change the
  agreed behavior, scope, risk, or architecture.
- Review material production changes for correctness before completion. Use
  `requesting-code-review` for major or risky milestones and
  `receiving-code-review` before acting on review feedback. Use
  `verification-before-completion` before success claims or commits, and
  `finishing-a-development-branch` only when integration is actually requested.
- Ponytail governs scope inside every Superpowers phase. Use it during
  investigation, design, planning, implementation, and review to prefer reuse,
  Blender/Python-native behavior, minimal dependencies, minimal abstractions,
  and the smallest correct diff. Ponytail may recommend deleting or deferring
  work, but it may not skip investigation, design or plan approval, TDD,
  review, verification, preservation checks, or required acceptance gates.
- Read-only inspection, status reporting, and mechanical documentation
  corrections that do not create or change product/process policy may proceed
  without design, plan, or implementation artifacts. They still require
  evidence for factual claims and `git diff --check` when files change.
- Direct user instructions and repository safety invariants take precedence
  over both toolsets. Do not create ceremony merely to demonstrate a skill, but
  do not relabel required reasoning, approval, or verification as ceremony.
  
## Handoff maintenance

Update `docs/HANDOFF.md` at the end of a turn that changes repository state or
materially changes what the next turn must address. Pure read-only answers and
status checks that leave the next action unchanged do not require a handoff
edit. Remove or revise items that no longer require immediate attention.

## Protected and local-only material

- Keep `.local-references`, `.packaged-releases`, and `.codex-assessment`
  protected by `.gitignore`.
- Minimal read-only inspection of `.local-references` is permitted when it is
  necessary to prevent a regression or run an approved compatibility check.
  The local CATS package and test assets may be used for those purposes. Do
  not modify or extract files in place, broadly inventory or quote them, or
  publish, commit, or document their contents or paths without explicit user
  instruction.
- Do not treat external archives, extracted upstream projects, old builds,
  Blender assets, or packaged ZIP files as source-of-truth code unless
  explicitly instructed.
- Do not commit generated profiles, logs, atlases, temporary test output,
  caches, or `.codex-assessment` material.
- Do not replace or add bundled wheels without explicit scope. Any dependency
  change requires provenance, license, hash, ABI/platform, package, and
  runtime validation.
- Do not edit `.git/`, rewrite history, delete files, or remove branches.
- Do not change licensing, attribution, repository ownership
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
named `<id>-<version>.zip`. Build from `addon/`, and read `id` and `version`
from `addon/blender_manifest.toml`. Do not hardcode these values. If the
worktree is dirty, report that the archive contains uncommitted changes.

For packaging changes, validate both `addon/` and the built archive with
Blender's extension validation command. Inspect the resulting ZIP to ensure
required runtime files, the manifest, icons, dependency metadata, and the
pinned wheel are present and that tests, caches, local references, and
generated output are absent.

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
