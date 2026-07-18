from __future__ import annotations

import importlib
import json
import os
import socket
import subprocess
import traceback
import urllib.request
from pathlib import Path
from types import SimpleNamespace

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


class RecordingLayout:
    def __init__(self, calls=None):
        self.calls = [] if calls is None else calls
        self.scale_y = 1.0

    def _child(self, name, *args, **kwargs):
        self.calls.append((name, args, kwargs))
        return RecordingLayout(self.calls)

    def box(self):
        return self._child("box")

    def column(self, *args, **kwargs):
        return self._child("column", *args, **kwargs)

    def row(self, *args, **kwargs):
        return self._child("row", *args, **kwargs)

    def label(self, *args, **kwargs):
        self.calls.append(("label", args, kwargs))

    def operator(self, *args, **kwargs):
        self.calls.append(("operator", args, kwargs))
        return SimpleNamespace(cats=False, link="")

    def separator(self, *args, **kwargs):
        self.calls.append(("separator", args, kwargs))

    def template_list(self, *args, **kwargs):
        self.calls.append(("template_list", args, kwargs))


def main() -> None:
    report = {
        "blender": bpy.app.version_string,
        "checks": {},
        "errors": [],
    }
    enabled = False
    material = None
    try:
        package = importlib.import_module(MODULE)
        assert bpy.ops.preferences.addon_enable(module=MODULE) == {"FINISHED"}
        enabled = True

        material = bpy.data.materials.new("SMC UI Preview Fallback")
        assert material.preview is None
        item = SimpleNamespace(mat=material)
        ui_list = package.extend_lists.SMC_UL_Combine_List
        preview_id = ui_list._get_material_preview_id(item)
        assert preview_id == 0
        report["checks"]["preview_fallback_icon_value"] = preview_id

        layout = RecordingLayout()
        cats_ui = importlib.import_module(f"{MODULE}.operators.ui.include")
        cats_ui.draw_ui(bpy.context, layout)
        operator_ids = [
            args[0]
            for name, args, _kwargs in layout.calls
            if name == "operator"
        ]
        assert "smc.refresh_ob_data" in operator_ids
        assert "smc.combiner" in operator_ids
        report["checks"]["cats_draw_operator_ids"] = operator_ids

        dependency_layout = RecordingLayout()
        package.ui.main_panel.MaterialCombinerPanel.draw_pillow_installer(
            bpy.context,
            dependency_layout,
        )
        dependency_operators = [
            args[0]
            for name, args, _kwargs in dependency_layout.calls
            if name == "operator"
        ]
        assert dependency_operators == ["smc.get_pillow"]
        report["checks"]["dependency_draw_operator_ids"] = (
            dependency_operators
        )
    except Exception as exc:
        report["errors"].append(
            {"error": repr(exc), "traceback": traceback.format_exc()}
        )
    finally:
        if material is not None:
            bpy.data.materials.remove(material)
        if enabled:
            bpy.ops.preferences.addon_disable(module=MODULE)

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
