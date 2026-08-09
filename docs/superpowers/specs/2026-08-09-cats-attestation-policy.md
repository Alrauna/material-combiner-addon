# CATS Consumption and Material Combiner Release Attestation Design

## Objective

Make Material Combiner 3.1.1 test against the latest final CATS release without
committing a CATS version, tag, commit, size, or hash. The downloaded artifact
is trusted only when GitHub verifies its build-provenance attestation against
the approved CATS repository and release workflow, after which the existing
Blender checkpoint proves compatibility. Material Combiner's own release
workflow must also generate GitHub build-provenance attestations for every
published extension ZIP before making the release public.

## Scope

Only `Alrauna/material-combiner-addon` changes. CATS and Alpha Material
Separator remain independent repositories and receive no workflow or product
changes. Their existing build/attest/publish workflows are producer-side
examples, not reverse-dependency test targets. Material Combiner adopts Alpha
Material Separator's privilege-separated artifact handoff, adapted to its four
release ZIPs and existing dry-run behavior.

Material Combiner's extension API, operators, RNA properties, imports,
registration behavior, bundled Pillow model, packaging layout, Blender support
matrix, atlas behavior, and CATS checkpoint assertions remain unchanged. The
extension manifest version changes from 3.1.0 to 3.1.1.

## Trust model

`tools/fetch_cats.py` resolves GitHub's latest final release endpoint for
`Alrauna/Cats-Blender-Plugin`. No resolved release identity is compared with a
committed release snapshot. Before the downloaded ZIP is parsed or installed,
the official GitHub CLI must successfully verify its default SLSA provenance
with all of these constraints:

- repository: `Alrauna/Cats-Blender-Plugin`;
- signer workflow:
  `Alrauna/Cats-Blender-Plugin/.github/workflows/Cats Tests.yml`;
- source ref: `refs/heads/main`;
- source digest: the exact 40-hex commit reported by that release; and
- self-hosted runners denied.

The source digest is resolved for each release and is not committed. The signer
workflow digest is deliberately not pinned: reviewed and protected `main` is
the moving trust boundary. The tool does not implement Sigstore verification;
it delegates cryptography and certificate-policy enforcement to
`gh attestation verify` and fails closed on a missing executable, timeout,
nonzero result, or malformed release source digest.

Attestation is the sole artifact-provenance decision. GitHub's published size,
the locally computed SHA-256, and the checkpoint's `--cats-sha256` remain
transport and same-file integrity facts, not committed trust pins. The tool
does not require `SHA256SUMS.txt` to trust an artifact.

## Material Combiner release provenance

The release workflow separates three capabilities:

1. `release_package` checks out the exact public `github.sha`, builds and
   validates the universal archive plus all three platform archives, generates
   `SHA256SUMS.txt`, and uploads exactly those five files as a short-lived,
   uncompressed workflow artifact. It has only `contents: read`.
2. `release_attestation` downloads that named artifact from the current
   workflow run, rejects missing or extra entries, verifies every ZIP against
   the package job's checksum manifest, and invokes the SHA-pinned
   `actions/attest` action over all four ZIP paths. It has only `actions: read`,
   `contents: read`, `id-token: write`, and `attestations: write`; it cannot
   modify repository contents or releases.
3. `release_publish` depends on successful packaging and attestation,
   independently downloads and verifies the same current-run artifact, and is
   the only job with `contents: write` and the protected `release` environment.
   It retains the existing refuse-existing, draft, upload, stored-byte rehash,
   and publish sequence.

The artifact handoff is bound to `GITHUB_RUN_ID`, a fixed artifact name, the
exact five-entry set, and `SHA256SUMS.txt`. Artifact compression is disabled so
GitHub does not wastefully recompress extension ZIPs, and retention is one day.
The attestation covers the four distributable ZIPs; the checksum manifest is a
published integrity index rather than a release subject. GitHub's official
action supports multiple path subjects in one provenance statement.

Real release dispatches run only from the repository's protected release
branch when the repository is public and must pass attestation before
publication. Dry runs execute the same checkout, build, validation, checksum,
and artifact-handoff path, then stop: they create neither a public release nor
a public attestation for unreleased rehearsal bytes. Leaving the release input
empty remains validation only.

## Dynamic identity and packaging checks

After attestation succeeds, existing bounded ZIP handling may inspect the
artifact. The extension manifest must identify `cats_blender_plugin`. The
manifest version must be a nonempty string, the release tag must equal
`v<manifest version>`, and the single release ZIP asset must be named
`cats_blender_plugin-<manifest version>.zip`. These comparisons move with the
release and detect a mislabeled or accidentally packaged release; none selects
or pins a particular version.

The fetcher continues to accept a direct Blender extension ZIP and the legacy
single-inner-ZIP wrapper because archive normalization is already covered and
costs no additional trust. API responses, downloads, extracted inner archives,
and GitHub outputs retain their existing bounds and injection protections. API
authentication remains restricted to `api.github.com`; the token is never
forwarded to the release CDN.

## Local archive behavior and compatibility

`--archive` remains available for explicit offline compatibility work. A local
archive has no dynamically resolved release or attestation, so the tool must
label it `attestation_verified: false`; it may validate the archive structure
and extension ID but must not claim provenance. `--strict --archive` fails
because strict provenance cannot be established offline. Plain `--archive` and
`--archive --allow-drift` remain usable for deliberate local inspection.

The legacy `--strict` and `--allow-drift` spellings remain accepted. For remote
downloads, neither flag can bypass attestation or dynamic identity checks;
normal remote operation and `--strict` are equivalent. Existing JSON report
fields and GitHub outputs remain available where meaningful so downstream test
runner integration does not change.

## Failure behavior

CI fails before Blender installation when:

- latest-release metadata is malformed, draft, or prerelease;
- the release does not expose exactly one ZIP asset;
- the source commit is not a full SHA-1 value;
- download or archive bounds are exceeded;
- GitHub CLI is unavailable or attestation verification fails;
- the attestation identity, workflow, ref, digest, or runner policy fails;
- the archive is not a Blender extension or has the wrong extension ID; or
- tag, asset name, and manifest version disagree.

An attested, correctly packaged but API-incompatible CATS update proceeds to
the existing checkpoint and fails its unchanged integration, restart, or
uninstall assertions. A compatible attested update passes without a Material
Combiner change.

## Test strategy

Unit tests must first demonstrate that the policy file contains no immutable
CATS release facts; arbitrary future versions pass when tag, name, manifest,
and attestation agree; and attestation failure cannot be bypassed with
`--allow-drift`. Tests mock the `gh` process boundary and assert the complete
argument vector, including repository, workflow, main ref, dynamic source
digest, and hosted-runner restriction. Existing bounded-input, token-isolation,
archive, wrong-ID, GitHub-output, checkpoint-hash, and CLI-conflict coverage is
preserved.

Workflow contract tests first fail against the current single release job,
then require the package/attestation/publish dependency chain, exact
least-privilege permissions, current-run named-artifact download, exact file
set and checksum verification, a SHA-pinned `actions/attest` invocation over
all four ZIPs, and publication only after attestation. They also prove dry runs
package and expose inspectable artifacts without invoking attestation or
release mutation. Existing release identity and archive-set unit tests remain
unchanged.

Final validation includes all unit tests, Ruff, dependency-wheel verification,
source and package validation with Blender 5.2, the relevant source/package
suites, and a live strict CATS fetch plus checkpoint. Because local GitHub CLI
2.97.0 currently reports `Error: verifying with issuer "sigstore.dev"`, a
GitHub-hosted validation run is a required acceptance gate for the real CATS
verification command; API presence alone is not accepted as cryptographic
verification. A hosted real-release rehearsal or the authorized 3.1.1 release
must additionally prove that all four Material Combiner ZIP digests receive
attestations and that publication cannot run when attestation fails.
