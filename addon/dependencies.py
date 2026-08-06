from __future__ import annotations

import hashlib
import importlib
import json
import os
import platform
import sys
from pathlib import Path

import bpy

from .dependency_status import (
    DependencyFacts,
    DependencyStatus,
    classify_dependency,
    message_for,
)


EXPECTED_VERSION = "12.3.0"
EXPECTED_ABI = "cpython-313"
SUPPORTED_PLATFORMS = {
    "win32": "windows-x64",
    "linux": "linux-x64",
}
SUPPORTED_ARCHITECTURES = {"amd64", "x86_64"}
PACKAGE_ROOT = Path(__file__).resolve().parent
LOCK_PATH = PACKAGE_ROOT / "dependencies.lock.json"
_restart_required = False
_stale_native_loaded = False


def _filesystem_path(path: Path) -> Path:
    """Use Windows extended-length syntax for dependency integrity I/O."""
    if os.name != "nt":
        return path
    value = str(path.absolute())
    if value.startswith("\\\\?\\"):
        return path
    if value.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + value[2:])
    return Path("\\\\?\\" + value)


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _plain_path(path: Path) -> Path:
    """Drop Windows extended-length syntax so paths compare consistently."""
    value = str(path)
    if value.startswith("\\\\?\\UNC\\"):
        return Path("\\\\" + value[8:])
    if value.startswith("\\\\?\\"):
        return Path(value[4:])
    return path


def _inside(path: Path, root: Path) -> bool:
    path = _plain_path(path.resolve())
    root = _plain_path(root.resolve())
    return path == root or root in path.parents


def _approved_developer_root() -> Path | None:
    value = os.environ.get("SMC_APPROVED_DEPENDENCY_PATH")
    return Path(value).resolve() if value else None


def _extension_root() -> Path:
    return PACKAGE_ROOT.parents[1]


def _current_platform() -> str | None:
    """Return this machine's package platform, or None if unsupported."""
    platform_name = SUPPORTED_PLATFORMS.get(sys.platform)
    if platform_name is None:
        return None
    if platform.machine().casefold() not in SUPPORTED_ARCHITECTURES:
        return None
    return platform_name


def _load_lock() -> tuple[dict[str, object] | None, str | None]:
    """Return the lock entry for this platform, if the package ships one."""
    try:
        lock = json.loads(
            _filesystem_path(LOCK_PATH).read_text(encoding="utf-8")
        )
        dependencies = lock["dependencies"]
    except Exception as exc:
        return None, repr(exc)
    current = _current_platform()
    for dependency in dependencies:
        if dependency["platform"] == current:
            return dependency, None
    return None, f"No bundled dependency for platform: {current}"


def _wheel_integrity(
    dependency: dict[str, object] | None,
) -> tuple[bool, bool, str | None]:
    if dependency is None:
        return False, False, "Dependency lock is unavailable."
    wheel = PACKAGE_ROOT / str(dependency["wheel"])
    filesystem_wheel = _filesystem_path(wheel)
    if not filesystem_wheel.is_file():
        return False, False, f"Missing wheel: {wheel}"
    try:
        valid = (
            filesystem_wheel.stat().st_size == int(dependency["size"])
            and _sha256(filesystem_wheel) == dependency["sha256"]
        )
    except OSError as exc:
        return True, False, repr(exc)
    return True, valid, None if valid else "Wheel hash or size mismatch."


def _runtime_imports() -> dict[str, object]:
    result: dict[str, object] = {
        "present": False,
        "native_imported": False,
        "python_version": None,
        "native_version": None,
        "paths": {},
        "exception": None,
    }
    try:
        pil = importlib.import_module("PIL")
        image = importlib.import_module("PIL.Image")
        result["present"] = True
        result["python_version"] = getattr(pil, "__version__", None)
        result["paths"] = {
            "PIL": str(Path(pil.__file__).resolve()),
            "PIL.Image": str(Path(image.__file__).resolve()),
        }
        imaging = importlib.import_module("PIL._imaging")
        result["native_imported"] = True
        result["native_version"] = getattr(
            imaging,
            "PILLOW_VERSION",
            None,
        ) or getattr(imaging, "__version__", None)
        result["paths"]["PIL._imaging"] = str(
            Path(imaging.__file__).resolve()
        )
    except Exception as exc:
        result["exception"] = repr(exc)
    return result


def get_dependency_status(cats_invocation: bool = False) -> DependencyStatus:
    current_platform = _current_platform()
    dependency, lock_error = _load_lock()
    wheel_present, files_complete, wheel_error = _wheel_integrity(dependency)
    runtime = _runtime_imports()
    paths = runtime["paths"]
    developer_root = _approved_developer_root()
    path_values = [Path(value) for value in paths.values()]
    managed_root = _extension_root()
    path_trusted = bool(path_values) and all(
        _inside(path, managed_root) for path in path_values
    )
    developer_approved = bool(path_values) and developer_root is not None and all(
        _inside(path, developer_root) for path in path_values
    )
    source_layout_supported = __package__.startswith("bl_ext.")
    facts = DependencyFacts(
        pillow_present=bool(runtime["present"]),
        wheel_present=wheel_present,
        platform_supported=current_platform is not None,
        abi_supported=sys.implementation.cache_tag == EXPECTED_ABI,
        native_imported=bool(runtime["native_imported"]),
        versions_match=(
            runtime["python_version"] == EXPECTED_VERSION
            and runtime["native_version"] == EXPECTED_VERSION
        ),
        files_complete=files_complete,
        dependency_path_trusted=path_trusted or developer_approved,
        source_layout_supported=source_layout_supported,
        developer_path_approved=developer_approved,
        cats_invocation=cats_invocation,
        restart_required=_restart_required,
        stale_native_loaded=_stale_native_loaded,
    )
    category, cause = classify_dependency(facts)
    summary, recovery = message_for(category)
    exception_parts = [
        value
        for value in (
            lock_error,
            wheel_error,
            runtime["exception"],
        )
        if value
    ]
    return DependencyStatus(
        category=category,
        healthy=category in {"healthy", "approved_developer_path"},
        summary=summary,
        recovery=recovery,
        expected_version=EXPECTED_VERSION,
        detected_version=runtime["python_version"],
        native_version=runtime["native_version"],
        blender_version=bpy.app.version_string,
        python_version=platform.python_version(),
        python_abi=sys.implementation.cache_tag,
        operating_system=platform.system(),
        architecture=platform.machine(),
        expected_platform=(
            current_platform or "/".join(sorted(SUPPORTED_PLATFORMS.values()))
        ),
        paths=paths,
        exception="; ".join(exception_parts) or None,
        cause=cause,
        restart_required=category in {
            "native_restart_required",
            "stale_native_after_update",
        },
    )


def mark_native_restart_required(stale_after_update: bool = False) -> None:
    global _restart_required, _stale_native_loaded
    _restart_required = not stale_after_update
    _stale_native_loaded = stale_after_update
