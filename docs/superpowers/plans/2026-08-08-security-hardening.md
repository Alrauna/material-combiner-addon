# Security Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make CATS acquisition fail closed and size bounded, harden the
existing browser operator's URL boundary, and record the intentional CI DNS
design without changing the extension's public API.

**Architecture:** Keep the existing standard-library-only tools and public
Blender classes. Add bounded stream helpers inside `tools/fetch_cats.py`, make
drift policy an explicit CLI choice, and replace the browser prefix regex with
complete `urllib.parse.urlsplit` validation. The CI resolver implementation is
documented but not modified.

**Tech Stack:** Python 3.13 standard library, Blender 5.2 Python API,
`unittest`, Ruff, Blender extension tooling.

## Global Constraints

- Preserve every module path, registered class, operator `bl_idname`, RNA
  property, default value, and saved-file identifier in
  `tests/contracts/public_api_contract.json`.
- Preserve all existing tests and assertions. No test may be deleted, skipped,
  weakened, or converted from behavioral coverage to an implementation-detail
  assertion.
- Add no runtime dependency and perform no runtime download or installation.
- Keep the extension package rooted at `addon/` and build only from that
  directory.
- Preserve the three supported platform declarations and reviewed Pillow
  wheels unchanged.
- Do not modify `tools/ci.py`, its resolver behavior, or its resolver tests.
- Use `BLENDER_52` as the local environment variable containing the absolute
  Blender 5.2 executable path. If it is unavailable, report every Blender gate
  as unrun and rely on CI before merge.
- Use test work directories under the operating-system temporary directory,
  never inside tracked source.

---

### Task 1: Record the protected DNS security invariant

**Files:**

- Modify: `AGENTS.md` after the project-purpose platform paragraphs
- Modify: `docs/HANDOFF.md`

**Interfaces:**

- Consumes: the existing `tools/ci.py` three-resolver implementation and
  `tests/unit/test_ci.py` consensus/parser coverage
- Produces: a repository instruction preventing accidental consolidation of
  independent resolver paths

- [ ] **Step 1: Add the invariant to `AGENTS.md`**

Insert this section after the platform-support paragraphs and before
`## Intended repository layout`:

```markdown
## Security design invariants

The checksum acquisition in `tools/ci.py` deliberately uses three independent
resolver paths: the runner resolver, Cloudflare DNS-over-HTTPS through curl,
and a hand-written Quad9 DNS-over-TLS client whose addresses are passed to curl
with `--resolve`. All three checksum manifests must agree, and the selected
checksum must match the committed SHA-256 pin. The separate resolver
implementations, hand-written DNS parser, three-way consensus, and committed
pin are intentional security controls, not cleanup debt. Do not consolidate or
replace them unless the replacement preserves all four properties and their
regression coverage.
```

- [ ] **Step 2: Verify the wording describes the code and tests**

Run:

```powershell
rg -n "runner resolver|Cloudflare|Quad9|three-way consensus|committed" AGENTS.md tools/ci.py tests/unit/test_ci.py
python -m unittest tests.unit.test_ci -v
```

Expected: the four invariant properties appear in `AGENTS.md`; all CI unit
tests pass without changes to `tools/ci.py` or `tests/unit/test_ci.py`.

- [ ] **Step 3: Update the active handoff note**

Add a completed-work bullet stating that the DNS resolver design is now a
protected `AGENTS.md` invariant. Do not claim any CATS or browser implementation
is complete yet.

- [ ] **Step 4: Review and commit the documentation-only unit**

Run:

```powershell
git diff -- AGENTS.md docs/HANDOFF.md
git diff --check
git add -- AGENTS.md docs/HANDOFF.md
git diff --cached --check
git commit -m "docs: protect CI resolver security design"
```

Expected: one documentation-only commit; `git diff --name-only HEAD^` lists
only `AGENTS.md` and `docs/HANDOFF.md`.

---

### Task 2: Make CATS drift fail closed by default

**Files:**

- Modify: `tests/unit/test_fetch_cats.py:92-122,181-198`
- Modify: `tools/fetch_cats.py:1-38,162-267`
- Modify: `tests/README.md:43-62`

**Interfaces:**

- Consumes: `fetch(output_dir: Path, archive: Path | None, allow_drift: bool)`
  and `main(argv: list[str] | None = None) -> int`
- Produces: fail-closed default behavior, explicit `--allow-drift`, retained
  legacy `--strict`, and unchanged JSON/GitHub-output shapes except for policy
  values

- [ ] **Step 1: Replace the old drift tests with fail-closed expectations**

Change `DriftPolicyTests` to exercise the new direct interface:

```python
class DriftPolicyTests(unittest.TestCase):
    """Drift fails by default and requires an explicit local override."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.archive = make_extension_zip(self.tmp / "cats.zip")

    def test_hash_drift_fails_by_default(self):
        report, exit_code = fetch_cats.fetch(self.tmp / "o1", self.archive)
        self.assertEqual(1, exit_code)
        self.assertTrue(report["drift"])
        self.assertTrue(report["drift_is_fatal"])

    def test_hash_drift_requires_explicit_allowance(self):
        report, exit_code = fetch_cats.fetch(
            self.tmp / "o2", self.archive, allow_drift=True
        )
        self.assertEqual(0, exit_code)
        self.assertTrue(report["drift"])
        self.assertFalse(report["drift_is_fatal"])

    def test_wrong_extension_id_always_fails(self):
        wrong = make_extension_zip(
            self.tmp / "wrong.zip", extension_id="something_else"
        )
        _, exit_code = fetch_cats.fetch(
            self.tmp / "o3", wrong, allow_drift=True
        )
        self.assertEqual(1, exit_code)
```

Replace `test_default_policy_is_warn` with source and CLI compatibility tests:

```python
def test_source_has_no_hidden_policy_switch(self):
    self.assertFalse(hasattr(fetch_cats, "HASH_MISMATCH_IS_FATAL"))

def test_legacy_strict_flag_is_still_accepted(self):
    report = {"drift": [], "drift_is_fatal": True}
    with mock.patch.object(fetch_cats, "fetch", return_value=(report, 1)) as fetch:
        self.assertEqual(
            1,
            fetch_cats.main(
                ["--output-dir", str(self.tmp), "--strict"]
            ),
        )
    fetch.assert_called_once_with(self.tmp, None, allow_drift=False)

def test_conflicting_policy_flags_are_rejected(self):
    with self.assertRaises(SystemExit):
        fetch_cats.main(
            [
                "--output-dir",
                str(self.tmp),
                "--strict",
                "--allow-drift",
            ]
        )
```

Give `ReferenceFileTests` a `setUp` that creates `self.tmp` for the CLI test.

- [ ] **Step 2: Run the focused tests and confirm RED**

Run:

```powershell
python -m unittest tests.unit.test_fetch_cats.DriftPolicyTests tests.unit.test_fetch_cats.ReferenceFileTests -v
```

Expected: failures show the current warn-by-default policy, absent
`--allow-drift`, old `fetch(..., strict=...)` signature, and existing hidden
constant.

- [ ] **Step 3: Implement the smallest fail-closed policy change**

Change the direct function interface to:

```python
def fetch(
    output_dir: Path,
    archive: Path | None,
    allow_drift: bool = False,
) -> tuple[dict[str, object], int]:
```

Set the report field and final drift decision directly from `allow_drift`:

```python
"drift_is_fatal": not allow_drift,
```

```python
if drift and not allow_drift:
    return report, 1
```

Delete `HASH_MISMATCH_IS_FATAL`. Define the CLI policy flags with one
mutually-exclusive group:

```python
policy = parser.add_mutually_exclusive_group()
policy.add_argument(
    "--strict",
    action="store_true",
    help="Require the pinned CATS reference (the default; retained for compatibility).",
)
policy.add_argument(
    "--allow-drift",
    action="store_true",
    help="Allow an unpinned CATS release for deliberate local inspection.",
)
```

Call:

```python
report, exit_code = fetch(
    arguments.output_dir,
    arguments.archive,
    allow_drift=arguments.allow_drift,
)
```

Update the module examples and `tests/README.md` so the normal command is
strict, `--strict` is documented as a compatible explicit spelling, and only
`--allow-drift` permits drift.

- [ ] **Step 4: Run focused and full unit checks for GREEN**

Run:

```powershell
python -m unittest tests.unit.test_fetch_cats -v
python -m unittest discover -s tests/unit -p "test_*.py"
python -m ruff check tools/fetch_cats.py tests/unit/test_fetch_cats.py
```

Expected: all commands pass; no existing security test is removed.

- [ ] **Step 5: Review and commit the policy unit**

Run:

```powershell
git diff -- tools/fetch_cats.py tests/unit/test_fetch_cats.py tests/README.md
git diff --check
git add -- tools/fetch_cats.py tests/unit/test_fetch_cats.py tests/README.md
git diff --cached --check
git commit -m "fix: make CATS reference drift fail closed"
```

---

### Task 3: Bound CATS responses, downloads, and inner archives

**Files:**

- Modify: `tests/unit/test_fetch_cats.py`
- Modify: `tools/fetch_cats.py`
- Modify: `tools/cats_reference.json`

**Interfaces:**

- Consumes: `_get(...) -> bytes`, `resolve_latest(...)`, `unwrap(...)`, and
  the committed CATS reference
- Produces: `_copy_bounded(source, destination, maximum, label) -> int`,
  `_download(url, output, maximum) -> int`, a four-field
  `resolve_latest(...) -> tuple[str, str, str, int]`, bounded extraction, size
  drift facts, and extension-version verification

- [ ] **Step 1: Add bounded-stream and size-policy regression tests**

Add a small response double:

```python
class FakeResponse:
    def __init__(self, data: bytes, url: str = "https://example.test/file"):
        self._stream = io.BytesIO(data)
        self.status = 200
        self.url = url

    def read(self, size=-1):
        return self._stream.read(size)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False
```

Import `io`. Add tests that prove:

```python
def test_api_response_over_limit_is_rejected(self):
    response = FakeResponse(b"x" * (fetch_cats.API_MAX_BYTES + 1))
    with mock.patch.object(fetch_cats.urllib.request, "urlopen", return_value=response):
        with self.assertRaisesRegex(RuntimeError, "API response exceeds"):
            fetch_cats._get("https://api.github.com/x", "application/json")

def test_download_over_limit_removes_partial_file(self):
    target = self.tmp / "asset.zip"
    response = FakeResponse(b"x" * 17)
    with mock.patch.object(fetch_cats.urllib.request, "urlopen", return_value=response):
        with self.assertRaisesRegex(RuntimeError, "release asset exceeds"):
            fetch_cats._download(
                "https://example.test/asset.zip", target, maximum=16
            )
    self.assertFalse(target.exists())

def test_inner_zip_member_over_limit_is_rejected(self):
    inner = self.tmp / "inner.zip"
    inner.write_bytes(b"x" * 17)
    wrapper = make_wrapper_zip(self.tmp / "wrapper.zip", "cats.zip", inner)
    with mock.patch.object(fetch_cats, "EXTENSION_MAX_BYTES", 16):
        with self.assertRaisesRegex(RuntimeError, "extension archive exceeds"):
            fetch_cats.unwrap(wrapper, "cats.zip", self.tmp / "out")
```

Add fetch-policy tests using a temporary patched `REFERENCE_PATH` whose hashes,
sizes, ID, and version match generated archives. Prove exact sizes pass, an
asset/extension size mismatch fails by default, the mismatch is allowed only
with `allow_drift=True`, and a mismatched extension version follows the same
drift policy. Keep the existing wrong-ID-always-fatal test.

First extend the existing fixture helper without changing its default callers:

```python
def make_extension_zip(
    path: Path,
    extension_id: str = "cats_blender_plugin",
    version: str = REFERENCE["extension_version"],
):
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "blender_manifest.toml",
            'schema_version = "1.0.0"\n'
            f'id = "{extension_id}"\n'
            f'version = "{version}"\n',
        )
        archive.writestr("__init__.py", "")
    return path
```

- [ ] **Step 2: Run new tests and confirm RED**

Run:

```powershell
python -m unittest tests.unit.test_fetch_cats -v
```

Expected: failures identify absent size constants/helpers, unbounded reads,
unused committed sizes, and absent extension-version verification.

- [ ] **Step 3: Implement bounded standard-library streaming**

Add constants:

```python
API_MAX_BYTES = 1 * 1024 * 1024
ASSET_MAX_BYTES = 64 * 1024 * 1024
EXTENSION_MAX_BYTES = 64 * 1024 * 1024
STREAM_CHUNK_BYTES = 64 * 1024
```

Add one shared copier:

```python
def _copy_bounded(source, destination, maximum: int, label: str) -> int:
    total = 0
    while chunk := source.read(STREAM_CHUNK_BYTES):
        total += len(chunk)
        if total > maximum:
            raise RuntimeError(f"{label} exceeds {maximum} bytes")
        destination.write(chunk)
    return total
```

Use it in `_get` with `io.BytesIO`, in `_download` with a file opened as
`"wb"`, and in `unwrap` with `ZipFile.open(info)`. `_download` and `unwrap`
must remove partial destinations on any exception. Keep the existing HTTPS,
status, final-redirect, token-host, and filename checks.

Change `resolve_latest` to return the GitHub-reported asset size as its fourth
value. In `fetch`, record and compare:

```python
actual_asset_size = asset_path.stat().st_size
actual_extension_size = extension.stat().st_size
```

Append drift messages when either differs from `asset_size` or
`extension_size`. Add `asset_size`, `extension_size`, and
`extension_version` to the JSON report.

Parse the extension manifest once through:

```python
def extension_manifest_of(archive: Path) -> dict[str, object] | None:
```

Retain `extension_id_of(archive)` as a wrapper returning the parsed `id`, so
existing test/tool callers continue to work. Compare manifest `version` with
the committed `extension_version`; a wrong ID remains independently fatal.

- [ ] **Step 4: Reconcile committed sizes without changing the pinned artifact**

Run:

```powershell
Get-Item .local-references\cats_blender_plugin-5.2.0-alpha.1-795d323.zip | Select-Object Length,FullName
python tools/fetch_cats.py --output-dir $env:TEMP\smc-cats-plan-check --archive .local-references\cats_blender_plugin-5.2.0-alpha.1-795d323.zip --strict
```

Expected: the checked local artifact either matches the committed reference or
the command fails with explicit size/hash drift. Do not modify or commit the
local archive. Change `tools/cats_reference.json` only if its existing sizes
are demonstrably incorrect for the already pinned hashes; do not adopt a new
artifact in this task.

- [ ] **Step 5: Run focused and full GREEN checks**

Run:

```powershell
python -m unittest tests.unit.test_fetch_cats -v
python -m unittest discover -s tests/unit -p "test_*.py"
python -m ruff check tools/fetch_cats.py tests/unit/test_fetch_cats.py
git diff --check
```

Expected: all pass, with limit, policy, token, redirect, hash, ID, version, and
GitHub-output coverage retained.

- [ ] **Step 6: Review and commit the bounded-acquisition unit**

Run:

```powershell
git diff -- tools/fetch_cats.py tests/unit/test_fetch_cats.py tools/cats_reference.json
git add -- tools/fetch_cats.py tests/unit/test_fetch_cats.py tools/cats_reference.json
git diff --cached --check
git commit -m "fix: bound CATS acquisition inputs"
```

Omit `tools/cats_reference.json` from `git add` if Step 4 proves it needs no
correction.

---

### Task 4: Validate complete HTTPS browser URLs

**Files:**

- Modify: `tests/blender/verify_blender52_ui.py:80-167`
- Modify: `addon/operators/browser.py:1-81`

**Interfaces:**

- Consumes: `OpenBrowser.link`, `OpenBrowser._validate_url()`, and
  `bpy.ops.smc.browser`
- Produces: unchanged `OpenBrowser`, `smc.browser`, `link` RNA property, and
  operator result sets with complete HTTPS validation

- [ ] **Step 1: Add the Blender regression before changing runtime code**

After enabling the package in `verify_blender52_ui.py`, replace the module's
`webbrowser.open` with a recorder and invoke the registered operator:

```python
browser = importlib.import_module(f"{MODULE}.operators.browser")
opened_urls: list[str] = []
browser.webbrowser.open = (
    lambda url, **_kwargs: opened_urls.append(url) or True
)
good_url = "https://example.com:443/docs?q=atlas#install"
assert bpy.ops.smc.browser(link=good_url) == {"FINISHED"}
bad_urls = (
    "http://example.com",
    "https://trusted.example@evil.example/path",
    "https://example.com whitespace",
    "https://example.com\nfile:///tmp/x",
    "https:///missing-host",
    "https://example.com:not-a-port/path",
)
for bad_url in bad_urls:
    assert bpy.ops.smc.browser(link=bad_url) == {"CANCELLED"}, bad_url
assert opened_urls == [good_url], opened_urls
report["checks"]["browser_https_validation"] = {
    "opened": opened_urls,
    "rejected": list(bad_urls),
}
```

- [ ] **Step 2: Run the UI suite and confirm RED**

Run:

```powershell
python tests/run_tests.py --blender $env:BLENDER_52 --work $env:TEMP\smc-browser-red source --script tests/blender/verify_blender52_ui.py --result ui.json
```

Expected: current regex permits at least HTTP, credential-bearing, and suffix
inputs, so the suite fails. If `BLENDER_52` is unavailable, do not edit runtime
code; report the missing RED gate and obtain direction.

- [ ] **Step 3: Implement complete URL validation without changing the operator API**

Replace `re` with:

```python
from urllib.parse import urlsplit
```

Keep `_validate_url(self) -> Tuple[bool, str]`. Its minimal validation is:

```python
if not self.link:
    return False, "URL cannot be empty"
if any(character.isspace() or ord(character) < 32 for character in self.link):
    return False, "URL cannot contain whitespace or control characters"
try:
    parsed = urlsplit(self.link)
    parsed.port
except ValueError:
    return False, "Invalid HTTPS URL"
if parsed.scheme != "https" or not parsed.hostname:
    return False, "URL must be a complete HTTPS address"
if parsed.username is not None or parsed.password is not None:
    return False, "URL credentials are not allowed"
return True, ""
```

Remove `URL_PATTERN` and the HTTP warning. Retain the class, RNA declaration,
`execute`, error reporting, and browser exception handling.

- [ ] **Step 4: Run GREEN and preservation suites**

Run:

```powershell
python tests/run_tests.py --blender $env:BLENDER_52 --work $env:TEMP\smc-browser-green source --script tests/blender/verify_blender52_ui.py --result ui.json
python tests/run_tests.py --blender $env:BLENDER_52 --work $env:TEMP\smc-public-api source --script tests/blender/verify_public_api.py --result api.json
python -m ruff check addon/operators/browser.py tests/blender/verify_blender52_ui.py
```

Expected: both Blender suites and Ruff pass; the public API contract file is
unchanged.

- [ ] **Step 5: Review and commit the runtime hardening unit**

Run:

```powershell
git diff -- addon/operators/browser.py tests/blender/verify_blender52_ui.py
git diff -- tests/contracts/public_api_contract.json tests/contracts/stage0_behavior.json tests/contracts/corrected_behavior.json
git diff --check
git add -- addon/operators/browser.py tests/blender/verify_blender52_ui.py
git diff --cached --check
git commit -m "fix: require complete HTTPS browser links"
```

Expected: the three contract diffs are empty.

---

### Task 5: Complete review, validation, and milestone handoff

**Files:**

- Modify: `docs/HANDOFF.md`
- Delete after final approval and verification:
  `docs/superpowers/specs/2026-08-08-security-hardening-design.md`
- Delete after final approval and verification:
  `docs/superpowers/plans/2026-08-08-security-hardening.md`

**Interfaces:**

- Consumes: all commits from Tasks 1-4 and the repository's documented test
  runner
- Produces: a reviewable completed branch, exact validation evidence, and a
  handoff directing the next chat to the separate simplification branch

- [ ] **Step 1: Review the complete branch for scope and compatibility**

Run:

```powershell
git diff --stat master...HEAD
git diff --name-status master...HEAD
git log --oneline --decorate master..HEAD
git diff master...HEAD -- tests/contracts/public_api_contract.json tests/contracts/stage0_behavior.json tests/contracts/corrected_behavior.json addon/blender_manifest.toml addon/dependencies.lock.json
```

Expected: no contract, manifest, wheel-lock, packer, updater-property, or
resolver implementation changes; commits correspond exactly to Tasks 1-4.

- [ ] **Step 2: Run non-Blender final validation**

Run:

```powershell
python -m unittest discover -s tests/unit -p "test_*.py"
python tools/verify_dependency_wheel.py
python -m ruff check .
git diff --check master...HEAD
```

Expected: all commands pass.

- [ ] **Step 3: Run all locally available Blender preservation gates**

Using a fresh temporary work directory per command, run source suites for:

```powershell
python tests/run_tests.py --blender $env:BLENDER_52 --work $env:TEMP\smc-final-api source --script tests/blender/verify_public_api.py --result r.json
python tests/run_tests.py --blender $env:BLENDER_52 --work $env:TEMP\smc-final-ui source --script tests/blender/verify_blender52_ui.py --result r.json
python tests/run_tests.py --blender $env:BLENDER_52 --work $env:TEMP\smc-final-life source --script tests/blender/verify_atomic_lifecycle.py --result r.json
python tests/run_tests.py --blender $env:BLENDER_52 --work $env:TEMP\smc-final-preflight source --script tests/blender/verify_preflight_failures.py --result r.json
python tests/run_tests.py --blender $env:BLENDER_52 --work $env:TEMP\smc-final-absent source --script tests/blender/verify_dependency_absent.py --result r.json --exclude-wheel
python tests/run_tests.py --blender $env:BLENDER_52 --work $env:TEMP\smc-final-atlas source --script tests/blender/verify_atlas_workflows.py --result r.json
python tests/run_tests.py --blender $env:BLENDER_52 --work $env:TEMP\smc-final-long source --script tests/blender/verify_atlas_workflows.py --result r.json --long-path
```

Do not claim foreground undo coverage on Windows. CI must supply Linux
foreground coverage and the three-platform matrix.

Build from `addon/`, derive the archive identity from the manifest, validate
source and archive, and run the installed-package suites:

```powershell
$extensionId = python -c "import tomllib; print(tomllib.load(open('addon/blender_manifest.toml','rb'))['id'])"
$extensionVersion = python -c "import tomllib; print(tomllib.load(open('addon/blender_manifest.toml','rb'))['version'])"
& $env:BLENDER_52 --factory-startup --command extension validate addon
& $env:BLENDER_52 --factory-startup --command extension build --source-dir addon --output-dir .packaged-releases
$archive = Resolve-Path ".packaged-releases/$extensionId-$extensionVersion.zip"
& $env:BLENDER_52 --factory-startup --command extension validate $archive
python tests/run_tests.py --blender $env:BLENDER_52 --work $env:TEMP\smc-final-pkg-dep package --package $archive --script tests/blender/verify_packaged_dependency.py --result r.json
python tests/run_tests.py --blender $env:BLENDER_52 --work $env:TEMP\smc-final-pkg-api package --package $archive --script tests/blender/verify_public_api.py --result r.json
python tests/run_tests.py --blender $env:BLENDER_52 --work $env:TEMP\smc-final-pkg-atlas package --package $archive --script tests/blender/verify_atlas_workflows.py --result r.json
```

Report that the ignored archive contains uncommitted changes. Fetch the pinned
CATS archive with the now-default strict policy and run the checkpoint:

```powershell
$catsOutput = Join-Path $env:TEMP "smc-cats-output.txt"
New-Item -ItemType File -Path $catsOutput -Force | Out-Null
python tools/fetch_cats.py --output-dir $env:TEMP\smc-final-cats --strict --github-output $catsOutput
$catsPath = (Get-Content $catsOutput | Where-Object { $_ -like 'extension=*' }).Substring(10)
$catsSha = (Get-Content $catsOutput | Where-Object { $_ -like 'extension_sha256=*' }).Substring(17)
python tests/run_tests.py --blender $env:BLENDER_52 --work $env:TEMP\smc-final-checkpoint checkpoint --package $archive --cats $catsPath --cats-sha256 $catsSha
```

Expected: source, archive, installed dependency/API/atlas, and CATS checkpoint
validation all pass. Network access is required only for the pinned CATS
fetch; if unavailable, report that checkpoint as unrun and require CI evidence
before merge.

- [ ] **Step 4: Perform correctness review before completion**

Use `superpowers:requesting-code-review` against `master...HEAD`. Resolve any
accepted feedback through `superpowers:receiving-code-review`, rerun the
affected RED/GREEN and preservation gates, and keep fixes within this branch's
security scope.

- [ ] **Step 5: Update the handoff with exact evidence**

Replace the active-branch section with:

- branch purpose and protected DNS decision;
- exact completed CATS and browser behavior;
- commands run, counts, platforms, and results;
- explicit unrun local/CI-only gates;
- confirmation that contracts, manifest, wheels, packers, and updater
  properties did not change;
- the recommended next action: review/publish this branch, then start a new
  chat and a new branch for compatibility-safe simplification only after this
  branch merges.

- [ ] **Step 6: Remove completed in-flight design artifacts**

After Tasks 1-5 are complete and verified, remove the design and plan with
`git rm`. This is required by `AGENTS.md`; their committed history preserves
the rationale.

Run:

```powershell
git rm -- docs/superpowers/specs/2026-08-08-security-hardening-design.md docs/superpowers/plans/2026-08-08-security-hardening.md
git add -- docs/HANDOFF.md
git diff --cached --check
git commit -m "docs: hand off completed security hardening"
```

- [ ] **Step 7: Run the final completion gate after the documentation commit**

Use `superpowers:verification-before-completion`, then run:

```powershell
python -m unittest discover -s tests/unit -p "test_*.py"
python tools/verify_dependency_wheel.py
python -m ruff check .
git diff --check master...HEAD
git status --short --untracked-files=all
git log --oneline --decorate master..HEAD
```

Expected: checks pass, working tree is clean, the completed spec/plan are
absent from the tree but present in branch history, and the branch is ready
for review/PR preparation. Do not push or open a PR without explicit approval.
