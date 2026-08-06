"""Image handling utilities for Material Combiner.

This module provides functions for retrieving and managing images associated
with Blender textures and materials, including handling packed and unpacked images.
"""

import os
from dataclasses import dataclass
from typing import Optional

import bpy


MAX_SOURCE_PIXELS = 100_000_000
MAX_ENCODED_BYTES = 512 * 1024 * 1024
SUPPORTED_IMAGE_SOURCES = {"FILE", "GENERATED"}


@dataclass
class ImageInput:
    """A validated category of image input without changing its datablock."""

    image: bpy.types.Image
    kind: str
    path: Optional[str] = None
    packed_file: Optional[bpy.types.PackedFile] = None
    encoded_size: int = 0

    @property
    def size(self) -> tuple[int, int]:
        return int(self.image.size[0]), int(self.image.size[1])


def get_image(tex: bpy.types.Texture) -> Optional[bpy.types.Image]:
    """Extract image from a Blender texture.

    Args:
        tex: Blender texture object to extract image from.

    Returns:
        The image associated with the texture or None if not found.
    """
    return tex.image if tex and hasattr(tex, "image") and tex.image else None


def get_packed_file(
    image: Optional[bpy.types.Image],
) -> Optional[bpy.types.PackedFile]:
    """Return existing packed data without mutating the image datablock.

    Args:
        image: Blender image to get packed data from.

    Returns:
        The image's packed file data or None if unavailable.
    """
    return image.packed_file if image and image.packed_file else None


def get_image_input(image: Optional[bpy.types.Image]) -> Optional[ImageInput]:
    """Classify an atlas input and enforce non-decoding source limits."""
    if image is None:
        return None
    if image.is_float:
        raise ValueError("Float/HDR images are not supported")

    width, height = (int(value) for value in image.size)
    if width <= 0 or height <= 0:
        raise ValueError("Image dimensions must be positive")
    if width * height > MAX_SOURCE_PIXELS:
        raise ValueError(
            "Source image exceeds the {:,}-pixel limit".format(
                MAX_SOURCE_PIXELS
            )
        )

    if image.source not in SUPPORTED_IMAGE_SOURCES:
        raise ValueError(
            "Image source {} is not supported".format(image.source)
        )

    packed_file = get_packed_file(image)
    if packed_file is not None:
        encoded_size = int(packed_file.size)
        _validate_encoded_size(encoded_size)
        return ImageInput(
            image=image,
            kind="PACKED",
            packed_file=packed_file,
            encoded_size=encoded_size,
        )
    if image.source == "GENERATED":
        return ImageInput(image=image, kind="GENERATED")

    path = _get_image_path(image)
    if path is None:
        raise ValueError("Image file is missing or unsupported")
    encoded_size = os.path.getsize(path)
    _validate_encoded_size(encoded_size)
    return ImageInput(
        image=image,
        kind="FILE",
        path=path,
        encoded_size=encoded_size,
    )


def _validate_encoded_size(encoded_size: int) -> None:
    if encoded_size <= 0:
        raise ValueError("Image input is empty")
    if encoded_size > MAX_ENCODED_BYTES:
        raise ValueError(
            "Encoded image exceeds the {:,}-byte limit".format(
                MAX_ENCODED_BYTES
            )
        )


def _get_image_path(img: Optional[bpy.types.Image]) -> Optional[str]:
    """Get the absolute file path for an image.

    Resolves the absolute path and filters out unsupported special formats.

    Args:
        img: Blender image to get the path for.

    Returns:
        Absolute file path if valid, None otherwise.
    """
    if not img:
        return None

    path = os.path.abspath(bpy.path.abspath(img.filepath))
    if os.path.isfile(path) and not path.lower().endswith((".spa", ".sph")):
        return path
    return None
