"""Global constants and configuration for the Material Combiner addon.

This module contains configuration variables and constants used throughout 
the addon. Requires Blender 5.0+.
"""

import bpy

from .dependencies import get_dependency_status

dependency_status = get_dependency_status()
pil_available = dependency_status.healthy

# CATS 5.0 and 5.2 call the centralized dependency UI while this remains
# false. It no longer means that an installer ran.
pil_install_attempted = False


def refresh_dependency_status(cats_invocation: bool = False):
    """Refresh compatibility globals from the immutable dependency status."""
    global dependency_status, pil_available, pil_install_attempted
    dependency_status = get_dependency_status(cats_invocation=cats_invocation)
    pil_available = dependency_status.healthy
    pil_install_attempted = False
    return dependency_status

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
