"""UI panel for the main Material Combiner interface.

This module provides the primary UI panel for the Material Combiner addon,
displaying the material list, atlas property controls, and action buttons.
It also handles the Pillow installation interface when the library is not
available.
"""

import bpy

from .. import globs
from ..icons import get_icon_id

class MaterialCombinerPanel(bpy.types.Panel):
    """Main panel for the Material Combiner addon.

    This class implements the primary UI panel for the Material Combiner addon,
    providing access to the material list, atlas properties settings, and
    action buttons. It also handles different states based on Pillow
    installation status.
    """
    bl_label = 'Main Menu'
    bl_idname = 'SMC_PT_Main_Panel'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'MatCombiner'

    def draw(self, context: bpy.types.Context) -> None:
        """Draw the panel interface based on Pillow installation status.

        Renders different panel states depending on whether Pillow is installed,
        installation is in progress, or installation needs to be initiated.

        Args:
            context: The current Blender context.
        """
        layout = self.layout

        status = globs.refresh_dependency_status()
        if status.healthy:
            self._render_main_interface(context, layout)
        else:
            self.draw_pillow_installer(context, layout)

    def _render_main_interface(self, context: bpy.types.Context, layout: bpy.types.UILayout) -> None:
        """Render the main interface when Pillow is installed.

        Creates the complete UI with material list, properties section,
        and action controls for atlas generation.

        Args:
            context: The current Blender context.
            layout: The layout to draw into.
        """
        self._create_materials_list(context, layout)
        self._create_properties_section(context.scene, layout)
        self._create_action_controls(layout)

    @staticmethod
    def _create_materials_list(context: bpy.types.Context, layout: bpy.types.UILayout) -> None:
        """Create the material list section with filtering options.

        Displays a list of available materials with related controls
        for selecting, filtering, and refreshing the list.

        Args:
            context: The current Blender context.
            layout: The layout to draw into.
        """
        scene = context.scene
        list_column = layout.column(align=True)

        list_column.label(text='Materials to Combine:')

        list_box = list_column.box()
        list_box.template_list(
            'SMC_UL_Combine_List',
            'combine_list',
            scene,
            'smc_ob_data',
            scene,
            'smc_ob_data_id',
            rows=12
        )

        refresh_row = list_column.row(align=True)
        refresh_row.scale_y = 1.2
        action_text = 'Update Material List' if scene.smc_ob_data else 'Generate Material List'
        refresh_row.operator('smc.refresh_ob_data', text=action_text, icon_value=get_icon_id('null'))

    def _create_properties_section(self, scene: bpy.types.Scene, layout: bpy.types.UILayout) -> None:
        """Create an atlas properties section with configuration options.

        Creates UI elements for configuring atlas size, quality settings,
        and spacing options.

        Args:
            scene: The current scene containing property values.
            layout: The layout to draw into.
        """
        column = layout.column()
        column.label(text='Atlas Properties:')

        box = column.box()
        self._add_size_properties(box, scene)
        self._add_quality_properties(box, scene)
        self._add_gap_settings(box, scene)

    @staticmethod
    def _add_size_properties(layout: bpy.types.UILayout, scene: bpy.types.Scene) -> None:
        """Add atlas size property controls to the layout.

        Displays atlas size selection and optional custom size inputs
        when custom size options are selected.

        Args:
            layout: The layout to draw into.
            scene: The current scene containing property values.
        """
        layout.prop(scene, 'smc_size', text='Atlas Size')
        layout.prop(scene, 'smc_packer_type', text='Packing Algorithm')

        if scene.smc_size in {'CUST', 'STRICTCUST'}:
            size_col = layout.column(align=True)
            size_col.scale_y = 1.2
            size_col.prop(scene, 'smc_size_width', text='Width')
            size_col.prop(scene, 'smc_size_height', text='Height')

    @staticmethod
    def _add_quality_properties(layout: bpy.types.UILayout, scene: bpy.types.Scene) -> None:
        """Add texture quality setting controls to the layout.

        Displays options for cropping and pixel art mode that affect
        the quality and appearance of the generated atlas.

        Args:
            layout: The layout to draw into.
            scene: The current scene containing property values.
        """
        quality_col = layout.column(align=True)
        quality_col.prop(scene, 'smc_crop', text='Enable Cropping')
        quality_col.prop(scene, 'smc_pixel_art', text='Pixel Art Mode')

    def _add_gap_settings(self, layout: bpy.types.UILayout, scene: bpy.types.Scene) -> None:
        """Add texture spacing setting controls to the layout.

        Displays options for base color size and spacing between textures
        in the generated atlas.

        Args:
            layout: The layout to draw into.
            scene: The current scene containing property values.
        """
        gap_col = layout.column(align=True)

        self._create_property_row(
            gap_col,
            'smc_diffuse_size',
            'Base Color Size:'
        )

        self._create_property_row(
            gap_col,
            'smc_gaps',
            'Spacing Between Textures:'
        )

    @staticmethod
    def _create_property_row(layout: bpy.types.UILayout, prop: str, label: str) -> None:
        """Create a property row with label and value input.

        Creates a two-column layout with label on the left and
        value input on the right.

        Args:
            layout: The layout to draw into.
            prop: The property name to create controls for.
            label: The display label for the property.
        """
        row = layout.row()
        col = row.column()
        col.scale_y = 1.2
        col.label(text=label)
        col = row.column()
        col.scale_x = 0.75
        col.scale_y = 1.2
        col.alignment = 'RIGHT'
        col.prop(bpy.context.scene, prop, text='')

    @staticmethod
    def _create_action_controls(layout: bpy.types.UILayout) -> None:
        """Create main action buttons for atlas generation.

        Adds buttons for initiating the atlas generation process.

        Args:
            layout: The layout to draw into.
        """
        col = layout.column()
        col.scale_y = 1.5
        col.operator(
            'smc.combiner',
            text='Generate Texture Atlas',
            icon_value=get_icon_id('save')
        ).cats = False

    @staticmethod
    def draw_pillow_installer(context: bpy.types.Context, layout: bpy.types.UILayout) -> None:
        """Draw centralized dependency status for standalone and CATS UI.

        Creates UI elements for installing Pillow and displaying
        help information.

        Args:
            context: The current Blender context.
            layout: The layout to draw into.
        """
        box = layout.box()
        status = globs.refresh_dependency_status()
        col = box.column(align=True)
        col.label(text='Material Combiner dependency issue', icon='ERROR')
        col.label(text=status.summary)
        if status.cause:
            col.label(text=f'Cause: {status.cause.replace("_", " ")}')
        col.separator()
        col.label(text=status.recovery)
        col.label(
            text=(
                f'Blender {status.blender_version}; '
                f'Python {status.python_version}; {status.architecture}'
            )
        )
        col.label(text=f'Dependency status: {status.category}')
        actions = box.column(align=True)
        actions.scale_y = 1.2
        actions.operator(
            'smc.get_pillow',
            text='Copy Dependency Diagnostics',
            icon='COPYDOWN',
        )

    @staticmethod
    def render_install_success(layout: bpy.types.UILayout) -> None:
        """Compatibility alias for callers expecting the legacy method."""
        MaterialCombinerPanel.draw_pillow_installer(bpy.context, layout)
