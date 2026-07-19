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
WORK = RESULT.parent / "preflight-work"
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


def _object_mode() -> None:
    if bpy.context.object is not None and bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")


def _clear_data() -> None:
    _object_mode()
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for material in list(bpy.data.materials):
        bpy.data.materials.remove(material)
    for image in list(bpy.data.images):
        bpy.data.images.remove(image)
    bpy.context.scene.smc_ob_data.clear()


def _make_color_material(name: str, color) -> bpy.types.Material:
    material = bpy.data.materials.new(name)
    material.diffuse_color = color
    material.use_nodes = True
    principled = material.node_tree.nodes.get("Principled BSDF")
    principled.inputs["Base Color"].default_value = color
    return material


def _make_image_material(
    name: str,
    path: Path,
) -> bpy.types.Material:
    image = bpy.data.images.load(str(path))
    image.pack()
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    texture = nodes.new("ShaderNodeTexImage")
    texture.name = "Image Texture"
    texture.image = image
    principled = nodes.get("Principled BSDF")
    material.node_tree.links.new(
        texture.outputs["Color"],
        principled.inputs["Base Color"],
    )
    return material


def _make_plane(
    name: str,
    x: float,
    material: bpy.types.Material,
    *,
    uv_scale=(1.0, 1.0),
    uv_offset=(0.0, 0.0),
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_plane_add(size=2.0, location=(x, 0.0, 0.0))
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    for loop in obj.data.uv_layers.active.data:
        loop.uv.x = loop.uv.x * uv_scale[0] + uv_offset[0]
        loop.uv.y = loop.uv.y * uv_scale[1] + uv_offset[1]
    return obj


def _build_color_fixture(count: int = 2):
    _clear_data()
    objects = []
    materials = []
    for index in range(count):
        material = _make_color_material(
            f"Preflight Color {index}",
            (0.2 + index * 0.2, 0.4, 0.6, 1.0),
        )
        materials.append(material)
        objects.append(
            _make_plane(
                f"Preflight Plane {index}",
                float(index * 3),
                material,
                uv_offset=(0.25, -0.25) if index == 0 else (0.0, 0.0),
            )
        )
    _set_selection(objects)
    return objects, materials


def _build_oversize_fixture():
    from PIL import Image

    _clear_data()
    input_directory = WORK / "oversize-input"
    input_directory.mkdir(parents=True, exist_ok=True)
    paths = [input_directory / "red.png", input_directory / "blue.png"]
    Image.new("RGBA", (1024, 1), (255, 0, 0, 255)).save(paths[0])
    Image.new("RGBA", (1024, 1), (0, 0, 255, 255)).save(paths[1])
    materials = [
        _make_image_material("Preflight Image A", paths[0]),
        _make_image_material("Preflight Image B", paths[1]),
        _make_color_material("Preflight Color C", (0.2, 0.5, 0.8, 1.0)),
    ]
    unrelated = bpy.data.materials.new("Preflight Unrelated")
    unrelated.root_mat = materials[0]
    objects = [
        _make_plane(
            "Preflight Plane A",
            -3.0,
            materials[0],
            uv_scale=(25.0, 1.0),
        ),
        _make_plane(
            "Preflight Plane B",
            0.0,
            materials[1],
            uv_offset=(0.25, -0.25),
        ),
        _make_plane("Preflight Plane C", 3.0, materials[2]),
    ]
    _set_selection([objects[0], objects[2]], active=objects[2])
    return objects, materials, unrelated


def _set_selection(objects, *, active=None) -> None:
    _object_mode()
    for obj in bpy.context.view_layer.objects:
        obj.select_set(False)
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = active or objects[0]


def _list_snapshot(scene: bpy.types.Scene):
    return [
        (
            item.ob.name if item.ob else None,
            item.ob_id,
            item.mat.name if item.mat else None,
            item.layer,
            item.used,
            item.type,
        )
        for item in scene.smc_ob_data
    ]


def _snapshot(directory: Path | None = None):
    scene = bpy.context.scene
    return {
        "settings": (
            scene.smc_save_path,
            scene.smc_size,
            scene.smc_gaps,
            scene.smc_list_id,
            scene.smc_ob_data_id,
        ),
        "list": _list_snapshot(scene),
        "roots": {
            material.name: material.root_mat.name if material.root_mat else None
            for material in bpy.data.materials
        },
        "images": sorted(image.name for image in bpy.data.images),
        "textures": sorted(texture.name for texture in bpy.data.textures),
        "objects": {
            obj.name: {
                "slots": [material.name for material in obj.data.materials],
                "indices": [poly.material_index for poly in obj.data.polygons],
                "uv": [
                    (round(loop.uv.x, 7), round(loop.uv.y, 7))
                    for loop in obj.data.uv_layers.active.data
                ] if obj.data.uv_layers.active else None,
                "selected": obj.select_get(),
            }
            for obj in scene.objects
            if obj.type == "MESH"
        },
        "active": (
            bpy.context.view_layer.objects.active.name
            if bpy.context.view_layer.objects.active
            else None
        ),
        "mode": bpy.context.mode,
        "files": (
            sorted(path.name for path in directory.iterdir())
            if directory and directory.is_dir()
            else []
        ),
    }


def _assert_cancelled_without_change(
    directory: Path | None,
    function,
) -> None:
    before = _snapshot(directory)
    result = function()
    assert result == {"CANCELLED"}, result
    after = _snapshot(directory)
    assert after == before, {"before": before, "after": after}


def _assert_raises_without_change(
    directory: Path | None,
    function,
    expected: str | None,
) -> None:
    before = _snapshot(directory)
    try:
        function()
    except RuntimeError as exc:
        if expected:
            assert expected in str(exc), exc
    else:
        raise AssertionError("injected failure did not propagate")
    after = _snapshot(directory)
    assert after == before, {"before": before, "after": after}


def _run_healthy_cases(report) -> None:
    scene = bpy.context.scene
    output = WORK / "output"
    output.mkdir(parents=True, exist_ok=True)

    objects, _materials = _build_color_fixture()
    bpy.ops.smc.refresh_ob_data()
    scene.smc_save_path = "preflight-sentinel"
    scene.smc_size = "STRICTCUST"
    scene.smc_gaps = 7
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.mode_set(mode="EDIT")
    _assert_cancelled_without_change(
        None,
        lambda: bpy.ops.smc.combiner(),
    )
    report["checks"]["no_directory"] = True
    _object_mode()

    missing = WORK / "does-not-exist"
    _assert_cancelled_without_change(
        missing,
        lambda: bpy.ops.smc.combiner(directory=str(missing)),
    )
    report["checks"]["missing_directory"] = True

    _clear_data()
    scene.smc_save_path = "empty-sentinel"
    _assert_cancelled_without_change(
        output,
        lambda: bpy.ops.smc.combiner(directory=str(output)),
    )
    report["checks"]["empty_scene"] = True

    _build_color_fixture(count=1)
    bpy.ops.smc.refresh_ob_data()
    scene.smc_save_path = "one-material-sentinel"
    _assert_cancelled_without_change(
        output,
        lambda: bpy.ops.smc.combiner(directory=str(output)),
    )
    report["checks"]["one_material"] = True

    _objects, materials, unrelated = _build_oversize_fixture()
    bpy.ops.smc.refresh_ob_data()
    scene.smc_packer_type = "BINARY_TREE"
    scene.smc_size = "AUTO"
    scene.smc_gaps = 2
    scene.smc_diffuse_size = 16
    scene.smc_save_path = "oversize-sentinel"
    _assert_cancelled_without_change(
        output,
        lambda: bpy.ops.smc.combiner(
            directory=str(output),
            cats=True,
        ),
    )
    assert unrelated.root_mat == materials[0]
    report["checks"]["oversize"] = True
    report["checks"]["cats_settings_operation_local"] = True

    # Force a failure after UV, slot, polygon, datablock, and list mutations
    # have begun. The entire attempted combine must roll back, including the
    # hidden staged PNG and newly-created Blender datablocks.
    _build_color_fixture()
    bpy.ops.smc.refresh_ob_data()
    operator_module = importlib.import_module(
        f"{MODULE}.operators.combiner.combiner"
    )
    original_finalize = operator_module.finalize_comb_mats

    def _fail_finalize(_build):
        raise RuntimeError("injected atlas finalize failure")

    operator_module.finalize_comb_mats = _fail_finalize
    try:
        _assert_raises_without_change(
            output,
            lambda: bpy.ops.smc.combiner(directory=str(output)),
            "injected atlas finalize failure",
        )
    finally:
        operator_module.finalize_comb_mats = original_finalize
    report["checks"]["post_mutation_failure_atomic"] = True

    # UV discovery aligns copies and does not mutate live mesh UV vectors.
    objects, _materials = _build_color_fixture()
    bpy.ops.smc.refresh_ob_data()
    combiner_ops = importlib.import_module(
        f"{MODULE}.operators.combiner.combiner_ops"
    )
    uv_before = [
        tuple(loop.uv)
        for obj in objects
        for loop in obj.data.uv_layers.active.data
    ]
    data = combiner_ops.get_data(scene.smc_ob_data)
    combiner_ops.get_mats_uv(scene, data)
    uv_after = [
        tuple(loop.uv)
        for obj in objects
        for loop in obj.data.uv_layers.active.data
    ]
    assert uv_after == uv_before
    report["checks"]["uv_preparation_uses_copies"] = True

    for value, check_name in (
        (float("inf"), "nonfinite_uv"),
        (26.25, "uv_repeat_limit"),
    ):
        objects, _materials = _build_color_fixture()
        objects[0].data.uv_layers.active.data[0].uv.x = value
        bpy.ops.smc.refresh_ob_data()
        _assert_cancelled_without_change(
            output,
            lambda: bpy.ops.smc.combiner(directory=str(output)),
        )
        report["checks"][check_name] = True

    operator_rna = bpy.ops.smc.combiner.get_rna_type()
    assert operator_rna.properties["directory"].subtype == "DIR_PATH"
    report["checks"]["directory_subtype"] = "DIR_PATH"


def _run_dependency_case(report, status) -> None:
    scene = bpy.context.scene
    output = WORK / "dependency-output"
    output.mkdir(parents=True, exist_ok=True)
    _build_color_fixture()
    bpy.ops.smc.refresh_ob_data()
    scene.smc_save_path = "dependency-sentinel"
    scene.smc_size = "STRICTCUST"
    scene.smc_gaps = 7
    _assert_cancelled_without_change(
        output,
        lambda: bpy.ops.smc.combiner(
            directory=str(output),
            cats=True,
        ),
    )
    report["checks"]["dependency_category"] = status.category
    report["checks"]["dependency_failure"] = True


def main() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    report = {
        "blender": bpy.app.version_string,
        "checks": {},
        "errors": [],
    }
    enabled = False
    try:
        package = importlib.import_module(MODULE)
        assert bpy.ops.preferences.addon_enable(module=MODULE) == {"FINISHED"}
        enabled = True
        status = package.globs.refresh_dependency_status()
        report["dependency_status"] = status.as_dict(include_paths=False)
        if status.healthy:
            _run_healthy_cases(report)
        else:
            _run_dependency_case(report, status)
    except Exception as exc:
        report["errors"].append(
            {"error": repr(exc), "traceback": traceback.format_exc()}
        )
    finally:
        _object_mode()
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
