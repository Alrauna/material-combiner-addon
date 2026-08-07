from __future__ import annotations

import importlib
import json
import os
import socket
import subprocess
import tomllib
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
    def __init__(self, calls=None, operators=None):
        self.calls = [] if calls is None else calls
        self.operators = [] if operators is None else operators
        self.scale_y = 1.0

    def _child(self, name, *args, **kwargs):
        self.calls.append((name, args, kwargs))
        return RecordingLayout(self.calls, self.operators)

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
        result = SimpleNamespace(cats=False, link="")
        self.operators.append(result)
        return result

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

        credits_layout = RecordingLayout()
        credits = package.ui.credits_panel.CreditsPanel
        credits._draw_header_section(credits_layout)
        credits._draw_contact_section(credits, credits_layout)
        credits._draw_support_section(credits, credits_layout)
        manifest = tomllib.loads(
            (Path(package.__file__).parent / "blender_manifest.toml").read_text(
                encoding="utf-8"
            )
        )
        label_texts = [
            args[0] if args else kwargs.get("text", "")
            for name, args, kwargs in credits_layout.calls
            if name == "label"
        ]
        version_labels = [
            text
            for text in label_texts
            if str(text).startswith("Material Combiner")
        ]
        assert version_labels == [
            "Material Combiner {}".format(manifest["version"])
        ], version_labels
        # Attribution: the original author and the current maintainer, with
        # the maintainer taken from the manifest rather than hardcoded.
        maintainer = manifest["maintainer"].split(" <")[0]
        assert "Created by:" in label_texts, label_texts
        assert "shotariya" in label_texts, label_texts
        assert "Maintained by:" in label_texts, label_texts
        assert maintainer in label_texts, label_texts
        report["checks"]["credits_attribution"] = [
            text
            for text in label_texts
            if text in ("Created by:", "shotariya", "Maintained by:", maintainer)
        ]
        credits_links = [entry.link for entry in credits_layout.operators]
        assert not [link for link in credits_links if "discord" in link.lower()]
        report["checks"]["credits_version_label"] = version_labels[0]
        report["checks"]["credits_links"] = credits_links
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
