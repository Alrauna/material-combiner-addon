"""Resolve, attest, and normalize the CATS extension used by the checkpoint.

Remote mode downloads the latest final release and requires the official
GitHub CLI to verify its approved build provenance before the ZIP is parsed.
Both direct Blender extension ZIPs and legacy single-inner-ZIP wrappers are
accepted; the normalized extension archive is what the runner consumes.

Local --archive mode is explicitly unattested. The legacy --strict and
--allow-drift spellings remain accepted, but no option bypasses remote
attestation or dynamic identity checks.

Examples:
    python tools/fetch_cats.py --output-dir build/cats
    python tools/fetch_cats.py --output-dir build/cats --archive local.zip
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE_PATH = ROOT / "tools" / "cats_reference.json"
API = "https://api.github.com/repos/{repository}/releases/latest"
TIMEOUT_SECONDS = 120
ATTESTATION_TIMEOUT_SECONDS = 120
USER_AGENT = "material-combiner-addon-ci"
API_MAX_BYTES = 1 * 1024 * 1024
ASSET_MAX_BYTES = 64 * 1024 * 1024
EXTENSION_MAX_BYTES = 64 * 1024 * 1024
STREAM_CHUNK_BYTES = 64 * 1024


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_github_output(path: Path, **values: object) -> None:
    """Append step outputs, refusing any value that could inject a row.

    The extension path is derived from a remote release asset name, so a
    newline in it would let that name declare further outputs of its own.
    """
    for key, value in values.items():
        text = str(value)
        if "\n" in text or "\r" in text:
            raise ValueError(f"GitHub output must be single-line: {key}")
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        for key, value in values.items():
            stream.write(f"{key}={value}\n")


def api_token() -> str | None:
    """Return a GitHub token if CI supplied one.

    Anonymous API access is limited to 60 requests an hour per IP, and hosted
    runners share egress addresses, so an unauthenticated call fails
    intermittently with a 403. Authenticated calls are counted per repository
    instead.
    """
    for name in ("GH_TOKEN", "GITHUB_TOKEN"):
        token = os.environ.get(name)
        if token:
            return token
    return None


def _open(url: str, accept: str, token: str | None = None):
    if not url.startswith("https://"):
        raise ValueError("HTTPS is required")
    headers = {"Accept": accept, "User-Agent": USER_AGENT}
    if token:
        # Only ever sent to the API host. Asset downloads redirect to a CDN,
        # and urllib replays request headers across redirects, so attaching
        # the token there would hand it to another host.
        if not url.startswith("https://api.github.com/"):
            raise ValueError("refusing to send a token off the API host")
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    response = urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS)
    try:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status} for {url}")
        # Release assets redirect to a CDN, so redirects must be followed.
        # urllib would follow one to plain HTTP, so check where it landed.
        if not response.url.startswith("https://"):
            raise RuntimeError(f"redirected off HTTPS: {response.url}")
        return response
    except Exception:
        response.close()
        raise


def _copy_bounded(source, destination, maximum: int, label: str) -> int:
    total = 0
    while chunk := source.read(STREAM_CHUNK_BYTES):
        total += len(chunk)
        if total > maximum:
            raise RuntimeError(f"{label} exceeds {maximum} bytes")
        destination.write(chunk)
    return total


def _get(url: str, accept: str, token: str | None = None) -> bytes:
    with _open(url, accept, token) as response:
        destination = io.BytesIO()
        _copy_bounded(response, destination, API_MAX_BYTES, "API response")
        return destination.getvalue()


def _download(
    url: str,
    output: Path,
    maximum: int = ASSET_MAX_BYTES,
) -> int:
    try:
        with _open(url, "application/octet-stream") as response:
            with output.open("wb") as destination:
                return _copy_bounded(
                    response,
                    destination,
                    maximum,
                    "release asset",
                )
    except Exception:
        output.unlink(missing_ok=True)
        raise


def resolve_latest(repository: str) -> tuple[str, str, str, int, str]:
    """Return the latest release tag and ZIP asset facts."""
    payload = json.loads(
        _get(
            API.format(repository=repository),
            "application/vnd.github+json",
            token=api_token(),
        )
    )
    if payload.get("draft") is not False or payload.get("prerelease") is not False:
        raise RuntimeError("Latest release is not final")
    source_digest = payload.get("target_commitish")
    if not isinstance(source_digest, str) or re.fullmatch(
        r"[0-9a-fA-F]{40}", source_digest
    ) is None:
        raise RuntimeError("Latest release target is not an exact commit")
    assets = [
        asset
        for asset in payload.get("assets", [])
        if asset["name"].endswith(".zip")
    ]
    if len(assets) != 1:
        raise RuntimeError(
            f"Expected exactly one ZIP asset, found {len(assets)}"
        )
    asset = assets[0]
    size = asset.get("size")
    if not isinstance(size, int) or size < 0:
        raise RuntimeError("Release asset has no valid published size")
    return (
        payload["tag_name"],
        asset["name"],
        asset["browser_download_url"],
        size,
        source_digest.lower(),
    )


def verify_attestation(
    archive: Path,
    *,
    repository: str,
    certificate_identity: str,
    source_ref: str,
    source_digest: str,
) -> None:
    executable = shutil.which("gh")
    if executable is None:
        raise RuntimeError("GitHub CLI is required to verify CATS provenance")
    try:
        subprocess.run(
            [
                executable,
                "attestation",
                "verify",
                str(archive),
                "--repo",
                repository,
                "--cert-identity",
                certificate_identity,
                "--source-ref",
                source_ref,
                "--source-digest",
                source_digest,
                "--deny-self-hosted-runners",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=ATTESTATION_TIMEOUT_SECONDS,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        raise RuntimeError(
            "CATS build-provenance verification failed"
        ) from error


def unwrap(archive: Path, expected_name: str, output_dir: Path) -> Path:
    """Return the installable extension ZIP, unwrapping a wrapper archive.

    A wrapper contains exactly one entry, itself a ZIP. Anything else is
    assumed to already be the installable extension.
    """
    with zipfile.ZipFile(archive) as outer:
        entries = [info for info in outer.infolist() if not info.is_dir()]
        if len(entries) == 1 and entries[0].filename.endswith(".zip"):
            inner_path = output_dir / Path(entries[0].filename).name
            try:
                with outer.open(entries[0]) as source:
                    with inner_path.open("wb") as destination:
                        _copy_bounded(
                            source,
                            destination,
                            EXTENSION_MAX_BYTES,
                            "extension archive",
                        )
                return inner_path
            except Exception:
                inner_path.unlink(missing_ok=True)
                raise
        if any(
            info.filename.endswith("blender_manifest.toml")
            for info in entries
        ):
            destination = output_dir / expected_name
            if destination.resolve() != archive.resolve():
                shutil.copyfile(archive, destination)
            return destination
    raise RuntimeError(f"Not a CATS extension archive: {archive}")


def extension_manifest_of(archive: Path) -> dict[str, object] | None:
    with zipfile.ZipFile(archive) as package:
        manifests = [
            name
            for name in package.namelist()
            if name.endswith("blender_manifest.toml")
        ]
        if not manifests:
            return None
        text = package.read(manifests[0]).decode("utf-8")
    # Parse properly rather than matching a line prefix: "idle" and
    # "identifier" both start with "id", so a crafted manifest could satisfy
    # the id check while declaring a different extension.
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return None


def extension_id_of(archive: Path) -> str | None:
    manifest = extension_manifest_of(archive)
    if manifest is None:
        return None
    value = manifest.get("id")
    return value if isinstance(value, str) else None


def fetch(
    output_dir: Path,
    archive: Path | None,
    allow_drift: bool = False,
) -> tuple[dict[str, object], int]:
    reference = json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))
    output_dir.mkdir(parents=True, exist_ok=True)
    drift: list[str] = []
    attestation_verified = False
    source_digest = None

    if archive is not None:
        asset_path = archive
        asset_name = archive.name
        tag = "(local archive)"
        published_asset_size = None
    else:
        (
            tag,
            asset_name,
            url,
            published_asset_size,
            source_digest,
        ) = resolve_latest(reference["repository"])
        # asset_name comes from the API response, so keep it to a bare
        # filename rather than trusting it to be path-safe.
        asset_path = output_dir / Path(asset_name).name
        _download(url, asset_path)
        verify_attestation(
            asset_path,
            repository=reference["repository"],
            certificate_identity=reference["certificate_identity"],
            source_ref=reference["source_ref"],
            source_digest=source_digest,
        )
        attestation_verified = True

    asset_size = asset_path.stat().st_size
    asset_sha256 = sha256_file(asset_path)
    if archive is None and asset_size != published_asset_size:
        drift.append(
            f"downloaded asset size {asset_size} does not match published "
            f"size {published_asset_size}"
        )

    extension = unwrap(
        asset_path, reference["extension_zip_name"], output_dir
    )
    extension_size = extension.stat().st_size
    extension_sha256 = sha256_file(extension)

    manifest = extension_manifest_of(extension)
    actual_id = manifest.get("id") if manifest is not None else None
    actual_version = (
        manifest.get("version") if manifest is not None else None
    )
    if actual_id != reference["extension_id"]:
        drift.append(
            f"extension id is {actual_id!r}, expected "
            f"{reference['extension_id']!r}"
        )
    if archive is None and (
        not isinstance(actual_version, str) or not actual_version
    ):
        drift.append("extension manifest has no valid version")
    if archive is None and isinstance(actual_version, str) and actual_version:
        expected_tag = f"v{actual_version}"
        expected_asset_name = f"cats_blender_plugin-{actual_version}.zip"
        if tag != expected_tag:
            drift.append(
                f"release tag is {tag!r}, expected {expected_tag!r}"
            )
        if asset_name != expected_asset_name:
            drift.append(
                f"asset name is {asset_name!r}, expected "
                f"{expected_asset_name!r}"
            )

    report = {
        "repository": reference["repository"],
        "release_tag": tag,
        "source_digest": source_digest,
        "attestation_verified": attestation_verified,
        "asset": str(asset_path),
        "asset_size": asset_size,
        "published_asset_size": published_asset_size,
        "asset_sha256": asset_sha256,
        "extension": str(extension),
        "extension_size": extension_size,
        "extension_sha256": extension_sha256,
        "extension_id": actual_id,
        "extension_version": actual_version,
        "drift": drift,
        "drift_is_fatal": True,
    }
    if drift:
        return report, 1
    return report, 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--archive",
        type=Path,
        help="Use a local archive instead of downloading, for offline runs.",
    )
    policy = parser.add_mutually_exclusive_group()
    policy.add_argument(
        "--strict",
        action="store_true",
        help="Require attested CATS provenance (retained for compatibility).",
    )
    policy.add_argument(
        "--allow-drift",
        action="store_true",
        help="Retained for local compatibility; cannot bypass remote checks.",
    )
    parser.add_argument(
        "--github-output",
        type=Path,
        help="Append the unwrapped extension path for a later CI step.",
    )
    arguments = parser.parse_args(argv)

    if arguments.strict and arguments.archive is not None:
        print(
            "error: strict provenance cannot be established for a local archive",
            file=sys.stderr,
        )
        return 1

    report, exit_code = fetch(
        arguments.output_dir,
        arguments.archive,
        allow_drift=arguments.allow_drift,
    )
    print(json.dumps(report, indent=2))
    if arguments.github_output is not None and exit_code == 0:
        write_github_output(
            arguments.github_output,
            extension=report["extension"],
            extension_sha256=report["extension_sha256"],
        )
    for message in report["drift"]:
        level = "error" if report["drift_is_fatal"] else "warning"
        print(f"{level}: CATS reference drift: {message}", file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
