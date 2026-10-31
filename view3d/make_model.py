"""Builds the 3D printers in Blender and converts them for Qt Quick 3D, one style each.

Run from the project folder (no style = all of them):
    "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b -P view3d/make_model.py
    "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b -P view3d/make_model.py -- hp_smart_tank_580

The printers are in view3d/printers/ (one module per family, see its STYLES) and are made
of the shared parts in view3d/parts.py. Each style is written to view3d/meshes/<style>/
*.mesh through pyside6-balsam. Only the geometry comes from here: colours, glass, ink and
pads are materials in the style's QML file (EpsonL3150.qml, HpSmartTank580.qml...). Units
are decimetres; the scene scales them. Blender is Z-up with the front of the printer
facing -Y; glTF turns that into Y-up with the front facing +Z.
"""
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bpy                      # noqa: E402

from parts import clear         # noqa: E402
from printers import STYLES     # noqa: E402

BALSAM = HERE.parent / ".venv" / "Lib" / "site-packages" / "PySide6" / "balsam.exe"


def export(style):
    """Build one style and write view3d/meshes/<style>/*.mesh."""
    clear()
    STYLES[style]()
    glb = HERE / f"{style}.glb"
    bpy.ops.export_scene.gltf(filepath=str(glb), export_format='GLB', export_yup=True,
                              export_normals=True, export_materials='NONE',
                              export_apply=True)
    print("written", glb)
    if not BALSAM.is_file():
        print("balsam.exe not found; run it on", glb.name, "by hand")
        return
    # balsam writes <out>/meshes/*.mesh plus a generic QML file we do not use
    tmp = HERE / f"_build_{style}"
    shutil.rmtree(tmp, ignore_errors=True)
    subprocess.run([str(BALSAM), "-o", str(tmp), str(glb)], check=True)
    dest = HERE / "meshes" / style
    shutil.rmtree(dest, ignore_errors=True)
    shutil.move(str(tmp / "meshes"), str(dest))
    shutil.rmtree(tmp, ignore_errors=True)
    glb.unlink()
    print("meshes ->", dest)


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    for style in args or list(STYLES):
        if style not in STYLES:
            raise SystemExit(f"unknown style {style!r}; known: {', '.join(STYLES)}")
        export(style)


if __name__ == "__main__":
    main()
