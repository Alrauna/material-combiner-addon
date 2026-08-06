from __future__ import annotations

import importlib
import json
import os
import socket
import subprocess
import sys
import traceback
import urllib.request
from pathlib import Path

import addon_utils
import bpy


MODULE = os.environ.get(
    "SMC_TEST_MODULE",
    "bl_ext.user_default.shotariyas_material_combiner",
)
CONTRACT = Path(os.environ["SMC_TEST_CONTRACT"])
RESULT = Path(os.environ["SMC_TEST_RESULT"])
PILLOW_ROOT = os.environ.get("SMC_TEST_PILLOW_ROOT")
NETWORK_ATTEMPTS: list[str] = []
PROCESS_ATTEMPTS: list[str] = []


def _blocked_network(*args, **kwargs):
    NETWORK_ATTEMPTS.append(repr((args, kwargs)))
    raise OSError("network disabled by Material Combiner test harness")


def _blocked_process(*args, **kwargs):
    PROCESS_ATTEMPTS.append(repr((args, kwargs)))
    raise RuntimeError("subprocess disabled by Material Combiner test harness")


urllib.request.urlopen = _blocked_network
socket.create_connection = _blocked_network
socket.socket.connect = _blocked_network
subprocess.call = _blocked_process
subprocess.run = _blocked_process
subprocess.check_call = _blocked_process
subprocess.check_output = _blocked_process
subprocess.Popen = _blocked_process

if PILLOW_ROOT:
    sys.path.insert(0, PILLOW_ROOT)


def _operator_defaults(idname: str) -> dict[str, object]:
    namespace, name = idname.split(".", 1)
    operator = getattr(getattr(bpy.ops, namespace), name)
    rna = operator.get_rna_type()
    return {
        prop.identifier: prop.default
        for prop in rna.properties
        if prop.identifier != "rna_type"
    }


def _rna_defaults(rna_type, identifiers: list[str]) -> dict[str, object]:
    result = {}
    for identifier in identifiers:
        prop = rna_type.bl_rna.properties[identifier]
        result[identifier] = (
            None if prop.type in {"POINTER", "COLLECTION"} else prop.default
        )
    return result


def _class_snapshot(package, values):
    snapshot = []
    for module_name, class_name, expected_idname in values:
        module = importlib.import_module(f"{package.__name__}.{module_name}")
        cls = getattr(module, class_name)
        snapshot.append(
            [
                module_name,
                class_name,
                getattr(cls, "bl_idname", None) or None,
            ]
        )
        if expected_idname is not None:
            assert snapshot[-1][2] == expected_idname
    return snapshot


def _assert_symbol(package, dotted_name: str) -> None:
    target = package
    for part in dotted_name.split("."):
        target = getattr(target, part)


def main() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    report = {
        "module": MODULE,
        "blender": bpy.app.version_string,
        "python": sys.version,
        "checks": {},
        "errors": [],
    }
    enabled = False
    try:
        package = importlib.import_module(MODULE)
        updater = getattr(package.registration, "addon_updater_ops", None)
        if updater is not None:
            updater.check_for_update_background = lambda: None
        result = bpy.ops.preferences.addon_enable(module=MODULE)
        enabled = result == {"FINISHED"}
        assert enabled, result

        classes = _class_snapshot(
            package,
            contract["registered_classes"],
        )
        report["checks"]["registered_class_snapshot"] = classes
        assert classes == contract["registered_classes"]
        report["checks"]["registered_classes"] = len(classes)

        actual_operators = {
            idname: _operator_defaults(idname)
            for idname in contract["operators"]
        }
        assert actual_operators == contract["operators"]
        report["checks"]["operators"] = actual_operators

        scene_props = contract["scene_properties"]
        material_props = contract["material_properties"]
        assert all(hasattr(bpy.types.Scene, name) for name in scene_props)
        assert all(hasattr(bpy.types.Material, name) for name in material_props)
        assert _rna_defaults(
            bpy.types.Scene,
            list(contract["scene_defaults"]),
        ) == contract["scene_defaults"]
        assert _rna_defaults(
            bpy.types.Material,
            list(contract["material_defaults"]),
        ) == contract["material_defaults"]
        report["checks"]["scene_properties"] = scene_props
        report["checks"]["material_properties"] = material_props

        entry = package.extend_types.CombineListEntry
        assert _rna_defaults(
            entry,
            list(contract["combine_list_entry_defaults"]),
        ) == contract["combine_list_entry_defaults"]
        ui_list = package.extend_lists.SMC_UL_Combine_List
        assert _rna_defaults(
            ui_list,
            list(contract["ui_list_defaults"]),
        ) == contract["ui_list_defaults"]
        preferences = package.extend_types.UpdatePreferences
        assert _rna_defaults(
            preferences,
            list(contract["preferences_defaults"]),
        ) == contract["preferences_defaults"]

        for module_path in contract["cats_contract"]["module_paths"]:
            importlib.import_module(f"{MODULE}.{module_path}")
        for symbol in contract["cats_contract"]["symbols"]:
            _assert_symbol(package, symbol)
        report["checks"]["cats_contract"] = True
    except Exception as exc:
        report["errors"].append(
            {
                "error": repr(exc),
                "traceback": traceback.format_exc(),
            }
        )
    finally:
        if enabled:
            try:
                bpy.ops.preferences.addon_disable(module=MODULE)
            except Exception as exc:
                report["errors"].append(
                    {
                        "error": repr(exc),
                        "traceback": traceback.format_exc(),
                    }
                )

    contract_scene_props = contract["scene_properties"]
    contract_material_props = contract["material_properties"]
    report["checks"]["unregistered_scene_properties"] = all(
        not hasattr(bpy.types.Scene, name) for name in contract_scene_props
    )
    report["checks"]["unregistered_material_properties"] = all(
        not hasattr(bpy.types.Material, name) for name in contract_material_props
    )
    report["network_attempts"] = NETWORK_ATTEMPTS
    report["subprocess_attempts"] = PROCESS_ATTEMPTS
    report["valid"] = (
        not report["errors"]
        and report["checks"]["unregistered_scene_properties"]
        and report["checks"]["unregistered_material_properties"]
        and not NETWORK_ATTEMPTS
        and not PROCESS_ATTEMPTS
    )
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"valid": report["valid"], "result": str(RESULT)}))
    raise SystemExit(0 if report["valid"] else 1)


main()
