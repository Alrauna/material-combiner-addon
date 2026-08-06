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
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


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


def verify_dependency(dependency: dict) -> list[str]:
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
        if f"Wheel-Version: {SUPPORTED_WHEEL_VERSION}" not in wheel_metadata:
            errors.append("unsupported-wheel-version")
        # A compressed tag set such as "manylinux_2_27_x86_64.manylinux_2_28_
        # x86_64" is written to WHEEL as one expanded Tag row per platform.
        for platform_tag in dependency["platform_tag"].split("."):
            expected_tag = (
                f"{dependency['python_tag']}-"
                f"{dependency['abi_tag']}-{platform_tag}"
            )
            if f"Tag: {expected_tag}" not in wheel_metadata:
                errors.append(f"wheel-tag-mismatch:{expected_tag}")

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
        if dependency["native_module"] not in archive.namelist():
            errors.append("native-module-missing")

    return errors


def main() -> int:
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    dependencies = lock["dependencies"]
    wheels = []
    for dependency in dependencies:
        errors = verify_dependency(dependency)
        wheels.append(
            {
                "platform": dependency["platform"],
                "wheel": dependency["wheel"],
                "sha256": sha256_file(ROOT / dependency["wheel"]),
                "errors": errors,
            }
        )

    platforms = [entry["platform"] for entry in wheels]
    report = {
        "valid": (
            bool(wheels)
            and not any(entry["errors"] for entry in wheels)
            and len(set(platforms)) == len(platforms)
        ),
        "wheels": wheels,
    }
    print(json.dumps(report, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
