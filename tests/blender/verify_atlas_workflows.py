from __future__ import annotations

import hashlib
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
WORK = RESULT.parent / "atlas-workflows"
CONTRACT = Path(os.environ["SMC_TEST_CONTRACT"]).with_name(
    "stage0_behavior.json"
)
CORRECTED_CONTRACT = CONTRACT.with_name("corrected_behavior.json")
NETWORK_ATTEMPTS: list[str] = []
PROCESS_ATTEMPTS: list[str] = []
PILImage = None


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


def _clear_data() -> None:
    if bpy.context.object and bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for collection in (
        bpy.data.meshes,
        bpy.data.materials,
        bpy.data.textures,
        bpy.data.images,
        bpy.data.curves,
    ):
        for datablock in list(collection):
            collection.remove(datablock)
    bpy.context.scene.smc_ob_data.clear()


def _write_input_png(path: Path, size, pixels) -> None:
    image = PILImage.new("RGBA", size)
    image.putdata(pixels)
    image.save(path)


def _make_image_material(name: str, path: Path, *, diffuse=False):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    material.diffuse_color = (1.0, 1.0, 1.0, 1.0)
    nodes = material.node_tree.nodes
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    principled = nodes.new("ShaderNodeBsdfPrincipled")
    texture = nodes.new("ShaderNodeTexImage")
    image = bpy.data.images.load(str(path))
    image.pack()
    texture.image = image
    material.node_tree.links.new(
        texture.outputs["Color"],
        principled.inputs["Base Color"],
    )
    material.node_tree.links.new(
        texture.outputs["Alpha"],
        principled.inputs["Alpha"],
    )
    material.node_tree.links.new(
        principled.outputs["BSDF"],
        output.inputs["Surface"],
    )
    material.smc_diffuse = diffuse
    return material


def _make_color_material(name: str, rgba):
    material = bpy.data.materials.new(name)
    material.diffuse_color = rgba
    material.use_nodes = True
    principled = material.node_tree.nodes.get("Principled BSDF")
    principled.inputs["Base Color"].default_value = rgba
    principled.inputs["Alpha"].default_value = rgba[3]
    material.smc_diffuse = True
    return material


def _make_plane(
    name: str,
    x: float,
    material: bpy.types.Material,
    *,
    uv_scale=(1.0, 1.0),
    uv_offset=(0.0, 0.0),
):
    bpy.ops.mesh.primitive_plane_add(size=2.0, location=(x, 0.0, 0.0))
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    for loop in obj.data.uv_layers.active.data:
        loop.uv.x = loop.uv.x * uv_scale[0] + uv_offset[0]
        loop.uv.y = loop.uv.y * uv_scale[1] + uv_offset[1]
    return obj


def _build_fixture(name: str):
    _clear_data()
    input_directory = WORK / name / "inputs"
    input_directory.mkdir(parents=True, exist_ok=True)
    path_a = input_directory / "rgba_a.png"
    path_b = input_directory / "rgba_b.png"
    pixels_a = [
        (255, 0, 0, 128),
        (255, 0, 0, 128),
        (0, 255, 0, 255),
        (0, 255, 0, 255),
    ] * 2
    pixels_b = [
        (0, 0, 255, 255),
        (255, 255, 0, 64),
    ] * 4
    _write_input_png(path_a, (4, 2), pixels_a)
    _write_input_png(path_b, (2, 4), pixels_b)
    material_a = _make_image_material("Fixture Image A", path_a)
    material_b = _make_image_material("Fixture Image B", path_b)
    material_c = _make_color_material(
        "Fixture Color C",
        (0.25, 0.5, 0.75, 0.5),
    )
    objects = [
        _make_plane(
            "Fixture Plane A",
            -3.0,
            material_a,
            uv_scale=(1.5, 1.25),
        ),
        _make_plane(
            "Fixture Plane B",
            0.0,
            material_b,
            uv_offset=(0.25, -0.25),
        ),
        _make_plane("Fixture Plane C", 3.0, material_c),
    ]
    for obj in bpy.context.view_layer.objects:
        obj.select_set(False)
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    return objects


def _run_case(name: str, *, cats: bool, expected) -> dict:
    _build_fixture(name)
    scene = bpy.context.scene
    scene.smc_packer_type = "BINARY_TREE"
    scene.smc_size = "AUTO" if not cats else "STRICTCUST"
    scene.smc_size_width = 1024
    scene.smc_size_height = 512
    scene.smc_crop = True
    scene.smc_pixel_art = False
    scene.smc_gaps = 2 if not cats else 7
    scene.smc_diffuse_size = 16
    original_settings = (scene.smc_size, scene.smc_gaps)
    output = WORK / name / "output"
    output.mkdir(parents=True, exist_ok=True)

    assert bpy.ops.smc.combiner(
        directory=str(output),
        cats=cats,
    ) == {"FINISHED"}
    paths = sorted(output.glob("Atlas_*.png"))
    assert len(paths) == 1, paths
    path = paths[0]
    with PILImage.open(path) as image:
        dimensions = list(image.size)
        mode = image.mode
    sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    assert dimensions == expected["dimensions"]
    assert sha256 == expected["sha256"]
    assert mode == "RGBA"
    assert (scene.smc_size, scene.smc_gaps) == original_settings
    return {
        "result": ["FINISHED"],
        "filename": path.name,
        "dimensions": dimensions,
        "sha256": sha256,
        "settings_before_after": list(original_settings),
    }


def _sample_blender_uv(image, uv):
    x = min(image.width - 1, max(0, int(uv.x * image.width)))
    y = min(image.height - 1, max(0, int((1.0 - uv.y) * image.height)))
    return image.getpixel((x, y))


def _run_rectpack_rotation_case() -> dict:
    """Verify rotated pixels and UVs agree for an asymmetric source."""
    _clear_data()
    root = WORK / "rectpack-rotation"
    inputs = root / "inputs"
    output = root / "output"
    inputs.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)

    path_a = inputs / "wide.png"
    path_b = inputs / "tall.png"
    source_a = PILImage.new("RGBA", (8, 2))
    for y in range(source_a.height):
        for x in range(source_a.width):
            source_a.putpixel((x, y), (20 + x * 20, 30 + y * 120, 70, 255))
    source_a.save(path_a)
    source_b = PILImage.new("RGBA", (3, 7), (10, 220, 180, 255))
    source_b.save(path_b)

    material_a = _make_image_material("Rotation Wide", path_a)
    material_b = _make_image_material("Rotation Tall", path_b)
    object_a = _make_plane("Rotation Plane Wide", -2.0, material_a)
    object_b = _make_plane("Rotation Plane Tall", 2.0, material_b)
    source_uvs = (
        (0.0625, 0.25),
        (0.4375, 0.25),
        (0.6875, 0.75),
        (0.9375, 0.75),
    )
    for loop, uv in zip(object_a.data.uv_layers.active.data, source_uvs):
        loop.uv = uv

    for obj in bpy.context.view_layer.objects:
        obj.select_set(False)
    object_a.select_set(True)
    object_b.select_set(True)
    bpy.context.view_layer.objects.active = object_a

    scene = bpy.context.scene
    scene.smc_packer_type = "RECT_PACK2D"
    scene.smc_size = "AUTO"
    scene.smc_crop = False
    scene.smc_pixel_art = True
    scene.smc_gaps = 0

    assert bpy.ops.smc.combiner(directory=str(output)) == {"FINISHED"}
    paths = sorted(output.glob("Atlas_*.png"))
    assert len(paths) == 1, paths
    with PILImage.open(paths[0]) as atlas:
        atlas.load()
        for loop, source_uv in zip(
            object_a.data.uv_layers.active.data,
            source_uvs,
        ):
            source_x = min(
                source_a.width - 1,
                int(source_uv[0] * source_a.width),
            )
            source_y = min(
                source_a.height - 1,
                int((1.0 - source_uv[1]) * source_a.height),
            )
            assert _sample_blender_uv(atlas, loop.uv) == source_a.getpixel(
                (source_x, source_y)
            )
        dimensions = list(atlas.size)
    assert dimensions == [5, 8], dimensions
    return {
        "dimensions": dimensions,
        "clockwise_pixel_and_uv_rotation": True,
    }


def main() -> None:
    global PILImage
    WORK.mkdir(parents=True, exist_ok=True)
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    corrected = json.loads(CORRECTED_CONTRACT.read_text(encoding="utf-8"))
    report = {
        "blender": bpy.app.version_string,
        "checks": {},
        "errors": [],
    }
    enabled = False
    try:
        importlib.import_module(MODULE)
        assert bpy.ops.preferences.addon_enable(module=MODULE) == {"FINISHED"}
        enabled = True
        from PIL import Image as pillow_image

        PILImage = pillow_image
        from PIL import ImageFile

        max_pixels = PILImage.MAX_IMAGE_PIXELS
        load_truncated = ImageFile.LOAD_TRUNCATED_IMAGES
        report["checks"]["standalone"] = _run_case(
            "standalone",
            cats=False,
            expected=corrected["standalone_golden_atlases"]["BINARY_TREE"],
        )
        report["checks"]["cats_operator"] = _run_case(
            "cats-operator",
            cats=True,
            expected=contract["cats_golden_atlas"],
        )
        report["checks"]["rectpack_rotation"] = (
            _run_rectpack_rotation_case()
        )
        assert PILImage.MAX_IMAGE_PIXELS == max_pixels
        assert ImageFile.LOAD_TRUNCATED_IMAGES == load_truncated
        report["checks"]["pillow_safety_defaults_unchanged"] = True
    except Exception as exc:
        report["errors"].append(
            {"error": repr(exc), "traceback": traceback.format_exc()}
        )
    finally:
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


if __name__ == "__main__":
    main()
