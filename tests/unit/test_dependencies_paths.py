from __future__ import annotations

import importlib
import sys
import types
import unittest
from pathlib import Path


# dependencies.py imports bpy and uses a relative import, so load it through a
# synthetic package with bpy stubbed out.
sys.modules.setdefault("bpy", types.ModuleType("bpy"))
_package = types.ModuleType("smc_dependencies_host")
_package.__path__ = [str(Path(__file__).resolve().parents[2])]
sys.modules.setdefault("smc_dependencies_host", _package)
dependencies = importlib.import_module("smc_dependencies_host.dependencies")


@unittest.skipUnless(sys.platform == "win32", "Windows path semantics")
class ExtendedLengthPathTests(unittest.TestCase):
    """A long extension path must not be mistaken for an untrusted one.

    Blender reports PIL._imaging.__file__ in Windows extended-length form once
    the profile path is long enough, which previously made the dependency check
    report dependency_conflict for a healthy install.
    """

    def test_extended_length_path_is_inside_plain_root(self):
        self.assertTrue(
            dependencies._inside(
                Path(r"\\?\C:\profile\extensions\.local\PIL\_imaging.pyd"),
                Path(r"C:\profile\extensions"),
            )
        )

    def test_plain_path_is_inside_extended_length_root(self):
        self.assertTrue(
            dependencies._inside(
                Path(r"C:\profile\extensions\.local\PIL\_imaging.pyd"),
                Path(r"\\?\C:\profile\extensions"),
            )
        )

    def test_extended_length_unc_path_is_inside_plain_unc_root(self):
        self.assertTrue(
            dependencies._inside(
                Path(r"\\?\UNC\server\share\extensions\PIL\_imaging.pyd"),
                Path(r"\\server\share\extensions"),
            )
        )

    def test_unrelated_extended_length_path_is_outside(self):
        self.assertFalse(
            dependencies._inside(
                Path(r"\\?\C:\elsewhere\PIL\_imaging.pyd"),
                Path(r"C:\profile\extensions"),
            )
        )


if __name__ == "__main__":
    unittest.main()
