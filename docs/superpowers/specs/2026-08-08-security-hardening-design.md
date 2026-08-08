# Security Hardening Design

## Scope

This milestone hardens the development-time CATS acquisition path and the
runtime browser operator while preserving every public extension interface.
It also records the CI resolver design as an explicit repository invariant.

Internal test deduplication and compatibility-safe cleanup are a separate
milestone and branch. They are intentionally excluded here so trust-boundary
changes remain independently reviewable.

## Global constraints

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

## Protected CI resolver design

`tools/ci.py` deliberately obtains Blender's official checksum manifest
through three independent resolver paths: the runner resolver, Cloudflare
DNS-over-HTTPS through curl, and a hand-written Quad9 DNS-over-TLS client whose
addresses are passed to curl with `--resolve`. All three payloads must agree,
and the resulting checksum must also match the committed SHA-256 pin.

This independence is a security design property, not cleanup debt. `AGENTS.md`
will state that the hand-written DNS parser, separate resolver
implementations, three-way consensus, and committed pin must remain. A future
replacement is allowed only if it preserves all four properties and their
regression coverage. This milestone does not modify `tools/ci.py` or its
tests.

## CATS acquisition policy

Hash, tag, asset-name, size, or extension-version drift will fail by default.
Developers may deliberately inspect an unpinned release with an explicit
`--allow-drift` option. The existing `--strict` option remains accepted for
CLI compatibility and selects the default fail-closed behavior. Supplying
both options is an error because their intent conflicts.

The module-level `HASH_MISMATCH_IS_FATAL` switch will be removed. Policy will
be visible at the command line rather than hidden in source edits.

The expected extension ID remains unconditionally enforced. `--allow-drift`
does not permit a different extension ID.

## Bounded download and archive handling

The GitHub API response will be read with a small fixed byte limit. Release
assets will be streamed directly to their destination instead of first being
held as one `bytes` object. Downloads and inner ZIP members will have fixed
maximum sizes comfortably above the pinned CATS artifact but low enough to
prevent unbounded memory or disk consumption.

The existing committed `asset_size` and `extension_size` fields will become
active integrity facts. A mismatch is drift: fatal by default and reportable
under `--allow-drift`. Fixed maximum limits always remain fatal, including
under `--allow-drift`.

HTTPS enforcement, token host restriction, redirect validation, filename
normalization, SHA-256 verification, extension-ID verification, and GitHub
output newline rejection remain intact.

## Browser URL validation

The public `operators.browser.OpenBrowser` class, `smc.browser` identifier,
`link` RNA property, registration, and `execute()` result conventions remain
unchanged.

Validation will use `urllib.parse.urlsplit` and will accept complete HTTPS
URLs that have a hostname and may contain a port, path, query, or fragment. It
will reject HTTP, credentials, whitespace or control characters, missing
hosts, and parse errors. `webbrowser.open()` will only receive a value that
passes the complete validation.

This deliberately tightens behavior without changing the extension API. All
current project-owned links already use HTTPS.

## Error behavior

CATS acquisition failures will continue to return a nonzero process status
and emit a JSON report where practical. Limit violations must identify which
boundary failed without printing tokens or response bodies. Drift warnings
under `--allow-drift` remain visible on standard error.

The browser operator will continue to report a concise Blender error and
return `{"CANCELLED"}` for invalid input or browser-launch failure.

## Test design

Development follows RED/GREEN TDD.

Unit coverage for `tools/fetch_cats.py` will prove:

- drift fails without flags;
- `--allow-drift` permits ordinary drift and reports it;
- legacy `--strict` remains accepted;
- conflicting flags fail;
- extension-ID mismatch is never permitted;
- API, asset, and inner-member limits reject oversized input;
- exact pinned sizes pass and size drift follows the selected policy;
- streamed downloads retain HTTPS, redirect, token, hash, and output safety.

Blender coverage will prove that `smc.browser` accepts a normal HTTPS URL and
rejects HTTP, credentials, whitespace, control characters, missing hosts, and
malformed ports without launching a browser.

Preservation gates are:

1. `python -m unittest discover -s tests/unit -p "test_*.py"`
2. `python tools/verify_dependency_wheel.py`
3. `python -m ruff check .`
4. Blender 5.2 source public-API, UI, lifecycle, preflight,
   dependency-absent, and atlas suites
5. Blender 5.2 package public-API, dependency, and atlas suites
6. the approved CATS checkpoint suite
7. `git diff --check`
8. confirmation that public and behavioral contract files are unchanged

CI remains responsible for the full Windows x64, Linux x64, and macOS arm64
matrix, Linux foreground atlas coverage, and Windows long-path coverage.

## Compatibility-safe simplification follow-up

After this branch merges, a new branch from updated `master` will receive its
own design and plan. Its intended scope is limited to:

- centralizing the repeated Blender test network/process denial harness while
  preserving every patched function, counter, assertion, and suite;
- replacing dependency-status dataclass reconstruction with
  `dataclasses.replace`;
- documenting the unused updater preference fields as retained compatibility
  shims without removing or changing them.

All three packers, their identifiers, updater properties/defaults, public
contracts, and test strength remain unchanged.
