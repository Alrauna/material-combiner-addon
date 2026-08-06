"""Registration module for the Material Combiner addon.

This module handles the registration and unregistration of all Blender classes
used by the addon. It also manages property annotations and initializes the
icon system.
"""

import bpy

from . import (
    extend_lists,
    extend_types,
    globs,
    operators,
    ui,
)
from .icons import initialize_smc_icons, unload_smc_icons
from .type_annotations import BlClasses

__bl_classes = [
    ui.selection_menu.SMC_MT_SelectionMenu,

    ui.credits_panel.CreditsPanel,
    ui.main_panel.MaterialCombinerPanel,
    ui.property_panel.PropertyMenu,
    ui.update_panel.UpdatePanel,

    operators.browser.OpenBrowser,
    operators.combine_list.MaterialListRefreshOperator,
    operators.combine_list.MaterialListToggleOperator,
    operators.combine_list.SelectAllMaterials,
    operators.combine_list.SelectNoneMaterials,
    operators.combiner.Combiner,
    operators.get_pillow.InstallPIL,

    extend_types.CombineListEntry,
    extend_types.UpdatePreferences,

    extend_lists.SMC_UL_Combine_List,
]

_registered_classes: list[BlClasses] = []


def register_all() -> None:
    """Register all components of the addon.
    
    This is the main registration function called when the addon is enabled.
    It registers all classes and initializes icons.
    """
    try:
        _register_classes()
        initialize_smc_icons()
        extend_types.register()
    except BaseException:
        _rollback_registration()
        raise


def unregister_all() -> None:
    """Unregister all components of the addon.
    
    This is the main unregistration function called when the addon is disabled.
    It unregisters all classes and cleans up icons.
    """
    _cleanup_registration(raise_errors=True)


def _register_classes() -> None:
    """Register all Blender classes used by the addon.
    
    Converts properties to annotations and records every successful class so a
    later failure can be rolled back in reverse dependency order.
    """
    if _registered_classes:
        raise RuntimeError('Material Combiner classes are already registered')

    for cls in __bl_classes:
        make_annotations(cls)
        bpy.utils.register_class(cls)
        _registered_classes.append(cls)
    print('Registered', len(_registered_classes), 'Material Combiner classes.')


def _unregister_classes() -> None:
    """Unregister all Blender classes used by the addon.
    
    Classes are unregistered in reverse order to handle dependencies.
    """
    count = 0
    classes = list(_registered_classes) or list(__bl_classes)
    errors = []
    for cls in reversed(classes):
        if not getattr(cls, 'is_registered', False):
            continue
        try:
            bpy.utils.unregister_class(cls)
            count += 1
        except Exception as exc:
            errors.append(exc)
    _registered_classes.clear()
    print('Unregistered', count, 'Material Combiner classes.')
    if errors:
        raise RuntimeError(
            f'Failed to unregister {len(errors)} Material Combiner classes'
        ) from errors[0]


def _rollback_registration() -> None:
    """Undo every completed registration phase after an enable failure."""
    _cleanup_registration(raise_errors=False)


def _cleanup_registration(*, raise_errors: bool) -> None:
    """Clean every lifecycle phase, continuing after individual failures."""
    cleanup_errors = []
    for cleanup in (
        extend_types.unregister,
        unload_smc_icons,
        _unregister_classes,
    ):
        try:
            cleanup()
        except Exception as exc:
            cleanup_errors.append(exc)
    for error in cleanup_errors:
        print('Material Combiner rollback error:', repr(error))
    if cleanup_errors and raise_errors:
        raise RuntimeError(
            f'Material Combiner cleanup failed in {len(cleanup_errors)} phases'
        ) from cleanup_errors[0]


def make_annotations(cls: BlClasses) -> BlClasses:
    """Convert class properties to annotations for Blender 2.80+.

    This function handles property definition for the extension system.

    Args:
        cls: Blender class to process.

    Returns:
        The processed class with properties converted to annotations.
    """
    # Blender 5.0+ uses _PropertyDeferred for properties
    bl_props = {k: v for k, v in cls.__dict__.items() if isinstance(v, bpy.props._PropertyDeferred)}

    if bl_props:
        if '__annotations__' not in cls.__dict__:
            cls.__annotations__ = {}

        annotations = cls.__dict__['__annotations__']

        for k, v in bl_props.items():
            annotations[k] = v
            delattr(cls, k)

    return cls
