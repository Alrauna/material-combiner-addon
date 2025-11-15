"""UI panel for displaying credits and support information.

This module provides a panel in the Blender UI that shows information about
the Material Combiner addon, including version, author credits, and links
for reporting issues or supporting development.
"""

import bpy

from ..icons import get_icon_id

ADDON_VERSION = "3.0.0"
DISCORD_URL = "https://discord.neoneko.xyz/"
GITHUB_ISSUES_URL = "https://github.com/teamneoneko/material-combiner-addon/issues"


class CreditsPanel(bpy.types.Panel):
    """Panel for displaying addon credits and support links.

    This class implements a Blender panel that displays information about
    the Material Combiner addon, including a version, credits, and links
    for support and bug reporting.
    """

    bl_label = "Credits & Support"
    bl_idname = "SMC_PT_Credits_Panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "MatCombiner"

    def draw(self, context: bpy.types.Context) -> None:
        """Draw the panel layout.

        Args:
            context: The current Blender context.
        """
        layout = self.layout
        self._draw_header_section(layout)
        self._draw_contact_section(layout)
        self._draw_support_section(layout)

    @staticmethod
    def _draw_header_section(layout: bpy.types.UILayout) -> None:
        """Draw the header section with addon name and author information.

        Args:
            layout: The layout to draw the section in.
        """
        box = layout.box()
        col = box.column()
        col.scale_y = 1.2

        col.label(
            text="Material Combiner {}".format(ADDON_VERSION),
            icon_value=get_icon_id("smc"),
        )

        author_row = box.row(align=True)
        author_row.scale_y = 1.2
        author_row.alignment = "LEFT"
        author_row.label(text="Created by:")
        author_row.label(text="shotariya", icon_value=get_icon_id("shot"))

    def _draw_contact_section(self, layout: bpy.types.UILayout) -> None:
        """Draw the contact section with issue reporting links.

        Args:
            layout: The layout to draw the section in.
        """
        box = layout.box()
        col = box.column(align=True)
        col.scale_y = 1.2

        col.label(text="Found an Issue?")
        self._create_link_button(
            col,
            text="Contact on Discord (@shotariya)",
            icon="discord",
            url=DISCORD_URL,
        )
        self._create_link_button(
            col,
            text="Report Bug on GitHub",
            icon="github",
            url=GITHUB_ISSUES_URL,
        )

    def _draw_support_section(self, layout: bpy.types.UILayout) -> None:
        """Draw the support section with financial support links.

        Args:
            layout: The layout to draw the section in.
        """
        box = layout.box()
        col = box.column(align=True)
        col.scale_y = 1.2

        col.label(text="Report Issues:")
        self._create_link_button(
            col, text="GitHub Issues", icon="github", url=GITHUB_ISSUES_URL
        )

    @staticmethod
    def _create_link_button(
        layout: bpy.types.UILayout, text: str, icon: str, url: str
    ) -> None:
        """Create a button that opens a URL when clicked.

        Args:
            layout: The layout to add the button to.
            text: The text to display on the button.
            icon: The icon identifier to use for the button.
            url: The URL to open when the button is clicked.
        """
        layout.operator(
            "smc.browser", text=text, icon_value=get_icon_id(icon)
        ).link = url
