# Project purpose

This repository contains Shotariya's Material Combiner, a Blender extension
for combining material textures into atlases to reduce draw calls.

The current development target is the 3.1.0 release for Blender 5.2 LTS on
Windows x64, Linux x64, and macOS arm64. The extension bundles one reviewed Pillow wheel per
platform through Blender's extension wheel mechanism. Other Blender versions
or platforms are not supported unless they are separately validated and the
manifest, dependency metadata, tests, and documentation are updated.

Atlas goldens assert decoded pixel content, not PNG file bytes. Pillow links
zlib-ng on Windows and macOS but stock zlib on Linux, so identical images
compress to different files. Do not reintroduce file-hash assertions for
atlas output.

Blender 5.2 ships no macOS Intel build, so macOS means Apple Silicon only.
It does ship windows-arm64, which this package does not target.

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

## Testing and CI Requirements

- Testing is part of implementation, not a separate cleanup task: before making changes, inspect the existing test suite, CI configuration, build/package configuration, public interfaces, primary workflows, integration points, and relevant existing coverage, and assume that changes may affect behavior outside the files or functions directly edited.
- For every non-trivial change, apply all applicable validation layers: basic/static validation such as syntax, compilation, imports, manifests, packaging, configuration, and dependency resolution.
- Maintain fast smoke tests proving the project remains fundamentally usable, including installation or initialization in a clean environment, import/loading, registration and unregistration where applicable, construction of important objects, presence of expected public modules/classes/operators/commands/identifiers/properties, execution of at least one minimal representative happy-path workflow, production of minimally valid output, clean shutdown, and preservation of critical compatibility or integration contracts.
- Add targeted tests covering the changed behavior, relevant edge cases, and failure paths.
- Add regression tests for reproducible defects whenever reasonably practical.
- Add integration tests whenever behavior crosses components, dependencies, applications, plugins, file formats, or external tools.
- When the possible blast radius is unclear, do not assume existing tests are sufficient: inspect callers, consumers, public contracts, integrations, and important invariants, compare behavior before and after the change where practical, run broader smoke/integration coverage, and add characterization tests for important existing behavior that lacks reliable documentation or coverage.
- Tests should protect meaningful observable behavior and stable contracts rather than implementation details or arbitrary test-count targets, and must be deterministic, repeatable, isolated from user-specific machine state, non-destructive, reasonably fast, explicit about fixtures and prerequisites, and runnable unattended through documented commands.
- During development, run the smallest relevant tests frequently, then all directly affected tests, the smoke suite, and broader integration or full-suite testing whenever the blast radius warrants it; do not claim success from code inspection alone, and record the validation commands performed and their results.
- Any useful, stable, unattended test created locally must be evaluated for CI inclusion and normally integrated into CI rather than left as an undocumented local check.
- CI should at minimum catch syntax/compile/import failures, installation or packaging failures, smoke-test failures, public API or compatibility-contract breakage where applicable, targeted regressions, and failures on supported runtimes or platforms where feasible.
- Expensive tests may live in separate scheduled or manual jobs so that a small, fast “must never fail” smoke gate remains on normal changes.
- Never weaken, delete, skip, or rewrite a failing test merely to make CI pass: first determine whether the implementation is wrong, the test is wrong, or expected behavior intentionally changed, preserve tests representing valid contracts, and update expectations only for deliberate and justified behavior changes.
- Treat every discovered failure mode, invariant, compatibility requirement, regression, or newly learned way the project can break as reusable engineering knowledge: whenever such knowledge is discovered, explicitly ask whether it can be converted into a permanent automated test, and add that test when practical so the test suite and CI continuously accumulate institutional knowledge rather than requiring future agents or maintainers to rediscover the same risks.
- A change is not complete until relevant automated tests and smoke tests pass, new behavior has appropriate coverage, fixed defects have regression coverage where practical, affected integration contracts have been checked, useful repeatable tests have been considered for CI, and no known validation failure is hidden or ignored.
- When adequate automation is genuinely impractical, explicitly document what remains untested, why it could not be automated, and what manual validation was performed instead.

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
6. Keep tests isolated from the user's normal Blender profile. Use
   `tests/run_tests.py` and an external temporary work directory.
7. Review `git diff` and `git diff --check`, then rerun `git status --short`.
8. Do not commit, push, publish, tag, or create a release unless explicitly
   requested.

Do not overwrite a dirty file merely because its current contents differ from
`HEAD`.

## Validation

Choose tests proportionate to the change. Consult `tests/README.md` and the
runner parameters rather than assuming paths.

Baseline non-Blender checks:

```
python -m unittest discover -s tests/unit -p "test_*.py"
python tools/verify_dependency_wheel.py
git diff --check
```

For add-on code, registration, UI, dependency, atlas, or compatibility
changes, use Blender 5.2 with `tests/run_tests.py`, which runs on Windows and
Linux:

- `source` mode for source-tree public API, UI, lifecycle, preflight,
  dependency, and atlas checks.
- `package` mode for an installed extension package.
- `checkpoint` mode for approved CATS integration, restart, and uninstall
  checks. Obtain the CATS archive with `tools/fetch_cats.py`, which unwraps
  the published release asset and reports hash drift. Drift warns rather than
  fails until the CATS repository adopts matching release automation.

The atlas undo and repeatability check needs `source --foreground`. In
background mode it reports that it requires a foreground context instead of
running, so a green background run does not cover it. On Linux without a
display the runner uses `xvfb-run`, and refuses to start if xvfb is missing
rather than skipping the check.

Use `source --long-path` to regression-test the Windows extended-length path
handling. Do not raise the padding target: pushing the extension root past
MAX_PATH makes every path carry the `\\?\` prefix, which hides the defect the
mode exists to catch. See `tests/README.md`.

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

## Git policy

Treat each topic branch as a bounded unit of work with one coherent objective. Do not continue onto materially different work merely because it is related, convenient, discovered during implementation, or part of the same conversation.

Before beginning any non-trivial implementation task:

- Inspect the current branch, its relationship to `main`, its existing commits, and the working tree.
- Determine whether the requested work belongs to the current branch's established scope.
- Check whether an existing local branch already has an appropriate scope for the work.
- If the work belongs on an existing suitable branch, stop and switch to that branch before modifying files.
- If no suitable branch exists, stop and create a new topic branch from an up-to-date `main` before modifying files.
- If the current branch contains unfinished work that prevents a safe switch, preserve that work appropriately and explicitly report the situation rather than mixing the new task into the branch.
- Do not interpret user momentum, conversational continuity, or phrases such as "also," "while you're here," or "next" as permission to expand the current branch's scope.

A materially different objective requires a separate branch even when it touches the same files, component, feature area, or bug. Examples include moving from a bug fix to refactoring, adding an unrelated improvement discovered during testing, performing cleanup not necessary for the current acceptance criteria, beginning the next planned milestone, or addressing a separate review concern.

When uncertain whether work belongs on the current branch, prefer stopping and separating it. Branches and pull requests should be small enough that their purpose can be described accurately in one concise sentence and reviewed independently.

Start each new topic branch from an up-to-date `main` and land it through a pull request. `main` is protected and accepts no direct push.

Base pull requests on `main`, not on another unmerged topic branch. Do not create stacked pull requests unless the user explicitly approves a stacked workflow. When new work genuinely depends on an unmerged branch, finish and merge the prerequisite branch first, update `main`, then create or rebase the dependent topic branch onto the updated `main` before opening its pull request.

During implementation, commit each coherent, verified unit before beginning a materially different unit of work. Do not accumulate unrelated completed changes through a long coding session or conversation. Stage explicit paths, inspect the staged diff, and ensure every commit contains only the scope described by its commit message.

Preserve unrelated user changes. Never discard, rewrite, stage, or commit unrelated modifications merely to obtain a clean working tree. Never commit ignored, private, credential-bearing, machine-local, reference-only, or generated outputs unless the repository explicitly requires them.

Do not initialize another repository, change repository remotes, push branches, force-push, delete branches, merge pull requests, or otherwise publish or destructively alter Git state without the approval required by the surrounding instructions. Rewriting history is permitted only when rebasing or cleaning up a branch that has never been published; rewriting published history requires separate approval.

### Branch completion and handoff

Continuously distinguish between "more work could be done" and "the branch's intended work is complete." Do not use spare context, remaining ideas, newly discovered opportunities, or conversational momentum as reasons to extend a completed branch.

Consider the branch complete when its stated objective and acceptance criteria are satisfied, appropriate tests and validation pass, required documentation for that scope is updated, and no known blocker remains that must be fixed before review.

When the branch reaches that state:

- Stop implementation rather than beginning the next task.
- Review the complete branch diff and commit history for accidental scope expansion.
- Run the appropriate final validation.
- Update `docs/HANDOFF.md` with the branch's purpose, important decisions, completed work, validation performed, known limitations or follow-up work, and the recommended next action.
- Explicitly separate follow-up ideas into future work rather than implementing them on the completed branch.
- Present the branch as ready for review, commit/PR preparation, or whatever publication step the user has authorized.

After `docs/HANDOFF.md` accurately captures the completed state, recommend ending the current chat and starting a new chat before beginning the next branch or substantial objective. The new chat should begin by reviewing `docs/HANDOFF.md`, the relevant repository state, and the new branch's intended scope. This handoff boundary is preferred once a branch is genuinely complete because carrying a finished implementation's full conversational history into unrelated work wastes context and increases the risk of scope drift.

Do not recommend a new chat merely because the conversation is long. Recommend it when there is a natural work boundary: the current branch is complete, its state has been documented, and the next meaningful work should occur on another branch.

If the user asks for additional implementation after a branch has reached this completion point, first classify the request against the completed branch's scope. If it is a distinct objective, do not modify files on the completed branch. Stop, explain that the existing branch should remain reviewable, and switch to an existing suitable branch or create a new topic branch from the appropriate updated base before continuing.