"""Main combiner operator for the Material Combiner addon.

This module coordinates selection validation, atlas preparation, image output,
UV updates, and material reassignment.
"""

import os
from typing import Set

import bpy
from bpy.props import BoolProperty, StringProperty

from ... import globs
from ...utils.packers import pack
from .combiner_ops import (
    align_uvs,
    assign_comb_mats,
    calculate_adjusted_size,
    clear_empty_mats,
    clear_mats,
    ensure_pillow_available,
    get_atlas,
    get_atlas_size,
    get_comb_mats,
    get_data,
    get_duplicates,
    get_mats_uv,
    get_size,
    get_structure,
    set_ob_mode,
    validate_ob_data,
)

MAX_ATLAS_SIZE = 20000


class _PreflightSnapshot:
    """State touched by legacy preparation before atlas creation begins."""

    _MODE_MAP = {
        "EDIT_MESH": "EDIT",
        "EDIT_CURVE": "EDIT",
        "EDIT_SURFACE": "EDIT",
        "EDIT_TEXT": "EDIT",
        "EDIT_ARMATURE": "EDIT",
        "EDIT_METABALL": "EDIT",
        "EDIT_LATTICE": "EDIT",
        "PAINT_WEIGHT": "WEIGHT_PAINT",
        "PAINT_VERTEX": "VERTEX_PAINT",
        "PAINT_TEXTURE": "TEXTURE_PAINT",
    }

    def __init__(self, context: bpy.types.Context) -> None:
        scene = context.scene
        self.save_path = scene.smc_save_path
        self.size = scene.smc_size
        self.gaps = scene.smc_gaps
        self.list_id = scene.smc_list_id
        self.ob_data_id = scene.smc_ob_data_id
        self.list_entries = [
            (
                item.ob,
                item.ob_id,
                item.mat,
                item.layer,
                item.used,
                item.type,
            )
            for item in scene.smc_ob_data
        ]
        self.active = context.view_layer.objects.active
        self.mode = context.mode
        self.selection = {
            obj: obj.select_get() for obj in context.view_layer.objects
        }
        self.roots = {mat: mat.root_mat for mat in bpy.data.materials}
        self.meshes = []
        for obj in scene.objects:
            if obj.type != "MESH":
                continue
            uv_layer = obj.data.uv_layers.active
            uv_values = (
                [(loop.uv.x, loop.uv.y) for loop in uv_layer.data]
                if uv_layer
                else None
            )
            self.meshes.append(
                (
                    obj,
                    list(obj.data.materials),
                    [poly.material_index for poly in obj.data.polygons],
                    uv_values,
                )
            )

    def restore(self, context: bpy.types.Context) -> None:
        """Restore state after a cancelled or failed preflight."""
        scene = context.scene
        scene.smc_save_path = self.save_path
        scene.smc_size = self.size
        scene.smc_gaps = self.gaps
        scene.smc_list_id = self.list_id
        scene.smc_ob_data_id = self.ob_data_id

        for material, root in self.roots.items():
            if material.root_mat != root:
                material.root_mat = root

        for obj, materials, indices, uv_values in self.meshes:
            if list(obj.data.materials) != materials:
                obj.data.materials.clear()
                for material in materials:
                    obj.data.materials.append(material)
            for polygon, material_index in zip(obj.data.polygons, indices):
                if polygon.material_index != material_index:
                    polygon.material_index = material_index
            if uv_values is not None and obj.data.uv_layers.active:
                for loop, (x, y) in zip(
                    obj.data.uv_layers.active.data, uv_values
                ):
                    if loop.uv.x != x or loop.uv.y != y:
                        loop.uv = (x, y)

        scene.smc_ob_data.clear()
        for values in self.list_entries:
            entry = scene.smc_ob_data.add()
            entry.ob = values[0]
            entry.ob_id = values[1]
            entry.mat = values[2]
            entry.layer = values[3]
            entry.used = values[4]
            entry.type = values[5]

        for obj in context.view_layer.objects:
            selected = self.selection.get(obj, False)
            if obj.select_get() != selected:
                obj.select_set(selected)
        context.view_layer.objects.active = self.active
        target_mode = self._MODE_MAP.get(self.mode, self.mode)
        if self.active and context.mode != self.mode:
            bpy.ops.object.mode_set(mode=target_mode)


class Combiner(bpy.types.Operator):
    """Combine selected materials into a texture atlas."""

    bl_idname = "smc.combiner"
    bl_label = "Create Atlas"
    bl_description = "Combine materials"
    bl_options = {"UNDO", "INTERNAL"}

    directory = StringProperty(
        description="Directory to save the atlas",
        maxlen=1024,
        default="",
        subtype="DIR_PATH",
        options={"HIDDEN"},
    )
    filter_glob = StringProperty(default="", options={"HIDDEN"})
    cats = BoolProperty(
        description="Enable special cats workflow mode",
        default=False,
    )
    data = None
    mats_uv = None
    structure = None

    def execute(self, context: bpy.types.Context) -> Set[str]:
        """Run immutable checks, prepare inputs, and create the atlas."""
        scene = context.scene
        self.data = None
        self.mats_uv = None
        self.structure = None

        dependency = globs.refresh_dependency_status(
            cats_invocation=self.cats
        )
        if not dependency.healthy:
            return self._return_with_message(
                "WARNING",
                f"Pillow dependency unavailable: {dependency.summary}",
            )
        ensure_pillow_available()

        directory = bpy.path.abspath(self.directory).strip()
        if not directory:
            return self._return_with_message(
                "WARNING", "No directory selected"
            )
        if not os.path.isdir(directory):
            return self._return_with_message(
                "WARNING", "The selected output directory does not exist"
            )

        snapshot = _PreflightSnapshot(context)
        try:
            validation_message = self._prepare(context)
        except Exception:
            snapshot.restore(context)
            raise
        if validation_message:
            snapshot.restore(context)
            return self._return_with_message("WARNING", validation_message)

        original_size = scene.smc_size
        original_gaps = scene.smc_gaps
        if self.cats:
            scene.smc_size = "PO2"
            scene.smc_gaps = 0

        try:
            try:
                self.structure = pack(
                    get_size(scene, self.structure),
                    scene.smc_packer_type,
                )
                size = get_atlas_size(self.structure)
                atlas_size = calculate_adjusted_size(scene, size)
            except Exception:
                snapshot.restore(context)
                raise

            if max(atlas_size, default=0) > MAX_ATLAS_SIZE:
                snapshot.restore(context)
                return self._return_with_message(
                    "WARNING",
                    "The output image size of {}x{}px is too large".format(
                        *atlas_size
                    ),
                )

            scene.smc_save_path = directory
            atlas = get_atlas(scene, self.structure, atlas_size)
            align_uvs(scene, self.structure, atlas.size, size)
            comb_mats = get_comb_mats(scene, atlas, self.mats_uv)
            assign_comb_mats(scene, self.data, comb_mats)
            clear_mats(scene, self.mats_uv)
            bpy.ops.smc.refresh_ob_data()
            self.report({"INFO"}, "Materials were combined")
            return {"FINISHED"}
        finally:
            if self.cats:
                scene.smc_size = original_size
                scene.smc_gaps = original_gaps

    def invoke(
        self,
        context: bpy.types.Context,
        event: bpy.types.Event,
    ) -> Set[str]:
        """Validate without atlas mutations, then open directory selection."""
        dependency = globs.refresh_dependency_status(
            cats_invocation=self.cats
        )
        if not dependency.healthy:
            return self._return_with_message(
                "WARNING",
                f"Pillow dependency unavailable: {dependency.summary}",
            )

        validation_message = self._validate_selection(context)
        if validation_message:
            return self._return_with_message(
                "WARNING", validation_message
            )

        if event is not None:
            context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def _validate_selection(
        self,
        context: bpy.types.Context,
    ) -> str | None:
        """Validate selection without changing UVs, slots, roots, or mode."""
        scene = context.scene
        bpy.ops.smc.refresh_ob_data()
        if validate_ob_data(scene.smc_ob_data):
            return "No valid objects selected"

        data = get_data(scene.smc_ob_data)
        if not data:
            return "No materials selected"

        materials = {
            material
            for object_materials in data.values()
            for material in object_materials
        }
        if len(materials) == 1:
            return "Only one unique material selected - nothing to combine"
        return None

    def _prepare(self, context: bpy.types.Context) -> str | None:
        """Prepare inputs after dependency and output-path preflight."""
        scene = context.scene
        bpy.ops.smc.refresh_ob_data()
        if validate_ob_data(scene.smc_ob_data):
            return "No valid objects selected"

        set_ob_mode(context.view_layer, scene.smc_ob_data)
        self.data = get_data(scene.smc_ob_data)
        if not self.data:
            return "No materials selected"

        self.mats_uv = get_mats_uv(scene, self.data)
        clear_empty_mats(scene, self.data, self.mats_uv)
        get_duplicates(self.mats_uv)
        self.structure = get_structure(scene, self.data, self.mats_uv)

        total_unique_mats = len(self.structure)
        has_duplicates = any(
            len(item["dup"]) > 0 for item in self.structure.values()
        )
        if total_unique_mats == 0:
            return "No materials selected"
        if total_unique_mats == 1 and not has_duplicates:
            return "Only one unique material selected - nothing to combine"
        return None

    def draw(self, context: bpy.types.Context) -> None:
        """Draw no extra controls in Blender's directory selector."""

    def _return_with_message(
        self,
        message_type: str,
        message: str,
    ) -> Set[str]:
        """Report a message with accurate cancellation semantics."""
        self.report({message_type}, message)
        if message_type in {"ERROR", "WARNING"}:
            return {"CANCELLED"}
        return {"FINISHED"}
