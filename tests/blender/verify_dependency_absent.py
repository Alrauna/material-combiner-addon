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


MODULE = "bl_ext.user_default.shotariyas_material_combiner"
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
    report = {"errors": []}
    enabled = False
    try:
        package = importlib.import_module(MODULE)
        updater = getattr(package.registration, "addon_updater_ops", None)
        if updater is not None:
            updater.check_for_update_background = lambda: None
        result = bpy.ops.preferences.addon_enable(module=MODULE)
        enabled = result == {"FINISHED"}
        assert enabled, result
        status = package.globs.refresh_dependency_status()
        report["status"] = status.as_dict(include_paths=True)
        report["compatibility_globals"] = {
            "pil_available": package.globs.pil_available,
            "pil_install_attempted": package.globs.pil_install_attempted,
        }
        report["diagnostics_result"] = sorted(bpy.ops.smc.get_pillow())
    except Exception as exc:
        report["errors"].append(
            {
                "error": repr(exc),
                "traceback": traceback.format_exc(),
            }
        )
    finally:
        if enabled:
            bpy.ops.preferences.addon_disable(module=MODULE)

    report["network_attempts"] = NETWORK_ATTEMPTS
    report["subprocess_attempts"] = PROCESS_ATTEMPTS
    report["valid"] = (
        not report["errors"]
        and report.get("status", {}).get("category") == "wheel_missing"
        and report.get("compatibility_globals")
        == {
            "pil_available": False,
            "pil_install_attempted": False,
        }
        and report.get("diagnostics_result") == ["CANCELLED"]
        and not NETWORK_ATTEMPTS
        and not PROCESS_ATTEMPTS
    )
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"valid": report["valid"], "result": str(RESULT)}))
    raise SystemExit(0 if report["valid"] else 1)


main()
