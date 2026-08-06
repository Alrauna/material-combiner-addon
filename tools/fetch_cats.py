"""Resolve, download, and verify the CATS extension used by the checkpoint.

The published release asset is a wrapper: a ZIP whose only entry is the
installable extension ZIP. Blender cannot install the wrapper, so it is
unwrapped here and the inner archive is what the runner consumes.

Hash drift is reported but does not fail the run. The CATS repository has not
yet adopted the same release automation as this one, so its artifacts are
expected to move. Flip HASH_MISMATCH_IS_FATAL, or pass --strict, once the two
repositories are aligned.

Examples:
    python tools/fetch_cats.py --output-dir build/cats
    python tools/fetch_cats.py --output-dir build/cats --strict
    python tools/fetch_cats.py --output-dir build/cats --archive local.zip
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import ssl
import sys
import urllib.request
import zipfile
from pathlib import Path


# One-line switch: set to True to make any hash or tag drift fail the run.
HASH_MISMATCH_IS_FATAL = False

ROOT = Path(__file__).resolve().parents[1]
REFERENCE_PATH = ROOT / "tools" / "cats_reference.json"
API = "https://api.github.com/repos/{repository}/releases/latest"
TIMEOUT_SECONDS = 120
USER_AGENT = "material-combiner-addon-ci"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _get(url: str, accept: str) -> bytes:
    if not url.startswith("https://"):
        raise ValueError("HTTPS is required")
    request = urllib.request.Request(
        url, headers={"Accept": accept, "User-Agent": USER_AGENT}
    )
    context = ssl.create_default_context()
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    with urllib.request.urlopen(
        request, timeout=TIMEOUT_SECONDS, context=context
    ) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status} for {url}")
        return response.read()


def resolve_latest(repository: str) -> tuple[str, str, str]:
    """Return the latest release tag, asset name, and asset download URL."""
    payload = json.loads(
        _get(
            API.format(repository=repository),
            "application/vnd.github+json",
        )
    )
    assets = [
        asset
        for asset in payload.get("assets", [])
        if asset["name"].endswith(".zip")
    ]
    if len(assets) != 1:
        raise RuntimeError(
            f"Expected exactly one ZIP asset, found {len(assets)}"
        )
    return payload["tag_name"], assets[0]["name"], assets[0][
        "browser_download_url"
    ]


def unwrap(archive: Path, expected_name: str, output_dir: Path) -> Path:
    """Return the installable extension ZIP, unwrapping a wrapper archive.

    A wrapper contains exactly one entry, itself a ZIP. Anything else is
    assumed to already be the installable extension.
    """
    with zipfile.ZipFile(archive) as outer:
        entries = [name for name in outer.namelist() if not name.endswith("/")]
        if len(entries) == 1 and entries[0].endswith(".zip"):
            inner_path = output_dir / Path(entries[0]).name
            inner_path.write_bytes(outer.read(entries[0]))
            return inner_path
        if any(name.endswith("blender_manifest.toml") for name in entries):
            destination = output_dir / expected_name
            if destination.resolve() != archive.resolve():
                shutil.copyfile(archive, destination)
            return destination
    raise RuntimeError(f"Not a CATS extension archive: {archive}")


def extension_id_of(archive: Path) -> str | None:
    with zipfile.ZipFile(archive) as package:
        manifests = [
            name
            for name in package.namelist()
            if name.endswith("blender_manifest.toml")
        ]
        if not manifests:
            return None
        text = package.read(manifests[0]).decode("utf-8")
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("id"):
            _, _, value = stripped.partition("=")
            return value.strip().strip('"')
    return None


def fetch(
    output_dir: Path, archive: Path | None, strict: bool
) -> tuple[dict[str, object], int]:
    reference = json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))
    output_dir.mkdir(parents=True, exist_ok=True)
    drift: list[str] = []

    if archive is not None:
        asset_path = archive
        tag = "(local archive)"
    else:
        tag, asset_name, url = resolve_latest(reference["repository"])
        if tag != reference["release_tag"]:
            drift.append(
                f"release tag moved: recorded {reference['release_tag']}, "
                f"published {tag}"
            )
        if asset_name != reference["asset_name"]:
            drift.append(
                f"asset renamed: recorded {reference['asset_name']}, "
                f"published {asset_name}"
            )
        asset_path = output_dir / asset_name
        asset_path.write_bytes(_get(url, "application/octet-stream"))

    asset_sha256 = sha256_file(asset_path)
    if archive is None and asset_sha256 != reference["asset_sha256"]:
        drift.append(
            f"asset sha256 changed: recorded {reference['asset_sha256']}, "
            f"downloaded {asset_sha256}"
        )

    extension = unwrap(
        asset_path, reference["extension_zip_name"], output_dir
    )
    extension_sha256 = sha256_file(extension)
    if extension_sha256 != reference["extension_sha256"]:
        drift.append(
            "extension sha256 changed: recorded "
            f"{reference['extension_sha256']}, got {extension_sha256}"
        )

    actual_id = extension_id_of(extension)
    fatal = actual_id != reference["extension_id"]
    if fatal:
        drift.append(
            f"extension id is {actual_id!r}, expected "
            f"{reference['extension_id']!r}"
        )

    report = {
        "repository": reference["repository"],
        "release_tag": tag,
        "asset": str(asset_path),
        "asset_sha256": asset_sha256,
        "extension": str(extension),
        "extension_sha256": extension_sha256,
        "extension_id": actual_id,
        "drift": drift,
        "drift_is_fatal": bool(strict or HASH_MISMATCH_IS_FATAL),
    }
    # A wrong extension id always fails: the checkpoint cannot enable it, so
    # continuing would only produce a confusing downstream error.
    if fatal:
        return report, 1
    if drift and (strict or HASH_MISMATCH_IS_FATAL):
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
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat drift as a failure instead of a warning.",
    )
    arguments = parser.parse_args(argv)

    report, exit_code = fetch(
        arguments.output_dir, arguments.archive, arguments.strict
    )
    print(json.dumps(report, indent=2))
    for message in report["drift"]:
        level = "error" if report["drift_is_fatal"] else "warning"
        print(f"{level}: CATS reference drift: {message}", file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
