# Handoff

## State

Branch `blender-52`, base commit `a146f80`. Uncommitted changes only; nothing
has been committed, pushed, or tagged.

The Blender 5.2 migration is otherwise complete and validated. Full suite is
green: unit, dependency wheel, source-tree Blender, installed-package, and
CATS checkpoint.

## This turn

Fixed two long-path defects in `dependencies.py`. Both made a healthy install
refuse to combine, with a misleading "reinstall the package" message, whenever
the extension path was long enough.

1. `_inside` compared a `\\?\`-prefixed path against a plain-form root, so
   `PIL._imaging` looked untrusted → `dependency_conflict`. New `_plain_path`
   strips the prefix from both operands. Regression test:
   `tests/unit/test_dependencies_paths.py`.
2. `_load_lock` read `dependencies.lock.json` without extended-length syntax.
   Blender's embedded Python is not long-path aware, so past MAX_PATH the read
   failed and the lock appeared absent → `wheel_missing`. It now reads through
   `_filesystem_path`, as `_wheel_integrity` already did.

Both corrections are recorded in `tests/contracts/corrected_behavior.json`.

`tests/run_blender_tests.ps1` now also excludes `.codex-assessment`,
`.local-references`, and `.packaged-releases` from the work-directory copy
(~770 MB per run previously).

`blender_manifest.toml` excludes `AGENTS.md`, `CLAUDE.md`, and `docs/` from the
release package, so agent and developer documentation no longer ships to users.

Ownership and links updated across the project. `README.md` rewritten: badges
removed, credit line now reads Grim-es (original) / Team Neoneko (previous) /
Alrauna (current), `teamneoneko` links repointed to
`Alrauna/material-combiner-addon`, Discord marked coming soon. Grim-es
attribution and the historical Issue #98 link were deliberately kept.

`ui/credits_panel.py`: `GITHUB_ISSUES_URL` repointed to Alrauna; the Discord
button and `DISCORD_URL` removed until the new server exists.
`operators/browser.py` docstring example and both `.github/ISSUE_TEMPLATE`
assignees updated. `tests/unit/test_project_links.py` guards against stale
owner URLs reappearing in shipped source.

Version is now single-sourced. `blender_manifest.toml` is `3.1.0` (the
`-alpha.1` suffix was dropped for release), and `ui/credits_panel.py` derives
`ADDON_VERSION` from the manifest with `tomllib` instead of hardcoding it. The
read goes through `dependencies._filesystem_path` so it survives past MAX_PATH,
and falls back to an empty string rather than a stale number. `AGENTS.md` now
names the 3.1.0 release instead of an alpha, and the README's alpha banner was
reduced to the platform constraint it actually describes.

`verify_blender52_ui.py` gained a Credits panel check asserting the drawn
version label equals the manifest version and that no drawn link is a Discord
URL. `RecordingLayout` now records returned operator objects so link
assignments are visible. Verified RED before the fix: it reported
`Material Combiner 3.0.0`.

Funding removed at the user's request: `.github/FUNDING.yml` deleted with
`git rm`, and `AGENTS.md` no longer protects funding links or lists funding
metadata under `.github/`.

Build naming simplified. `AGENTS.md` now specifies `<id>-<version>.zip` with no
git short hash; the dirty-worktree caveat is kept but no longer refers to a
base commit. `.packaged-releases/` was emptied of all five earlier archives and
rebuilt as `shotariyas_material_combiner-3.1.0.zip`.

## Next

- Review and commit the pending changes.
- Defect 2 has no automated regression test. It only reproduces under Blender's
  embedded Python with an extension path over 260 characters; a standalone
  long-path-aware `python.exe` cannot fail it. Covering it needs the runner to
  be able to force a long physical work directory. Not done.
- `AGENTS.md` carries a pre-existing uncommitted edit that is not ours. It has
  trailing whitespace on line 98, which makes repo-wide `git diff --check`
  return non-zero.
- `CLAUDE.md` is untracked. Decide whether to commit or ignore it.
- Re-add the Discord button in `ui/credits_panel.py` once the new server URL
  exists. The `icons/discord.png` asset is retained for that.
- `ui/credits_panel.py` imports the private `dependencies._filesystem_path`.
  Promote it to a public helper if a third consumer appears.
- Version 3.1.0 is set in the manifest but nothing is tagged. Tag and release
  when ready.
- Build archives no longer carry a commit hash, so a `.zip` in
  `.packaged-releases/` cannot be traced to the commit it was built from, and a
  rebuild silently overwrites the previous file of the same name. Rebuild
  before publishing rather than trusting an archive already on disk.
