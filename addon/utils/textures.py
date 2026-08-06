"""Texture handling utilities for Material Combiner.

This module is maintained for backward compatibility but is not actively used
in Blender 5.0+ as the addon only supports node-based materials.
"""

from typing import Optional

import bpy


def get_texture(mat: bpy.types.Material) -> Optional[bpy.types.Texture]:
    """Get texture from a material's texture slots.

    Note: This function is deprecated and only for legacy compatibility.
    Blender 5.0+ does not support texture slots. Always returns None.

    Args:
        mat: Material to extract texture from.

    Returns:
        None - texture slots are not supported in Blender 5.0+
    """
    # Blender 5.0+ does not support texture_slots
    # All materials must use node-based shaders
    return None
