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
from types import SimpleNamespace

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


def _make_material_from_image(
    name: str,
    image: bpy.types.Image,
    *,
    diffuse=False,
    input_name="Base Color",
):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    material.diffuse_color = (1.0, 1.0, 1.0, 1.0)
    nodes = material.node_tree.nodes
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    principled = nodes.new("ShaderNodeBsdfPrincipled")
    texture = nodes.new("ShaderNodeTexImage")
    texture.image = image
    material.node_tree.links.new(
        texture.outputs["Color"],
        principled.inputs[input_name],
    )
    if input_name == "Base Color":
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


def _make_image_material(
    name: str,
    path: Path,
    *,
    diffuse=False,
    pack=True,
    input_name="Base Color",
):
    image = bpy.data.images.load(str(path))
    if pack:
        image.pack()
    return _make_material_from_image(
        name,
        image,
        diffuse=diffuse,
        input_name=input_name,
    )


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
        pixel_sha256 = hashlib.sha256(image.tobytes()).hexdigest()
    sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    assert dimensions == expected["dimensions"]
    # Assert decoded pixels, not PNG bytes. The container encoding depends on
    # which zlib implementation Pillow links (zlib-ng on Windows, stock zlib
    # on Linux), so file hashes differ across platforms for identical images.
    assert pixel_sha256 == expected["pixel_sha256"], pixel_sha256
    assert mode == "RGBA"
    assert (scene.smc_size, scene.smc_gaps) == original_settings
    return {
        "result": ["FINISHED"],
        "filename": path.name,
        "dimensions": dimensions,
        "pixel_sha256": pixel_sha256,
        "file_sha256": sha256,
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


def _select_pair(material_a, material_b, name):
    objects = (
        _make_plane(f"{name} A", -2.0, material_a),
        _make_plane(f"{name} B", 2.0, material_b),
    )
    for obj in bpy.context.view_layer.objects:
        obj.select_set(False)
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    return objects


def _configure_safe_input_case():
    scene = bpy.context.scene
    scene.smc_packer_type = "BINARY_TREE"
    scene.smc_size = "AUTO"
    scene.smc_crop = False
    scene.smc_pixel_art = True
    scene.smc_gaps = 0
    scene.smc_diffuse_size = 4


def _run_input_source_cases() -> dict:
    root = WORK / "input-sources"
    root.mkdir(parents=True, exist_ok=True)
    checks = {}

    # Ordinary external files remain external and are never implicitly packed.
    _clear_data()
    external_dir = root / "external"
    external_dir.mkdir(parents=True, exist_ok=True)
    external_path = external_dir / "external.png"
    PILImage.new("RGBA", (2, 2), (240, 40, 20, 255)).save(external_path)
    external_material = _make_image_material(
        "External File",
        external_path,
        pack=False,
    )
    external_image = next(
        node.image
        for node in external_material.node_tree.nodes
        if node.bl_idname == "ShaderNodeTexImage"
    )
    _select_pair(
        external_material,
        _make_color_material("External Color", (0.1, 0.2, 0.3, 1.0)),
        "External",
    )
    _configure_safe_input_case()
    external_output = external_dir / "output"
    external_output.mkdir(exist_ok=True)
    assert bpy.ops.smc.combiner(directory=str(external_output)) == {"FINISHED"}
    assert external_image.packed_file is None
    checks["external_file_not_packed"] = True

    # Non-float generated images contribute their pixels rather than a color fallback.
    _clear_data()
    generated_dir = root / "generated"
    generated_dir.mkdir(parents=True, exist_ok=True)
    generated = bpy.data.images.new(
        "Generated Source",
        width=2,
        height=2,
        alpha=True,
        float_buffer=False,
    )
    generated.pixels = (
        1.0, 0.0, 0.0, 1.0,
        0.0, 1.0, 0.0, 1.0,
        0.0, 0.0, 1.0, 1.0,
        1.0, 1.0, 0.0, 1.0,
    )
    generated_material = _make_material_from_image(
        "Generated Material",
        generated,
    )
    _select_pair(
        generated_material,
        _make_color_material("Generated Color", (0.5, 0.5, 0.5, 1.0)),
        "Generated",
    )
    _configure_safe_input_case()
    generated_output = generated_dir / "output"
    generated_output.mkdir(exist_ok=True)
    assert bpy.ops.smc.combiner(directory=str(generated_output)) == {"FINISHED"}
    with PILImage.open(next(generated_output.glob("Atlas_*.png"))) as atlas:
        atlas_colors = set(atlas.getdata())
    assert {(255, 0, 0, 255), (0, 255, 0, 255)}.issubset(atlas_colors)
    checks["generated_pixels_used"] = True

    def assert_rejected(case_name, material, image):
        _select_pair(
            material,
            _make_color_material(f"{case_name} Color", (0.2, 0.3, 0.4, 1.0)),
            case_name,
        )
        _configure_safe_input_case()
        case_output = root / case_name / "output"
        case_output.mkdir(parents=True, exist_ok=True)
        assert bpy.ops.smc.combiner(directory=str(case_output)) == {"CANCELLED"}
        assert not list(case_output.glob("Atlas_*.png"))
        assert image.packed_file is None

    # A texture wired to a non-albedo shader input is ambiguous and rejected.
    _clear_data()
    unsupported_dir = root / "unsupported-shader"
    unsupported_dir.mkdir(parents=True, exist_ok=True)
    unsupported_path = unsupported_dir / "roughness.png"
    PILImage.new("RGBA", (2, 2), (100, 100, 100, 255)).save(unsupported_path)
    unsupported_material = _make_image_material(
        "Unsupported Shader",
        unsupported_path,
        pack=False,
        input_name="Roughness",
    )
    unsupported_image = next(
        node.image
        for node in unsupported_material.node_tree.nodes
        if node.bl_idname == "ShaderNodeTexImage"
    )
    assert_rejected(
        "unsupported-shader",
        unsupported_material,
        unsupported_image,
    )
    checks["unsupported_shader_rejected"] = True

    # A file that becomes truncated after Blender loads it is rejected on preflight.
    _clear_data()
    malformed_dir = root / "malformed"
    malformed_dir.mkdir(parents=True, exist_ok=True)
    malformed_path = malformed_dir / "malformed.png"
    PILImage.new("RGBA", (2, 2), (30, 60, 90, 255)).save(malformed_path)
    malformed_material = _make_image_material(
        "Malformed File",
        malformed_path,
        pack=False,
    )
    malformed_image = next(
        node.image
        for node in malformed_material.node_tree.nodes
        if node.bl_idname == "ShaderNodeTexImage"
    )
    malformed_path.write_bytes(b"\x89PNG\r\n\x1a\ntruncated")
    assert_rejected("malformed", malformed_material, malformed_image)
    checks["malformed_file_rejected"] = True

    # Float generated buffers are outside the safe-core input policy.
    _clear_data()
    float_image = bpy.data.images.new(
        "Float Generated",
        width=2,
        height=2,
        alpha=True,
        float_buffer=True,
    )
    float_material = _make_material_from_image("Float Material", float_image)
    assert_rejected("float-generated", float_material, float_image)
    checks["float_image_rejected"] = True

    # UDIM/tiled sources are rejected even when Blender can create them.
    _clear_data()
    tiled_image = bpy.data.images.new(
        "Tiled Source",
        width=2,
        height=2,
        tiled=True,
    )
    tiled_material = _make_material_from_image("Tiled Material", tiled_image)
    assert_rejected("tiled-source", tiled_material, tiled_image)
    checks["tiled_image_rejected"] = True

    # Exercise hard caps without allocating hostile-sized images.
    ops = importlib.import_module(
        f"{MODULE}.operators.combiner.combiner_ops"
    )
    images_module = importlib.import_module(f"{MODULE}.utils.images")
    try:
        images_module._validate_encoded_size(512 * 1024 * 1024 + 1)
    except ValueError:
        pass
    else:
        raise AssertionError("encoded byte limit was not enforced")
    try:
        ops.validate_resource_budget({}, (20_001, 20_001))
    except ValueError:
        pass
    else:
        raise AssertionError("atlas pixel limit was not enforced")
    synthetic_source = images_module.ImageInput(
        image=SimpleNamespace(size=(10_000, 10_000)),
        kind="GENERATED",
    )
    try:
        ops.validate_resource_budget(
            {"synthetic": {"gfx": {"source": synthetic_source}}},
            (20_000, 20_000),
        )
    except ValueError:
        pass
    else:
        raise AssertionError("working memory limit was not enforced")
    checks["resource_limits_enforced"] = True

    return checks


def _run_undo_repeatability_case() -> dict:
    """Verify one-step datablock undo while successful PNGs remain external."""
    objects = _build_fixture("undo-repeatability")
    scene = bpy.context.scene
    scene.smc_packer_type = "BINARY_TREE"
    scene.smc_size = "AUTO"
    scene.smc_crop = False
    scene.smc_pixel_art = True
    scene.smc_gaps = 0
    scene.smc_diffuse_size = 8
    bpy.context.preferences.edit.use_global_undo = True

    output = WORK / "undo-repeatability" / "output"
    output.mkdir(parents=True, exist_ok=True)
    object_names = [obj.name for obj in objects]
    before = {
        "slots": {
            obj.name: [material.name for material in obj.data.materials]
            for obj in objects
        },
        "uvs": {
            obj.name: [tuple(loop.uv) for loop in obj.data.uv_layers.active.data]
            for obj in objects
        },
        "materials": sorted(material.name for material in bpy.data.materials),
        "textures": sorted(texture.name for texture in bpy.data.textures),
        "images": sorted(image.name for image in bpy.data.images),
    }

    assert bpy.ops.ed.undo_push(message="Material Combiner test baseline") == {
        "FINISHED"
    }
    assert bpy.ops.smc.combiner(directory=str(output)) == {"FINISHED"}
    first_path = output / "Atlas_00001.png"
    assert first_path.is_file()
    first_hash = hashlib.sha256(first_path.read_bytes()).hexdigest()
    # Direct Python operator calls do not receive Blender's UI-managed undo
    # boundary, so mirror the boundary supplied to a bl_options={'UNDO'}
    # operator when invoked from the interface.
    assert bpy.ops.ed.undo_push(message="Material Combiner operation") == {
        "FINISHED"
    }

    assert bpy.ops.ed.undo() == {"FINISHED"}
    objects = [bpy.data.objects[name] for name in object_names]
    after_undo = {
        "slots": {
            obj.name: [material.name for material in obj.data.materials]
            for obj in objects
        },
        "uvs": {
            obj.name: [tuple(loop.uv) for loop in obj.data.uv_layers.active.data]
            for obj in objects
        },
        "materials": sorted(material.name for material in bpy.data.materials),
        "textures": sorted(texture.name for texture in bpy.data.textures),
        "images": sorted(image.name for image in bpy.data.images),
    }
    assert after_undo == before, {"before": before, "after": after_undo}
    assert first_path.is_file()
    assert hashlib.sha256(first_path.read_bytes()).hexdigest() == first_hash

    assert bpy.ops.smc.combiner(directory=str(output)) == {"FINISHED"}
    second_path = output / "Atlas_00002.png"
    assert second_path.is_file()
    assert hashlib.sha256(first_path.read_bytes()).hexdigest() == first_hash
    return {
        "single_undo_restored_datablocks": True,
        "png_retained_after_undo": first_path.name,
        "repeat_output": second_path.name,
        "first_output_not_overwritten": True,
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
        report["checks"]["input_sources"] = _run_input_source_cases()
        if os.environ.get("SMC_TEST_FOREGROUND") == "1":
            report["checks"]["undo_repeatability"] = (
                _run_undo_repeatability_case()
            )
        else:
            report["checks"]["undo_repeatability"] = (
                "requires foreground Blender context"
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
