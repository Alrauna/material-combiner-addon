from __future__ import annotations

import importlib.util
import json
import os
import sys
import traceback
from pathlib import Path

import bpy


MC = "bl_ext.user_default.shotariyas_material_combiner"
CATS = "bl_ext.user_default.cats_blender_plugin"
RESULT = Path(os.environ["SMC_TEST_RESULT"])
EXTENSIONS = Path(os.environ["BLENDER_USER_EXTENSIONS"])


def main() -> None:
    report = {
        "blender": bpy.app.version_string,
        "checks": {},
        "errors": [],
    }
    try:
        assert MC not in bpy.context.preferences.addons
        assert CATS not in bpy.context.preferences.addons
        assert importlib.util.find_spec(MC) is None
        assert importlib.util.find_spec(CATS) is None
        assert not (EXTENSIONS / "user_default" / MC.rsplit(".", 1)[1]).exists()
        assert not (
            EXTENSIONS / "user_default" / CATS.rsplit(".", 1)[1]
        ).exists()
        assert not hasattr(bpy.types.Scene, "smc_ob_data")
        assert not hasattr(bpy.types.Material, "root_mat")
        assert MC not in sys.modules
        assert CATS not in sys.modules
        report["checks"]["packages_absent"] = True
        report["checks"]["rna_clean"] = True
        report["checks"]["modules_absent"] = True
    except Exception as exc:
        report["errors"].append(
            {"error": repr(exc), "traceback": traceback.format_exc()}
        )

    report["valid"] = not report["errors"]
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"valid": report["valid"], "result": str(RESULT)}))
    raise SystemExit(0 if report["valid"] else 1)


main()
