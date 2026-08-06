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

import bpy


MODULE = "bl_ext.user_default.shotariyas_material_combiner"
RESULT = Path(os.environ["SMC_TEST_RESULT"])
EXTENSIONS_ROOT = Path(os.environ["BLENDER_USER_EXTENSIONS"]).resolve()
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


def _inside(path: Path, root: Path) -> bool:
    path = path.resolve()
    root = root.resolve()
    return path == root or root in path.parents


def main() -> None:
    report = {
        "blender": bpy.app.version_string,
        "python": sys.version,
        "extensions_root": str(EXTENSIONS_ROOT),
        "paths": {},
        "errors": [],
    }
    enabled = False
    try:
        package = importlib.import_module(MODULE)
        updater = getattr(package.registration, "addon_updater_ops", None)
        if updater is not None:
            updater.check_for_update_background = lambda: None
        enable_result = bpy.ops.preferences.addon_enable(module=MODULE)
        enabled = enable_result == {"FINISHED"}
        assert enabled, enable_result
        status = package.globs.refresh_dependency_status()
        report["dependency_status"] = status.as_dict(include_paths=True)
        report["compatibility_globals"] = {
            "pil_available": package.globs.pil_available,
            "pil_install_attempted": package.globs.pil_install_attempted,
        }
        diagnostics_result = bpy.ops.smc.get_pillow()
        report["diagnostics_operator"] = {
            "result": sorted(diagnostics_result),
        }

        import PIL
        from PIL import Image, features
        import PIL._imaging as imaging

        paths = {
            "PIL": str(Path(PIL.__file__).resolve()),
            "PIL.Image": str(Path(Image.__file__).resolve()),
            "PIL._imaging": str(Path(imaging.__file__).resolve()),
        }
        report["paths"] = paths
        report["paths_in_extension_environment"] = {
            name: _inside(Path(value), EXTENSIONS_ROOT)
            for name, value in paths.items()
        }
        report["pillow_python_version"] = PIL.__version__
        report["pillow_native_version"] = getattr(
            imaging,
            "PILLOW_VERSION",
            None,
        ) or getattr(imaging, "__version__", None)
        report["pillow_feature_version"] = features.version_module("pil")
        report["native_imported"] = hasattr(imaging, "new")
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

    report["network_attempts"] = NETWORK_ATTEMPTS
    report["subprocess_attempts"] = PROCESS_ATTEMPTS
    report["valid"] = (
        not report["errors"]
        and all(report.get("paths_in_extension_environment", {}).values())
        and report.get("pillow_python_version") == "12.3.0"
        and report.get("pillow_native_version") == "12.3.0"
        and report.get("pillow_feature_version") == "12.3.0"
        and report.get("native_imported") is True
        and report.get("dependency_status", {}).get("category") == "healthy"
        and report.get("compatibility_globals", {}).get("pil_available") is True
        and report.get("compatibility_globals", {}).get(
            "pil_install_attempted"
        ) is False
        and report.get("diagnostics_operator", {}).get("result")
        == ["FINISHED"]
        and not NETWORK_ATTEMPTS
        and not PROCESS_ATTEMPTS
    )
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"valid": report["valid"], "result": str(RESULT)}))
    raise SystemExit(0 if report["valid"] else 1)


main()
