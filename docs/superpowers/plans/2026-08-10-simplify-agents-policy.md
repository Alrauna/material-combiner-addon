# Simplify AGENTS Policy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the contradictory, framework-coupled `AGENTS.md` with a compact, portable policy that preserves project safety, compatibility, packaging, and validation invariants.

**Architecture:** Keep durable repository invariants in the root instruction file and route detailed test and release procedures to their existing documentation. Replace mandatory skill workflows and approval waterfalls with risk-based autonomy, and make Git rules consistent with this repository's `master` branch and Codex-managed worktrees.

**Tech Stack:** Markdown, Git, PowerShell validation, existing Python unit tests.

## Global Constraints

- Preserve the 3.1.1 target for Blender 5.2 LTS on Windows x64, Linux x64, and macOS arm64.
- Preserve the three independent checksum resolver paths, three-way consensus, and committed SHA-256 pin.
- Preserve decoded-pixel atlas goldens and the bundled reviewed Pillow wheel model.
- Preserve public API, Blender identifiers, RNA properties, CATS integration, lifecycle, and behavioral contracts.
- Preserve `addon/` as the package root and keep protected/local-only material uncommitted.
- Do not change runtime code, tests, manifests, dependencies, licensing, attribution, or release metadata.
- Do not commit, push, publish, or open a pull request without separate user authorization.

---

### Task 1: Replace the root agent policy and record the handoff

**Files:**

- Modify: `AGENTS.md`
- Modify: `docs/HANDOFF.md`
- Delete at the completed milestone boundary, only after its approved wording is preserved as authorized: `docs/superpowers/plans/2026-08-10-simplify-agents-policy.md`

**Interfaces:**

- Consumes: the user-approved policy review from 2026-08-10 and the existing repository invariants.
- Produces: a self-contained root policy below 16 KiB with unambiguous authorization, validation, Git, and handoff rules.

- [x] **Step 1: Run the RED policy check against the existing file**

```powershell
$text = Get-Content -Raw AGENTS.md
$bytes = [Text.Encoding]::UTF8.GetByteCount($text)
$failures = @()
if ($bytes -ge 16384) { $failures += "AGENTS.md is $bytes bytes" }
if ($text -match 'Superpowers owns the development lifecycle') { $failures += 'framework coupling remains' }
if ($text -match 'During implementation, commit each coherent') { $failures += 'implicit commit requirement remains' }
if ($text -match 'Do not edit `\.git/`, rewrite history, delete files') { $failures += 'absolute deletion/history contradiction remains' }
if ($text -notmatch 'Codex-managed worktree') { $failures += 'worktree policy is absent' }
if ($text -notmatch 'rolling compatibility') { $failures += 'CATS determinism exception is absent' }
if ($failures.Count) { throw ($failures -join '; ') }
```

Expected: FAIL with the size, framework-coupling, implicit-commit, deletion/history, worktree, and rolling-checkpoint findings.

- [x] **Step 2: Rewrite `AGENTS.md` with the approved compact structure**

The replacement must contain these sections and exact decisions:

1. **Purpose and supported target**
   - Name Shotariya's Material Combiner and its atlas/draw-call purpose.
   - State version 3.1.1, Blender 5.2 LTS, and the three supported platforms.
   - State that other versions/platforms require validation and synchronized metadata, tests, and documentation.
2. **Non-negotiable invariants**
   - Retain the checksum resolver security design without weakening or consolidating it.
   - Retain decoded-pixel atlas goldens and the no-runtime-download Pillow model.
3. **Repository and package boundaries**
   - Keep `addon/` as the only shipped root and point detailed layout questions to the repository documentation.
   - Keep `ui/` distinct from `operators/ui/` and package only reviewed runtime material.
4. **Working model**
   - Read-only analysis and mechanical documentation may proceed directly.
   - A clear bounded implementation request authorizes investigation and editing without a second design or plan approval.
   - Pause only for unresolved choices that materially change behavior, architecture, compatibility, security, licensing, dependencies, publication, or scope.
   - Require root-cause investigation for defects and appropriate regression evidence for behavior changes.
   - Do not require named third-party skills or repository plan/spec artifacts.
5. **Git and authorization**
   - Name `master` as the protected default branch.
   - Use the latest locally available `master`; fetch or update it only when the user authorizes that network/Git operation.
   - Inspect status and preserve unrelated work before editing.
   - Keep each topic branch coherent, but allow necessary regression tests and fixes within the same objective.
   - In a Codex-managed worktree, do not switch branches through the shell; use the provided detached worktree and the app's Create Branch or Handoff flow when requested.
   - Do not commit, push, publish, tag, release, create/merge a PR, rewrite history, or delete branches unless explicitly requested.
   - Permit Git-aware file deletion only when required by the approved task; never discard unrelated material.
6. **Validation**
   - Make validation risk-based and route exact Blender commands to `tests/README.md`.
   - Documentation-only changes require review, `git diff --check`, and status inspection.
   - Production changes require targeted tests, affected contracts/integrations, smoke coverage when applicable, and broader tests when blast radius warrants them.
   - Add an in-scope regression test without interrupting for a separate question when practical; record broader test or CI opportunities as follow-up work instead of expanding the branch automatically.
   - Declare the latest-release CATS checkpoint an approved rolling compatibility exception; record the resolved version/hash and do not describe it as deterministic.
   - Use the hosted Windows, Linux, and macOS matrix for supported-platform release coverage, and report unavailable platform or Blender validation explicitly.
7. **Protected material and compatibility**
   - Preserve protected local directories and forbid committing material directly from `.codex-assessment`.
   - Permit a user-approved curated artifact only after copying it to an intentional tracked location and reviewing it.
   - Preserve all listed compatibility contracts unless the task explicitly changes them.
8. **Packaging and release safety**
   - Retain build-from-`addon/`, archive naming/location, dirty-tree disclosure, validation, archive inspection, and publication safety.
9. **Handoff**
   - Update `docs/HANDOFF.md` only at a milestone boundary, an explicit handoff, or when blocked/next action materially changes.
   - Do not require starting a new chat.

- [x] **Step 3: Update `docs/HANDOFF.md` for this policy branch**

Replace stale active-branch material with a concise top section recording:

- branch `codex/simplify-agents-policy` from `master` at `5cc7534`;
- objective: simplify and deconflict `AGENTS.md` without changing product behavior;
- baseline: 109 unit tests passed with three expected skips;
- current state and next action;
- no runtime, manifest, dependency, contract, licensing, attribution, or release changes.

Retain genuinely useful release and maintenance information below it; remove only stale immediate-action instructions that no longer apply.

- [x] **Step 4: Run the GREEN policy and preservation checks**

```powershell
$text = Get-Content -Raw AGENTS.md
$bytes = [Text.Encoding]::UTF8.GetByteCount($text)
if ($bytes -ge 16384) { throw "AGENTS.md is $bytes bytes" }
foreach ($required in @(
    'Codex-managed worktree',
    'rolling compatibility',
    'Do not commit',
    'master',
    'decoded pixel',
    'three independent',
    'tests/README.md'
)) {
    if ($text -notmatch [regex]::Escape($required)) { throw "Missing: $required" }
}
foreach ($forbidden in @(
    'Superpowers owns the development lifecycle',
    'During implementation, commit each coherent',
    'recommend ending the current chat',
    'Neither is packaged'
)) {
    if ($text -match [regex]::Escape($forbidden)) { throw "Still present: $forbidden" }
}
git diff --check
git status --short --untracked-files=all
```

Expected: PASS; only the approved policy, handoff, and in-flight plan are changed.

- [x] **Step 5: Run regression validation appropriate to policy-only documentation**

```powershell
python -m unittest discover -s tests/unit -p "test_*.py"
```

Expected: 109 tests pass with the same three expected skips. Blender, package, wheel, and CATS execution are unnecessary because no runtime or build input changes.

- [x] **Step 6: Review the complete diff and authorization boundary**

```powershell
git diff -- AGENTS.md docs/HANDOFF.md docs/superpowers/plans/2026-08-10-simplify-agents-policy.md
git diff --check
git status --short --untracked-files=all
```

Expected: no product/process requirement from the approved review is missing; no unrelated file is changed; no commit or publication operation has occurred.

**Commit boundary:** If and only if the user separately authorizes commits, preserve the approved plan wording as required by the currently active policy, commit the coherent documentation change, and remove the temporary plan at the milestone boundary in the authorization-compliant manner agreed with the user.
