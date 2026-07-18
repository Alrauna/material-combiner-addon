"""UI panel explaining how extension updates are managed.

The addon does not make network requests or install its own updates at runtime.
"""

import bpy

from .. import globs


class UpdatePanel(bpy.types.Panel):
    """Panel describing Blender-managed extension updates.

    This class implements a Blender panel that provides information about
    checking, configuring, and installing updates for the Material Combiner addon,
    using the addon updater API.
    """

    bl_label = "Updates"
    bl_idname = "SMC_PT_Update_Panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "MatCombiner"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context: bpy.types.Context) -> None:
        """Draw the panel layout with updater UI elements.

        Args:
            context: The current Blender context.
        """
        layout = self.layout
        layout.label(text='Updates are managed by Blender Extensions.')
        layout.label(text='Use Preferences > Extensions to update or reinstall.')
