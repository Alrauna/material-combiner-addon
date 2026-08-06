from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


PACKERS = (
    Path(__file__).resolve().parents[2] / "addon" / "utils" / "packers"
)


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, PACKERS / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


binary_tree = _load("smc_binary_tree", "binary_tree_bin_packer.py")
max_rects = _load("smc_max_rects", "max_rects_bin_packer.py")
rectpack = _load("smc_rectpack2d", "rectpack2D.py")


class PackerPlacementTests(unittest.TestCase):
    def assert_normalized(self, packed):
        for item in packed.values():
            fit = item["gfx"]["fit"]
            self.assertEqual(
                {"x", "y", "w", "h", "rotated"},
                set(fit),
            )
            self.assertGreater(fit["w"], 0)
            self.assertGreater(fit["h"], 0)
            self.assertGreaterEqual(fit["x"], 0)
            self.assertGreaterEqual(fit["y"], 0)

    def test_non_rotating_packers_report_normalized_fits(self):
        fixture = {
            "wide": {"gfx": {"size": (8, 2)}},
            "tall": {"gfx": {"size": (3, 7)}},
        }
        for packer in (
            binary_tree.BinaryTreeBinPacker(),
            max_rects.MaxRectsBinPacker(),
        ):
            with self.subTest(packer=type(packer).__name__):
                packed = packer.pack(
                    {
                        key: {"gfx": dict(value["gfx"])}
                        for key, value in fixture.items()
                    }
                )
                self.assert_normalized(packed)
                self.assertFalse(
                    any(item["gfx"]["fit"]["rotated"] for item in packed.values())
                )

    def test_rectpack_rotation_swaps_placement_dimensions(self):
        packed = rectpack.RectPack2D().pack(
            {
                "wide": {"gfx": {"size": (8, 2)}},
                "tall": {"gfx": {"size": (3, 7)}},
            }
        )
        self.assert_normalized(packed)
        wide = packed["wide"]["gfx"]["fit"]
        self.assertTrue(wide["rotated"])
        self.assertEqual((2, 8), (wide["w"], wide["h"]))


if __name__ == "__main__":
    unittest.main()
