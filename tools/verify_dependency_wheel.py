from __future__ import annotations

import base64
import csv
import hashlib
import json
import re
import stat
import sys
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1] / "addon"
LOCK_PATH = ROOT / "dependencies.lock.json"
SUPPORTED_WHEEL_VERSION = "1.0"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def record_digest(value: str) -> str:
    algorithm, encoded = value.split("=", 1)
    if algorithm != "sha256":
        raise ValueError(f"Unsupported RECORD hash: {algorithm}")
    return base64.urlsafe_b64decode(
        encoded + "=" * (-len(encoded) % 4)
    ).hex()


def validate_member(name: str) -> None:
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    if (
        not name
        or "\x00" in name
        or "\\" in name
        or name.startswith(("/", "\\", "//", "\\\\"))
        or re.match(r"^[A-Za-z]:", name)
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
        or any(":" in part for part in path.parts)
    ):
        raise ValueError(f"Unsafe wheel member: {name}")


def main() -> int:
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    dependency = lock["dependencies"][0]
    wheel = ROOT / dependency["wheel"]
    errors: list[str] = []

    if wheel.stat().st_size != dependency["size"]:
        errors.append("wheel-size-mismatch")
    if sha256_file(wheel) != dependency["sha256"]:
        errors.append("wheel-sha256-mismatch")

    with zipfile.ZipFile(wheel) as archive:
        if archive.testzip() is not None:
            errors.append("wheel-crc-failure")
        names: set[str] = set()
        for info in archive.infolist():
            try:
                validate_member(info.filename)
            except ValueError as exc:
                errors.append(str(exc))
            key = info.filename.rstrip("/").casefold()
            if key in names:
                errors.append(f"duplicate-member:{info.filename}")
            names.add(key)
            if stat.S_ISLNK((info.external_attr >> 16) & 0xFFFF):
                errors.append(f"symlink:{info.filename}")

        wheel_file = next(
            name for name in archive.namelist()
            if name.endswith(".dist-info/WHEEL")
        )
        wheel_metadata = archive.read(wheel_file).decode("utf-8")
        expected_tag = (
            f"{dependency['python_tag']}-"
            f"{dependency['abi_tag']}-win_amd64"
        )
        if f"Wheel-Version: {SUPPORTED_WHEEL_VERSION}" not in wheel_metadata:
            errors.append("unsupported-wheel-version")
        if f"Tag: {expected_tag}" not in wheel_metadata:
            errors.append("wheel-tag-mismatch")

        record_file = next(
            name for name in archive.namelist()
            if name.endswith(".dist-info/RECORD")
        )
        record_rows = {
            row[0]: (row[1], row[2])
            for row in csv.reader(
                archive.read(record_file).decode("utf-8").splitlines()
            )
        }
        archived_files = {
            info.filename for info in archive.infolist() if not info.is_dir()
        }
        if archived_files != set(record_rows):
            errors.append("record-membership-mismatch")
        for name, (hash_value, size_value) in record_rows.items():
            if name == record_file:
                if hash_value or size_value:
                    errors.append("record-self-entry-not-empty")
                continue
            data = archive.read(name)
            if record_digest(hash_value) != sha256(data):
                errors.append(f"record-hash-mismatch:{name}")
            if int(size_value) != len(data):
                errors.append(f"record-size-mismatch:{name}")

        license_name = dependency["license_file"]
        if sha256(archive.read(license_name)) != dependency["license_sha256"]:
            errors.append("license-hash-mismatch")
        native_name = f"PIL/_imaging.{dependency['abi_tag']}-win_amd64.pyd"
        if native_name not in archive.namelist():
            errors.append("native-module-missing")

    report = {
        "valid": not errors,
        "wheel": dependency["wheel"],
        "sha256": sha256_file(wheel),
        "errors": errors,
    }
    print(json.dumps(report, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
