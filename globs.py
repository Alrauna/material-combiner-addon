"""Global constants and configuration for the Material Combiner addon.

This module contains configuration variables and constants used throughout 
the addon. Requires Blender 5.0+.
"""

import importlib.util
import site
import sys

import bpy

sys.path.insert(0, site.getusersitepackages())

pil_available = all(
    importlib.util.find_spec(module) is not None
    for module in ("PIL", "PIL.Image", "PIL.ImageChops")
)

pil_install_attempted = False

# Blender version checks (minimum version is now 5.0)
is_blender_5_plus = bpy.app.version >= (5, 0, 0)

ICON_OBJECT = "META_CUBE"
ICON_PROPERTIES = "PREFERENCES"
ICON_DROPDOWN = "THREE_DOTS"


class CombineListTypes:
    """Constants for material combination list entry types.

    These constants are used to identify the type of entry in the
    material combination list UI. They determine how entries are
    displayed, processed, and interacted with.
    """

    OBJECT = 0
    MATERIAL = 1
    SEPARATOR = 2
