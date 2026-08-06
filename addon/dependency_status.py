from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping


HEALTHY = "healthy"
PILLOW_ABSENT = "pillow_absent"
WHEEL_MISSING = "wheel_missing"
WRONG_PLATFORM = "wrong_platform"
ABI_MISMATCH = "abi_mismatch"
NATIVE_IMPORT_FAILED = "native_import_failed"
COMPONENT_VERSION_MISMATCH = "component_version_mismatch"
FILES_CORRUPT_OR_INCOMPLETE = "files_corrupt_or_incomplete"
DEPENDENCY_CONFLICT = "dependency_conflict"
UNSUPPORTED_SOURCE_LAYOUT = "unsupported_source_layout"
APPROVED_DEVELOPER_PATH = "approved_developer_path"
CATS_DEPENDENCY_UNAVAILABLE = "cats_dependency_unavailable"
NATIVE_RESTART_REQUIRED = "native_restart_required"
STALE_NATIVE_AFTER_UPDATE = "stale_native_after_update"


@dataclass(frozen=True)
class DependencyFacts:
    pillow_present: bool = True
    wheel_present: bool = True
    platform_supported: bool = True
    abi_supported: bool = True
    native_imported: bool = True
    versions_match: bool = True
    files_complete: bool = True
    dependency_path_trusted: bool = True
    source_layout_supported: bool = True
    developer_path_approved: bool = False
    cats_invocation: bool = False
    restart_required: bool = False
    stale_native_loaded: bool = False


@dataclass(frozen=True)
class DependencyStatus:
    category: str
    healthy: bool
    summary: str
    recovery: str
    expected_version: str
    detected_version: str | None
    native_version: str | None
    blender_version: str
    python_version: str
    python_abi: str
    operating_system: str
    architecture: str
    expected_platform: str
    paths: Mapping[str, str]
    exception: str | None = None
    cause: str | None = None
    restart_required: bool = False

    def as_dict(self, include_paths: bool = False) -> dict[str, object]:
        data = asdict(self)
        if not include_paths:
            data["paths"] = {
                name: value.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
                for name, value in self.paths.items()
            }
        return data


_MESSAGES = {
    HEALTHY: (
        "Pillow is available and usable.",
        "No recovery action is required.",
    ),
    PILLOW_ABSENT: (
        "Pillow is not available in Blender's extension environment.",
        "Reinstall the complete Material Combiner package for this platform.",
    ),
    WHEEL_MISSING: (
        "The Material Combiner package does not contain its required wheel.",
        "Reinstall the complete official package instead of a source folder.",
    ),
    WRONG_PLATFORM: (
        "This Material Combiner package targets a different platform.",
        "Install the Material Combiner package built for this operating system and architecture.",
    ),
    ABI_MISMATCH: (
        "The bundled Pillow wheel does not match Blender's Python ABI.",
        "Install the package built for this Blender and Python version.",
    ),
    NATIVE_IMPORT_FAILED: (
        "Pillow's Python modules loaded, but its native imaging module failed.",
        "Reinstall the package. Restart Blender if the native module was recently updated.",
    ),
    COMPONENT_VERSION_MISMATCH: (
        "Pillow's Python and native components report different versions.",
        "Reinstall the complete Material Combiner package and restart Blender.",
    ),
    FILES_CORRUPT_OR_INCOMPLETE: (
        "The bundled Pillow files are incomplete or do not match the release lock.",
        "Reinstall the complete Material Combiner package from a trusted copy.",
    ),
    DEPENDENCY_CONFLICT: (
        "Pillow was loaded from outside Material Combiner's managed extension environment.",
        "Disable the conflicting extension, then reinstall or re-enable Material Combiner.",
    ),
    UNSUPPORTED_SOURCE_LAYOUT: (
        "Material Combiner is running from an unsupported source-directory layout.",
        "Remove the source copy and install the packaged extension from disk.",
    ),
    APPROVED_DEVELOPER_PATH: (
        "Pillow is available from an approved isolated developer path.",
        "Use the packaged extension before release or ordinary user testing.",
    ),
    CATS_DEPENDENCY_UNAVAILABLE: (
        "CATS invoked Material Combiner while its packaged dependency is unavailable.",
        "Repair the Material Combiner package, then retry the CATS atlas operation.",
    ),
    NATIVE_RESTART_REQUIRED: (
        "A loaded native Pillow module cannot be replaced or removed in this process.",
        "Restart Blender after completing the package change.",
    ),
    STALE_NATIVE_AFTER_UPDATE: (
        "The package was updated, but the previous native Pillow module is still loaded.",
        "Restart Blender before using Material Combiner.",
    ),
}


def classify_dependency(facts: DependencyFacts) -> tuple[str, str | None]:
    if facts.stale_native_loaded:
        return STALE_NATIVE_AFTER_UPDATE, None
    if facts.restart_required:
        return NATIVE_RESTART_REQUIRED, None

    base_facts = DependencyFacts(
        **{
            **asdict(facts),
            "cats_invocation": False,
        }
    )
    base_category = _classify_base(base_facts)
    if facts.cats_invocation and base_category not in {
        HEALTHY,
        APPROVED_DEVELOPER_PATH,
    }:
        return CATS_DEPENDENCY_UNAVAILABLE, base_category
    return base_category, None


def _classify_base(facts: DependencyFacts) -> str:
    if not facts.wheel_present:
        return WHEEL_MISSING
    if not facts.platform_supported:
        return WRONG_PLATFORM
    if not facts.abi_supported:
        return ABI_MISMATCH
    if not facts.pillow_present:
        return PILLOW_ABSENT
    if not facts.native_imported:
        return NATIVE_IMPORT_FAILED
    if not facts.versions_match:
        return COMPONENT_VERSION_MISMATCH
    if not facts.files_complete:
        return FILES_CORRUPT_OR_INCOMPLETE
    if not facts.dependency_path_trusted:
        return DEPENDENCY_CONFLICT
    if not facts.source_layout_supported:
        return UNSUPPORTED_SOURCE_LAYOUT
    if facts.developer_path_approved:
        return APPROVED_DEVELOPER_PATH
    return HEALTHY


def message_for(category: str) -> tuple[str, str]:
    return _MESSAGES[category]
