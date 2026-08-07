from __future__ import annotations

import importlib
import importlib.util
import json
import os
import traceback
from pathlib import Path

import addon_utils
import bpy

MC = "bl_ext.user_default.shotariyas_material_combiner"
CATS = "bl_ext.user_default.cats_blender_plugin"
RESULT = Path(os.environ["SMC_TEST_RESULT"])
CONTRACT = Path(os.environ["SMC_TEST_CONTRACT"]).with_name(
    "stage0_behavior.json"
)


class OperatorProxy:
    def __init__(self, idname: str) -> None:
        self.idname = idname
        self.cats = False
        self.link = ""


class RecordingLayout:
    def __init__(self, calls=None, proxies=None) -> None:
        self.calls = [] if calls is None else calls
        self.proxies = [] if proxies is None else proxies
        self.scale_y = 1.0

    def _child(self, name, *args, **kwargs):
        self.calls.append((name, args, kwargs))
        return RecordingLayout(self.calls, self.proxies)

    def box(self):
        return self._child("box")

    def column(self, *args, **kwargs):
        return self._child("column", *args, **kwargs)

    def row(self, *args, **kwargs):
        return self._child("row", *args, **kwargs)

    def label(self, *args, **kwargs):
        self.calls.append(("label", args, kwargs))

    def separator(self, *args, **kwargs):
        self.calls.append(("separator", args, kwargs))

    def template_list(self, *args, **kwargs):
        self.calls.append(("template_list", args, kwargs))

    def operator(self, idname, *args, **kwargs):
        self.calls.append(("operator", (idname, *args), kwargs))
        proxy = OperatorProxy(idname)
        self.proxies.append(proxy)
        return proxy


def _load_atlas_helper():
    path = Path(__file__).with_name("verify_atlas_workflows.py")
    spec = importlib.util.spec_from_file_location("smc_atlas_helper", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _enabled(module: str) -> bool:
    return module in bpy.context.preferences.addons


def _assert_mc_registered() -> None:
    assert hasattr(bpy.types.Scene, "smc_ob_data")
    assert hasattr(bpy.types.Material, "root_mat")
    assert bpy.ops.smc.combiner.get_rna_type().identifier == "SMC_OT_combiner"


def main() -> None:
    helper = _load_atlas_helper()
    report = {
        "blender": bpy.app.version_string,
        "checks": {},
        "errors": [],
    }
    try:
        assert bpy.ops.preferences.addon_enable(module=MC) == {"FINISHED"}
        assert bpy.ops.preferences.addon_enable(module=CATS) == {"FINISHED"}
        assert _enabled(MC) and _enabled(CATS)
        _assert_mc_registered()
        report["checks"]["enable_order"] = [MC, CATS]

        optimization = importlib.import_module(f"{CATS}.ui.optimization")
        optimization.check_for_smc(force_refresh=True)
        assert callable(optimization.draw_smc_ui)
        report["checks"]["cats_discovery"] = True

        from PIL import Image as pillow_image

        helper.PILImage = pillow_image
        helper._build_fixture("cats-real-draw")
        bpy.ops.smc.refresh_ob_data()
        layout = RecordingLayout()
        optimization.custom_draw_smc_ui(bpy.context, layout)
        proxies = [
            proxy
            for proxy in layout.proxies
            if proxy.idname == "smc.combiner"
        ]
        assert len(proxies) == 1
        assert proxies[0].cats is True
        report["checks"]["cats_draw_sets_cats_true"] = True

        helper.WORK = RESULT.parent / "cats-checkpoint-atlas"
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        report["checks"]["cats_atlas"] = helper._run_case(
            "cats-triggered",
            cats=proxies[0].cats,
            expected=contract["cats_golden_atlas"],
        )

        assert bpy.ops.preferences.addon_disable(module=MC) == {"FINISHED"}
        assert not _enabled(MC)
        assert not hasattr(bpy.types.Scene, "smc_ob_data")
        optimization.check_for_smc(force_refresh=True)
        assert optimization.smc_is_disabled is True
        assert bpy.ops.preferences.addon_enable(module=MC) == {"FINISHED"}
        optimization.check_for_smc(force_refresh=True)
        assert callable(optimization.draw_smc_ui)
        report["checks"]["mc_cycle_while_cats_enabled"] = True

        assert bpy.ops.preferences.addon_disable(module=CATS) == {"FINISHED"}
        assert not _enabled(CATS)
        assert bpy.ops.preferences.addon_enable(module=CATS) == {"FINISHED"}
        report["checks"]["cats_cycle_while_mc_enabled"] = True

        reload_result = bpy.ops.script.reload()
        assert reload_result == {"FINISHED"}, reload_result
        assert _enabled(MC) and _enabled(CATS)
        _assert_mc_registered()
        report["checks"]["script_reload"] = ["FINISHED"]

        assert bpy.ops.wm.save_userpref() == {"FINISHED"}
        report["checks"]["preferences_saved_for_restart"] = True
        report["checks"]["addon_utils_enabled"] = {
            MC: list(addon_utils.check(MC)),
            CATS: list(addon_utils.check(CATS)),
        }
    except Exception as exc:
        report["errors"].append(
            {"error": repr(exc), "traceback": traceback.format_exc()}
        )

    report["network_attempts"] = helper.NETWORK_ATTEMPTS
    report["subprocess_attempts"] = helper.PROCESS_ATTEMPTS
    report["valid"] = (
        not report["errors"]
        and not helper.NETWORK_ATTEMPTS
        and not helper.PROCESS_ATTEMPTS
    )
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"valid": report["valid"], "result": str(RESULT)}))
    raise SystemExit(0 if report["valid"] else 1)


main()
