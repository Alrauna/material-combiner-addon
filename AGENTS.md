# Project scope

This repository contains Shotariya's Material Combiner, a Blender extension
that combines material textures into atlases to reduce draw calls.

The current target is release 3.1.1 for Blender 5.2 LTS on Windows x64,
Linux x64, and macOS arm64. Blender 5.2 has no macOS Intel build; the package
does not target windows-arm64. Treat other Blender versions and platforms as
unsupported until the manifest, dependency metadata, tests, and documentation
are updated from actual validation.

The extension bundles one reviewed Pillow wheel per supported platform through
Blender's extension wheel mechanism. It must never download dependencies at
runtime, invoke pip, inject the normal user site, or modify Blender's bundled
Python.

Atlas goldens assert decoded pixel content, not PNG file bytes. Pillow uses
zlib-ng on Windows and macOS but stock zlib on Linux, so identical images can
compress differently. Do not reintroduce atlas file-hash assertions.

## Security invariant

Checksum acquisition in `tools/ci.py` deliberately uses three independent
resolver paths: the runner resolver, Cloudflare DNS-over-HTTPS through curl,
and a hand-written Quad9 DNS-over-TLS client whose addresses are passed to
curl with `--resolve`. All three manifests must agree, and the selected
checksum must match the committed SHA-256 pin.

The separate resolver implementations, hand-written DNS parser, three-way
consensus, and committed pin are intentional security controls. Do not
consolidate or replace them unless the approved replacement preserves all
four properties and their regression coverage.

## Repository and package boundaries

`addon/` is the Blender extension package root and the only directory shipped
to users. Build from `addon/`, never from the repository root, and do not add
another wrapper inside it without a demonstrated Blender, import, packaging,
or test requirement.

Inside `addon/`:

- Package and registration infrastructure remains at the package root.
- `operators/`, `ui/`, and `utils/` keep their existing responsibilities.
- `ui/` and `operators/ui/` are intentionally distinct and must not be merged.
- `icons/`, `wheels/`, `blender_manifest.toml`, `dependencies.lock.json`, and
  `THIRD_PARTY.md` are deliberate runtime or packaged metadata.

Everything outside `addon/` is development material. `tests/`, `tools/`,
`docs/`, `.github/`, `README.md`, `LICENSE`, `tests/README.md`, and
`pyproject.toml` are not packaged. Keep runtime paths and package metadata
synchronized when an authorized move is unavoidable.

## Working model

- Read-only investigation, status reporting, and mechanical documentation
  corrections may proceed directly.
- A clear, bounded request to implement a change authorizes investigation,
  editing, and proportionate local validation. It does not authorize commits,
  publication, destructive Git operations, dependency changes, licensing or
  attribution changes, or broader follow-up work.
- Pause for user direction only when an unresolved choice would materially
  change behavior, UX, architecture, compatibility, security, licensing,
  dependencies, publication, risk, or the requested scope.
- Start defects and unexpected results by reproducing the problem and finding
  the root cause. Add an in-scope regression test when practical before the
  production fix; do not weaken a valid failing test to make a change pass.
- Prefer existing project patterns, Blender/Python-native behavior, minimal
  dependencies, minimal abstractions, and the smallest correct diff.
- Named third-party skills, repository design documents, and repository plan
  files are optional aids, not prerequisites. Use them only when the user asks
  or the task's risk and complexity genuinely justify them.
- Keep each branch and task focused on one coherent objective. Necessary
  tests, documentation, and fixes for that objective stay in scope; unrelated
  improvements become follow-up work.

## Protected and local-only material

- Keep `.local-references/`, `.packaged-releases/`, and `.codex-assessment/`
  ignored and out of commits.
- Inspect `.local-references/` only when necessary for an approved
  compatibility check. Do not modify or extract it in place, broadly inventory
  or quote it, or publish its contents or paths.
- Never commit material directly from `.codex-assessment/`. A user-approved
  curated artifact must first be copied to an intentional tracked location and
  reviewed like any other source or documentation change.
- Do not treat external archives, extracted upstream projects, old builds,
  Blender assets, or release ZIPs as source-of-truth code unless explicitly
  instructed.
- Do not commit generated profiles, logs, atlases, temporary output, caches,
  assessment output, or release ZIPs.
- Do not replace or add bundled wheels without explicit scope and validated
  provenance, license, hash, ABI/platform, package, and runtime behavior.
- Do not change licensing, attribution, repository ownership metadata, or
  third-party notices without explicit approval.

If an artifact's origin or publication rights are uncertain, keep it local and
ask before using or publishing it.

## Compatibility contracts

Preserve these interfaces unless the requested task explicitly changes them:

- Extension ID, name, version policy, platform declarations, and public
  manifest metadata.
- Blender operator `bl_idname` values and registered class identifiers.
- RNA scene/material properties and saved-file identifiers.
- Importable module paths in `tests/contracts/public_api_contract.json`.
- CATS-facing modules, symbols, UI integration, and operator calls.
- Registration, unregistration, reload, restart, and uninstall behavior.
- Behavioral evidence and golden outputs in
  `tests/contracts/stage0_behavior.json`.
- The bundled Pillow dependency model described above.

A known defect may be corrected, but retain the earlier behavioral evidence
and add corrected expectations or a regression test rather than silently
rewriting a valid contract.

## Safe editing procedure

1. Before editing, run `git status --short --untracked-files=all`. Existing
   changes belong to the user; preserve them and avoid unrelated files.
2. Inspect the affected entry points, callers, tests, contracts, and
   integration boundaries. Expand inspection only when the blast radius is
   unclear.
3. Make the smallest change that satisfies the task. Do not reorganize or
   rename adjacent public code for neatness.
4. Use Git-aware moves and removals when the approved task requires them.
   Never delete, overwrite, stage, or discard unrelated material.
5. Keep test work outside tracked source and isolate Blender from the user's
   normal profile using `tests/run_tests.py` and an external work directory.
6. Review the complete diff, run `git diff --check`, and rerun status before
   reporting completion.

## Git and authorization

`master` is the protected default branch. Use the latest locally available
`master` as a new branch base. Fetch, pull, rebase, or otherwise update it only
when the user authorizes that network or Git-state change.

For non-trivial implementation, inspect the current branch, its relationship
to `master`, its commits, and the working tree. A clear implementation request
authorizes creation of a local `codex/` topic branch when the current clean
checkout has unrelated scope. If user changes prevent a safe switch, stop and
report the conflict rather than stashing or mixing work without permission.

In a Codex-managed worktree, do not switch branches through the shell. Work in
the provided branch or detached worktree, and use the app's Create Branch or
Handoff flow when the user requests integration. A branch cannot be checked
out in more than one worktree at a time.

Do not commit, amend, push, force-push, publish, tag, create a release, create
or merge a pull request, rewrite history, delete branches, change remotes, or
initialize another repository unless the user explicitly requests that exact
class of action. When commits are authorized, stage explicit paths and keep
each commit coherent. Never rewrite published history without separate,
explicit approval.

## Validation

Choose validation by risk and affected behavior. Consult `tests/README.md` for
the authoritative Blender runner modes, prerequisites, and commands.

- Read-only work changes nothing and needs no test run.
- Documentation-only changes require content review, `git diff --check`, and
  final status inspection. Run code tests only when the documentation changes
  executable commands, configuration, contracts, or development policy with a
  plausible implementation impact.
- Production changes require targeted tests for changed behavior and failure
  paths, affected compatibility or integration checks, and the smallest useful
  smoke test. Run broader unit, Blender, package, or platform coverage when the
  blast radius warrants it.
- Packaging, dependency, registration, UI, atlas, and compatibility changes
  require their applicable Blender source/package/checkpoint validation from
  `tests/README.md`.
- Add useful in-scope regression tests without pausing for a separate question.
  Record broader test or CI opportunities as follow-up work instead of
  expanding the current branch automatically.

Common non-Blender gates when affected are:

```text
python -m unittest discover -s tests/unit -p "test_*.py"
python tools/verify_dependency_wheel.py
git diff --check
```

Tests should be deterministic and isolated. The approved CATS latest-release
checkpoint is a rolling compatibility exception: it intentionally resolves a
new final upstream release after verifying provenance. Record the resolved
release identity and SHA-256 for each run, and do not describe that external
input as deterministic or pinned.

Hosted release validation covers the supported Windows, Linux, and macOS
matrix. If Blender 5.2, a platform runner, an approved integration package, or
another required dependency is unavailable, state exactly what was not run;
do not claim unsupported validation.

Never hide a known validation failure. When automation is impractical,
document what remains untested, why, and any manual validation performed.

## Packaging and publication safety

Put intentional build output in `.packaged-releases/`. Every extension archive
must be named `<id>-<version>.zip`, with both values read from
`addon/blender_manifest.toml`; do not hardcode them. Report when a package was
built from a dirty worktree.

For packaging changes, validate both `addon/` and the built archive with
Blender's extension validation command. Inspect the ZIP for required runtime
files, manifest, icons, dependency metadata, attribution, and reviewed wheels,
and ensure tests, caches, local references, assessment output, logs, and
bytecode are absent.

Before authorized GitHub publication:

- Confirm status contains no protected, generated, credential-bearing, or
  machine-local material.
- Check documentation and configuration for absolute paths, usernames,
  credentials, tokens, and machine-specific settings.
- Revalidate dependency hashes, third-party notices, and declared platform
  targets against actual validation.
- Base the pull request on protected `master`; do not create a stacked pull
  request unless the user explicitly approves that workflow.

## Handoff

Update `docs/HANDOFF.md` at a milestone boundary, an explicit handoff, or when
a blocker or materially changed next action must survive into another task.
Keep it concise and remove stale immediate-action instructions. Routine edits
within an active task do not require handoff churn, and branch completion does
not require recommending a new chat.
