"""Acquire a verified Blender for CI.

Blender is downloaded, not trusted. The official checksum manifest is fetched
three times over independent DNS resolvers and all three responses must be
byte-identical before the archive hash is compared against the value committed
below. A single poisoned resolver therefore cannot substitute a build.

Example:
    python tools/ci.py prepare-blender --platform linux \\
        --output-dir /tmp/blender --github-output "$GITHUB_OUTPUT"
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse


BLENDER_VERSION = "5.2.0"
BASE_URL = "https://download.blender.org/release/Blender5.2"
CHECKSUM_URL = f"{BASE_URL}/blender-{BLENDER_VERSION}.sha256"

# Independent resolvers. The first uses whatever DNS the runner is configured
# with; the others bypass it entirely. All three must return a byte-identical
# manifest, so an unreachable resolver fails the build: only endpoints
# confirmed reachable belong here. Quad9 was tried and could not resolve
# through curl's DoH client on the development network, so it is not used.
RESOLVERS = (
    None,
    "https://cloudflare-dns.com/dns-query",
    "https://dns.google/dns-query",
)

CONNECT_TIMEOUT_SECONDS = 30
TOTAL_TIMEOUT_SECONDS = 900
PROCESS_TIMEOUT_SECONDS = 960
RETRIES = 2

PLATFORMS = {
    "windows": {
        "filename": f"blender-{BLENDER_VERSION}-windows-x64.zip",
        "sha256": (
            "2d184b626c001692c362291911293b6a"
            "297179d618d95e9e9192c3a80318adc4"
        ),
        "executable": "blender.exe",
        "python_glob": "python.exe",
    },
    "linux": {
        "filename": f"blender-{BLENDER_VERSION}-linux-x64.tar.xz",
        "sha256": (
            "96f6c181a30f4950607839dc84d42a35"
            "4b250d8a0231b098b59b7bc69c351c48"
        ),
        "executable": "blender",
        "python_glob": "python3.*",
    },
}


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def parse_checksum_manifest(payload: bytes) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in payload.decode("utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) != 2 or len(parts[0]) != 64:
            raise ValueError(f"malformed checksum row: {line!r}")
        digest, filename = parts[0].lower(), parts[1].removeprefix("*")
        if filename in result:
            raise ValueError(f"duplicate checksum entry: {filename}")
        result[filename] = digest
    if not result:
        raise ValueError("empty checksum manifest")
    return result


def require_consensus(
    payloads: list[bytes], filename: str, expected_sha256: str
) -> None:
    """Every resolver must agree, and agree with the committed hash."""
    if len(set(payloads)) != 1:
        raise ValueError("resolvers disagree about the checksum manifest")
    published = parse_checksum_manifest(payloads[0]).get(filename)
    if published is None:
        raise ValueError(f"checksum entry is missing: {filename}")
    if published != expected_sha256:
        raise ValueError(
            "published checksum does not match the committed value: "
            f"published {published}, committed {expected_sha256}"
        )


def download(url: str, output: Path, doh_url: str | None = None) -> None:
    if urlparse(url).scheme != "https":
        raise ValueError("HTTPS is required")
    command = [
        "curl",
        "--proto", "=https",
        "--tlsv1.2",
        "--fail",
        "--silent",
        "--show-error",
        "--location",
        "--connect-timeout", str(CONNECT_TIMEOUT_SECONDS),
        "--max-time", str(TOTAL_TIMEOUT_SECONDS),
        "--retry", str(RETRIES),
        "--retry-delay", "2",
        "--retry-all-errors",
        "--output", str(output),
        "--write-out", "%{http_code}",
    ]
    if doh_url:
        if urlparse(doh_url).scheme != "https":
            raise ValueError("DNS-over-HTTPS requires HTTPS")
        command += ["--doh-url", doh_url]
    command.append(url)

    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=PROCESS_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        output.unlink(missing_ok=True)
        raise RuntimeError(f"download timed out: {url}") from exc
    if result.returncode or result.stdout.strip() != "200":
        output.unlink(missing_ok=True)
        raise RuntimeError(
            f"download failed: curl={result.returncode} "
            f"http={result.stdout.strip()!r} {result.stderr.strip()}"
        )


def bundled_python(blender: Path, glob: str) -> Path:
    candidates = [
        path
        for path in blender.parent.joinpath(
            BLENDER_VERSION.rsplit(".", 1)[0], "python", "bin"
        ).glob(glob)
        if path.is_file() and "config" not in path.name
    ]
    if not candidates:
        raise ValueError("bundled Python executable was not found")
    return min(candidates, key=lambda path: len(path.name)).resolve()


def prepare_blender(
    platform: str, output_dir: Path, github_output: Path | None
) -> tuple[Path, Path]:
    metadata = PLATFORMS[platform]
    output_dir.mkdir(parents=True, exist_ok=True)

    payloads: list[bytes] = []
    for index, resolver in enumerate(RESOLVERS):
        path = output_dir / f"checksums-{index}.txt"
        download(CHECKSUM_URL, path, resolver)
        payloads.append(path.read_bytes())
    require_consensus(payloads, metadata["filename"], metadata["sha256"])

    archive = output_dir / metadata["filename"]
    download(f"{BASE_URL}/{metadata['filename']}", archive)
    actual = sha256_file(archive)
    if actual != metadata["sha256"]:
        raise ValueError(
            f"archive hash mismatch: expected {metadata['sha256']}, "
            f"got {actual}"
        )

    extracted = output_dir / "blender"
    if platform == "linux":
        shutil.unpack_archive(archive, extracted, filter="data")
    else:
        shutil.unpack_archive(archive, extracted)

    root = metadata["filename"]
    for suffix in (".tar.xz", ".zip"):
        root = root.removesuffix(suffix)
    blender = (extracted / root / metadata["executable"]).resolve()
    if not blender.is_file():
        raise ValueError(f"expected Blender executable at {blender}")

    reported = subprocess.run(
        [str(blender), "--version"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()[0].strip()
    if reported != f"Blender {BLENDER_VERSION} LTS":
        raise ValueError(f"unexpected Blender version: {reported!r}")

    python = bundled_python(blender, metadata["python_glob"])
    if github_output is not None:
        with github_output.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(f"blender={blender}\n")
            stream.write(f"python={python}\n")
    print(f"blender: {blender}")
    print(f"python:  {python}")
    return blender, python


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare-blender")
    prepare.add_argument("--platform", choices=tuple(PLATFORMS), required=True)
    prepare.add_argument("--output-dir", type=Path, required=True)
    prepare.add_argument("--github-output", type=Path)
    arguments = parser.parse_args(argv)

    if arguments.command == "prepare-blender":
        prepare_blender(
            arguments.platform,
            arguments.output_dir,
            arguments.github_output,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
