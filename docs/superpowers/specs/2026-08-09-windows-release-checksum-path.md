# Windows Release Checksum Path Design

## Problem

Release run 31317909983 produced and transported `SHA256SUMS.txt` unchanged.
Its downloaded SHA-256 exactly matched the package job output
`cef974c759a85c44a9d99d8f03408089e05cf053047060f31bf57017585d0b87`.
On Git Bash for Windows, however, GNU `sha256sum` prefixes its output with `\`
when an absolute filename contains backslashes. The workflow's `awk` parser
therefore compared a 65-character escaped value with the expected 64-character
digest and failed before attestation. The same parser shape exists in the
publication handoff check and stored-release ZIP check.

The failure was safe: attestation stopped, publication was skipped, and no
`v3.1.1` tag or release was created.

## Approved design

Keep the Windows release jobs and every existing security gate. Compute hashes
from inside their containing directory and pass only relative filenames to
`sha256sum`. Relative filenames contain no backslashes, so GNU coreutils emits
an ordinary digest field on Windows while hashing the same bytes.

Change only the three affected commands in `.github/workflows/ci.yml`. Add a
workflow contract that requires relative-path hashing in both artifact
consumers and the stored-release verification loop. Do not normalize or strip
the digest, change artifact bytes, weaken exact inventory or checksum checks,
change permissions, or bypass attestation.

## Acceptance

- The regression contract fails against the current absolute-path commands.
- Both artifact consumers hash `SHA256SUMS.txt` from `$download`.
- Stored release ZIPs are hashed by filename from `$stored`.
- Existing release security and ordering contracts remain green.
- The original Git Bash reproduction returns a 64-character expected digest
  with the new relative-path command.
- Full unit, Ruff, dependency-wheel, and diff checks pass.

