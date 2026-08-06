"""Compatibility diagnostics for Material Combiner's Pillow dependency."""

import json
from typing import Set

import bpy

from .. import globs


class InstallPIL(bpy.types.Operator):
    """Preserved non-installing diagnostics operator used by CATS."""

    bl_idname = "smc.get_pillow"
    bl_label = "Copy Dependency Diagnostics"
    bl_description = (
        "Copy Material Combiner dependency diagnostics. "
        "This operator never installs or modifies Python packages."
    )

    def execute(self, context: bpy.types.Context) -> Set[str]:
        status = globs.refresh_dependency_status()
        context.window_manager.clipboard = json.dumps(
            status.as_dict(include_paths=False),
            indent=2,
        )
        self.report({"INFO"}, "Dependency diagnostics copied")
        return {"FINISHED"} if status.healthy else {"CANCELLED"}
