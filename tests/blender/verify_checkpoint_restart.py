from __future__ import annotations

import json
import os
import socket
import subprocess
import traceback
import urllib.request
from pathlib import Path

import bpy


MC = "bl_ext.user_default.shotariyas_material_combiner"
CATS = "bl_ext.user_default.cats_blender_plugin"
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


def main() -> None:
    report = {
        "blender": bpy.app.version_string,
        "checks": {},
        "errors": [],
    }
    try:
        assert MC in bpy.context.preferences.addons
        assert CATS in bpy.context.preferences.addons
        assert hasattr(bpy.types.Scene, "smc_ob_data")
        assert hasattr(bpy.types.Material, "root_mat")
        assert bpy.ops.smc.combiner.get_rna_type().identifier == (
            "SMC_OT_combiner"
        )
        report["checks"]["restart_loaded_both"] = True

        assert bpy.ops.preferences.addon_disable(module=CATS) == {"FINISHED"}
        assert bpy.ops.preferences.addon_disable(module=MC) == {"FINISHED"}
        assert not hasattr(bpy.types.Scene, "smc_ob_data")
        assert not hasattr(bpy.types.Material, "root_mat")
        assert bpy.ops.wm.save_userpref() == {"FINISHED"}
        report["checks"]["disabled_cleanly"] = True
    except Exception as exc:
        report["errors"].append(
            {"error": repr(exc), "traceback": traceback.format_exc()}
        )

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
