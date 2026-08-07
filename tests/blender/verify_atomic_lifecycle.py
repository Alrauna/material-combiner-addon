from __future__ import annotations

import importlib
import json
import os
import socket
import subprocess
import traceback
import urllib.request
from pathlib import Path

import bpy

MODULE = os.environ.get(
    "SMC_TEST_MODULE",
    "bl_ext.user_default.shotariyas_material_combiner",
)
RESULT = Path(os.environ["SMC_TEST_RESULT"])
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


def _classes(package):
    return package.registration.__dict__["__bl_classes"]


def _assert_clean(package) -> None:
    assert not package.registration._registered_classes
    assert all(
        not getattr(cls, "is_registered", False) for cls in _classes(package)
    )
    assert all(
        not hasattr(bpy.types.Scene, name)
        for name in package.extend_types._SCENE_PROPS
    )
    assert all(
        not hasattr(bpy.types.Material, name)
        for name in package.extend_types._MATERIAL_PROPS
    )
    assert package.icons.smc_icons is None


def _assert_registered(package) -> None:
    assert len(package.registration._registered_classes) == len(
        _classes(package)
    )
    assert all(
        getattr(cls, "is_registered", False) for cls in _classes(package)
    )
    assert all(
        hasattr(bpy.types.Scene, name)
        for name in package.extend_types._SCENE_PROPS
    )
    assert all(
        hasattr(bpy.types.Material, name)
        for name in package.extend_types._MATERIAL_PROPS
    )
    assert package.icons.smc_icons is not None


def _cycle_addon(package, cycles: int) -> None:
    for _index in range(cycles):
        assert bpy.ops.preferences.addon_enable(module=MODULE) == {"FINISHED"}
        _assert_registered(package)
        assert bpy.ops.preferences.addon_disable(module=MODULE) == {"FINISHED"}
        _assert_clean(package)


def _force_class_failure(package) -> None:
    original = bpy.utils.register_class
    calls = 0

    def fail_during_registration(cls):
        nonlocal calls
        calls += 1
        if calls == 5:
            raise RuntimeError("forced class registration failure")
        return original(cls)

    bpy.utils.register_class = fail_during_registration
    try:
        try:
            package.register()
        except RuntimeError as exc:
            assert str(exc) == "forced class registration failure"
        else:
            raise AssertionError("class registration failure was swallowed")
    finally:
        bpy.utils.register_class = original
    _assert_clean(package)


def _force_property_failure(package) -> None:
    original = package.extend_types._register_material_properties

    def fail_material_properties():
        raise RuntimeError("forced property registration failure")

    package.extend_types._register_material_properties = fail_material_properties
    try:
        try:
            package.register()
        except RuntimeError as exc:
            assert str(exc) == "forced property registration failure"
        else:
            raise AssertionError("property registration failure was swallowed")
    finally:
        package.extend_types._register_material_properties = original
    _assert_clean(package)


def main() -> None:
    report = {
        "module": MODULE,
        "blender": bpy.app.version_string,
        "checks": {},
        "errors": [],
    }
    package = None
    try:
        package = importlib.import_module(MODULE)
        _assert_clean(package)
        _cycle_addon(package, 3)
        report["checks"]["enable_disable_cycles"] = 3

        _force_class_failure(package)
        report["checks"]["class_failure_rollback"] = True

        _force_property_failure(package)
        report["checks"]["property_failure_rollback"] = True

        package.register()
        _assert_registered(package)
        package.unregister()
        _assert_clean(package)
        report["checks"]["recovery_after_failures"] = True
    except Exception as exc:
        report["errors"].append(
            {"error": repr(exc), "traceback": traceback.format_exc()}
        )
    finally:
        if package is not None:
            try:
                package.unregister()
            except Exception:
                pass

    report["network_attempts"] = NETWORK_ATTEMPTS
    report["subprocess_attempts"] = PROCESS_ATTEMPTS
    report["valid"] = (
        not report["errors"]
        and not NETWORK_ATTEMPTS
        and not PROCESS_ATTEMPTS
    )
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"valid": report["valid"], "result": str(RESULT)}))
    raise SystemExit(0 if report["valid"] else 1)


main()
