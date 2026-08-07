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
import ipaddress
import re
import secrets
import shutil
import socket
import ssl
import struct
import subprocess
import tomllib
from pathlib import Path
from urllib.parse import urlparse


BLENDER_VERSION = "5.2.0"
BASE_URL = "https://download.blender.org/release/Blender5.2"
CHECKSUM_URL = f"{BASE_URL}/blender-{BLENDER_VERSION}.sha256"

# Three independent resolution paths, each fetching the checksum manifest:
#
#   1. whatever DNS the runner is configured with
#   2. Cloudflare, over DNS-over-HTTPS, through curl
#   3. Quad9, over DNS-over-TLS, resolved here and handed to curl via --resolve
#
# The third deliberately does not use curl's DoH client. Speaking DNS-over-TLS
# directly keeps the resolution independent of curl's implementation, so a
# defect or a compromise in one client cannot silently affect all three paths.
CLOUDFLARE_DOH_URL = "https://cloudflare-dns.com/dns-query"
QUAD9_DOT_HOST = "dns.quad9.net"
QUAD9_DOT_PORT = 853
MAX_RESOLVED_ADDRESSES = 16

# A release is X.Y.Z only. Prerelease suffixes are rejected so a tag can
# never disagree with the manifest about what was published.
VERSION_PATTERN = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+\Z")
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
# Blender names split archives after the platform, not the wheel tag.
SPLIT_PLATFORMS = ("windows_x64", "linux_x64")

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


def write_github_output(path: Path, **values: object) -> None:
    """Append step outputs, refusing any value that could inject a row.

    A newline in a value would let the value declare further outputs of its
    own, so reject it rather than write it.
    """
    for key, value in values.items():
        text = str(value)
        if "\n" in text or "\r" in text:
            raise ValueError(f"GitHub output must be single-line: {key}")
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        for key, value in values.items():
            stream.write(f"{key}={value}\n")


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


def _read_exact(stream: object, size: int) -> bytes:
    result = bytearray()
    while len(result) < size:
        chunk = stream.recv(size - len(result))  # type: ignore[attr-defined]
        if not chunk:
            raise ValueError("truncated DNS-over-TLS response")
        result.extend(chunk)
    return bytes(result)


def _decode_dns_name(
    message: bytes,
    offset: int,
    known_label_offsets: set[int],
) -> tuple[tuple[bytes, ...], int, set[int]]:
    labels: list[bytes] = []
    observed_offsets: set[int] = set()
    cursor = offset
    next_offset: int | None = None
    expanded_size = 1
    while True:
        if cursor >= len(message):
            raise ValueError("truncated DNS name")
        length = message[cursor]
        encoding = length & 0xC0
        if encoding == 0xC0:
            if cursor + 2 > len(message):
                raise ValueError("truncated DNS name pointer")
            pointer = ((length & 0x3F) << 8) | message[cursor + 1]
            if pointer not in known_label_offsets:
                raise ValueError("invalid DNS name pointer")
            if next_offset is None:
                next_offset = cursor + 2
            cursor = pointer
            continue
        if encoding:
            raise ValueError("invalid DNS label encoding")
        observed_offsets.add(cursor)
        cursor += 1
        if length == 0:
            if next_offset is None:
                next_offset = cursor
            return tuple(labels), next_offset, observed_offsets
        if length > 63 or cursor + length > len(message):
            raise ValueError("invalid DNS name")
        expanded_size += length + 1
        if expanded_size > 255:
            raise ValueError("DNS name exceeds 255 bytes")
        labels.append(message[cursor : cursor + length].lower())
        cursor += length


def _parse_dns_a_response(
    message: bytes,
    transaction_id: int,
    expected_question: bytes,
) -> tuple[str, ...]:
    if len(message) < 12:
        raise ValueError("truncated DNS response")
    response_id, flags, questions, answers, _, _ = (
        struct.unpack("!HHHHHH", message[:12])
    )
    # Reject non-standard opcodes, truncation, and error responses.
    if (
        response_id != transaction_id
        or not flags & 0x8000
        or flags & 0x7A0F
        or questions != 1
    ):
        raise ValueError("invalid DNS response")
    offset = 12 + len(expected_question)
    if message[12:offset] != expected_question:
        raise ValueError("DNS response question mismatch")
    question_name, question_end, known_label_offsets = _decode_dns_name(
        message,
        12,
        set(),
    )
    if (
        question_end + 4 != offset
        or message[question_end:offset] != struct.pack("!HH", 1, 1)
    ):
        raise ValueError("invalid DNS response question")
    addresses: list[str] = []
    for _ in range(answers):
        owner, offset, owner_offsets = _decode_dns_name(
            message,
            offset,
            known_label_offsets,
        )
        if offset + 10 > len(message):
            raise ValueError("truncated DNS record")
        record_type, record_class, _, length = struct.unpack(
            "!HHIH",
            message[offset : offset + 10],
        )
        offset += 10
        data = message[offset : offset + length]
        if len(data) != length:
            raise ValueError("truncated DNS record data")
        offset += length
        if record_type == 1 and record_class == 1 and length == 4:
            if owner != question_name:
                raise ValueError("DNS answer owner mismatch")
            address = str(ipaddress.IPv4Address(data))
            if address not in addresses:
                if len(addresses) >= MAX_RESOLVED_ADDRESSES:
                    raise ValueError("DNS address budget exceeded")
                addresses.append(address)
            known_label_offsets.update(owner_offsets)
    if not addresses:
        raise ValueError("Quad9 returned no IPv4 address")
    return tuple(addresses)


def quad9_addresses(hostname: str) -> tuple[str, ...]:
    """Resolve over DNS-over-TLS, independent of curl's resolver."""
    labels = hostname.encode("idna").split(b".")
    if any(not label or len(label) > 63 for label in labels):
        raise ValueError("invalid DNS hostname")
    transaction_id = secrets.randbits(16)
    question = (
        b"".join(bytes((len(label),)) + label for label in labels)
        + b"\0"
        + struct.pack("!HH", 1, 1)
    )
    message = (
        struct.pack("!HHHHHH", transaction_id, 0x0100, 1, 0, 0, 0)
        + question
    )
    context = ssl.create_default_context()
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    with socket.create_connection(
        (QUAD9_DOT_HOST, QUAD9_DOT_PORT),
        timeout=CONNECT_TIMEOUT_SECONDS,
    ) as raw:
        with context.wrap_socket(raw, server_hostname=QUAD9_DOT_HOST) as tls:
            tls.sendall(struct.pack("!H", len(message)) + message)
            response_size = struct.unpack("!H", _read_exact(tls, 2))[0]
            response = _read_exact(tls, response_size)
    return _parse_dns_a_response(response, transaction_id, question)


def download(
    url: str,
    output: Path,
    doh_url: str | None = None,
    resolved_addresses: tuple[str, ...] | None = None,
) -> None:
    if urlparse(url).scheme != "https":
        raise ValueError("HTTPS is required")
    if doh_url and resolved_addresses is not None:
        raise ValueError("choose DNS-over-HTTPS or a resolved address")
    command = [
        "curl",
        "--proto", "=https",
        "--tlsv1.2",
        "--fail",
        "--silent",
        "--show-error",
        # Deliberately no --location. download.blender.org does not redirect,
        # and following one would allow an HTTPS to HTTP downgrade, since
        # curl governs redirect protocols separately from --proto.
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
    if resolved_addresses is not None:
        hostname = urlparse(url).hostname
        if (
            not resolved_addresses
            or len(resolved_addresses) > MAX_RESOLVED_ADDRESSES
            or hostname is None
        ):
            raise ValueError("resolved addresses require a hostname")
        addresses = ",".join(
            str(ipaddress.IPv4Address(address))
            for address in resolved_addresses
        )
        command += ["--resolve", f"{hostname}:443:{addresses}"]
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

    checksum_host = urlparse(CHECKSUM_URL).hostname
    paths = [output_dir / f"checksums-{index}.txt" for index in range(3)]
    download(CHECKSUM_URL, paths[0])
    download(CHECKSUM_URL, paths[1], doh_url=CLOUDFLARE_DOH_URL)
    download(
        CHECKSUM_URL,
        paths[2],
        resolved_addresses=quad9_addresses(checksum_host),
    )
    payloads = [path.read_bytes() for path in paths]
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
        write_github_output(github_output, blender=blender, python=python)
    print(f"blender: {blender}")
    print(f"python:  {python}")
    return blender, python


def release_identity(version: str, manifest: Path) -> tuple[str, list[str]]:
    """Return the tag and the exact archive names a release must publish.

    The manifest is the authority for both the version and the extension id,
    so a release cannot be cut for a version the package does not declare.
    """
    if not VERSION_PATTERN.fullmatch(version):
        raise ValueError(f"release version must use X.Y.Z: {version!r}")
    parsed = tomllib.loads(manifest.read_text(encoding="utf-8"))
    if parsed["version"] != version:
        raise ValueError(
            f"manifest version {parsed['version']!r} does not match "
            f"requested {version!r}"
        )
    extension_id = parsed["id"]
    names = [f"{extension_id}-{version}.zip"]
    names += [
        f"{extension_id}-{version}-{platform}.zip"
        for platform in SPLIT_PLATFORMS
    ]
    return f"v{version}", names


def write_sha256s(paths: list[Path], output: Path) -> dict[str, str]:
    digests = {path.name: sha256_file(path) for path in paths}
    output.write_text(
        "".join(f"{digest}  {name}\n" for name, digest in digests.items()),
        encoding="utf-8",
        newline="\n",
    )
    return digests


def require_file_sha256(path: Path, expected_sha256: str) -> None:
    if not SHA256_PATTERN.fullmatch(expected_sha256):
        raise ValueError(f"malformed expected SHA-256: {expected_sha256!r}")
    actual = sha256_file(path)
    if actual != expected_sha256:
        raise ValueError(
            f"{path.name} SHA-256 mismatch: expected {expected_sha256}, "
            f"got {actual}"
        )


def prepare_release(
    version: str,
    manifest: Path,
    release_dir: Path,
    checksum_output: Path,
    github_output: Path | None,
) -> dict[str, str]:
    tag, names = release_identity(version, manifest)
    paths = []
    for name in names:
        path = release_dir / name
        if not path.is_file():
            raise ValueError(f"release archive is missing: {name}")
        paths.append(path)
    # Anything else in the directory would be published unverified.
    unexpected = sorted(
        item.name
        for item in release_dir.iterdir()
        if item.is_file()
        and item.name not in names
        and item != checksum_output
    )
    if unexpected:
        raise ValueError(f"unexpected files in release directory: {unexpected}")

    digests = write_sha256s(paths, checksum_output)
    if github_output is not None:
        write_github_output(github_output, tag=tag, archives=" ".join(names))
    print(f"tag: {tag}")
    for name, digest in digests.items():
        print(f"  {digest}  {name}")
    return digests


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare-blender")
    prepare.add_argument("--platform", choices=tuple(PLATFORMS), required=True)
    prepare.add_argument("--output-dir", type=Path, required=True)
    prepare.add_argument("--github-output", type=Path)

    check = subparsers.add_parser("check-release")
    check.add_argument("--version", required=True)
    check.add_argument("--manifest", type=Path, required=True)

    release = subparsers.add_parser("prepare-release")
    release.add_argument("--version", required=True)
    release.add_argument("--manifest", type=Path, required=True)
    release.add_argument("--release-dir", type=Path, required=True)
    release.add_argument("--checksum-output", type=Path, required=True)
    release.add_argument("--github-output", type=Path)

    verify = subparsers.add_parser("verify-file")
    verify.add_argument("--file", type=Path, required=True)
    verify.add_argument("--expected-sha256", required=True)

    arguments = parser.parse_args(argv)

    if arguments.command == "prepare-blender":
        prepare_blender(
            arguments.platform,
            arguments.output_dir,
            arguments.github_output,
        )
    elif arguments.command == "check-release":
        tag, names = release_identity(arguments.version, arguments.manifest)
        print(f"tag: {tag}")
        for name in names:
            print(f"  {name}")
    elif arguments.command == "prepare-release":
        prepare_release(
            arguments.version,
            arguments.manifest,
            arguments.release_dir,
            arguments.checksum_output,
            arguments.github_output,
        )
    elif arguments.command == "verify-file":
        require_file_sha256(arguments.file, arguments.expected_sha256)
        print(f"verified: {arguments.file.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
