material-combiner-addon
===========

> **Originally created by [Grim-es](https://github.com/Grim-es/material-combiner-addon)** | **Previously maintained by [Team Neoneko](https://github.com/teamneoneko/material-combiner-addon)** | **Currently maintained by [Alrauna](https://github.com/Alrauna/material-combiner-addon)**

#### An add-on for Blender 5.2 LTS that helps reduce draw calls in game engines by combining textures without quality loss and avoiding issues with UV bounds larger than 0–1.

> **⚠️ Blender 5.2 LTS on Windows x64 only.** Other platform packages require native validation before they can be published.

> **Note:** This add-on is actively maintained, with focus on Blender 5.x. Earlier Blender versions are not supported.

## FEATURES

* **Combining Multiple Materials**: Allows you to mix diffuse colors with textures, and specify both the size of the
  resulting atlas and the size of each texture.
* **Multi-combining**: Adds image-layers for each material, which are combined into different atlases. This feature
  supports the generation of Normal maps, Specular maps, and other atlases. (Not implemented in newer versions |
  Supported in version 2.0.3.3)
* **UV Packing**: Packs UVs into the selected scale bounds by splitting mesh faces, and is compatible with rigged
  models. (Not implemented in newer versions | Supported in version 1.1.6.3)

## INSTALLATION

1. Download the latest release from the [Releases tab](https://github.com/Alrauna/material-combiner-addon/releases).
2. In Blender 5.2 LTS, go to Edit > Preferences > Extensions.
3. Click **Install from Disk**.
4. Select the downloaded `.zip` file.
5. Enable the Material Combiner extension.
6. Material Combiner includes its required Pillow dependency. Do not install
   Pillow with pip or modify Blender's bundled Python.

## HOW TO USE

1. Once the add-on is installed and activated, go to the 3D Viewport in Blender.
2. On the right side of the 3D View (Scene) window, open the side panel by pressing the `N` key on your keyboard.
3. In the side panel, locate the **MatCombiner** section.
4. You will see a list of objects and their corresponding materials:
    - For each material, you can choose to include or exclude it from the atlasing process by checking or unchecking the
      box next to it.
    - Each object has a **Select All** or **Deselect All** button, allowing you to quickly enable or disable atlasing
      for all of its materials.
5. You can also set the size for materials that do not have an image. The default size is set to 32 pixels.
6. Once you have made your selections, click the `Save atlas to..` button to start the atlasing process.
7. If the materials are not merged properly or the atlas image does not contain all the textures, please refer to the
   section:
   [After clicking "Save atlas to…" the materials are simply merged or the atlas image does not have all the textures](#after-clicking-save-atlas-to-the-materials-are-simply-merged-or-the-atlas-image-does-not-have-all-the-textures).

## KNOWN ISSUES

### After clicking "Save atlas to…" the materials are simply merged or the atlas image does not have all the textures

- Textures are packaged in a .blend file. Save the .blend file to a location of your choice, then go to File > External
  Data > Unpack Resources / Unpack All Into Files to extract the textures.
- Your version of Blender is not in English, in this case the nodes will be named differently, their names are strictly
  written in the script. You need to manually rename the nodes to their own names, or switch the blender version to
  English and regenerate the nodes by re-importing the model.
- You are using an unsupported shader (Surface property of material) or incorrect node names. You can check
  [addon/utils/materials.py](addon/utils/materials.py) to see which shaders are supported and what node names should be used. For
  more background, refer to the original discussion on GitHub:
  [Issue #98](https://github.com/Grim-es/material-combiner-addon/issues/98).
- If objects already share the same material with the same texture, they will not be atlased because they are already
  optimized, and the existing image will be used instead.

### Material Combiner dependency issue

Pillow is bundled in the complete platform package and is loaded through
Blender's extension system. Material Combiner never downloads or installs it
at runtime. Its provenance, license, and hash are recorded in
[addon/THIRD_PARTY.md](addon/THIRD_PARTY.md).

If the Dependency Status panel appears:

1. Copy the sanitized dependency diagnostics from the panel.
2. Remove unsupported source-folder installations.
3. Reinstall the complete Material Combiner package for Blender 5.2 and
   Windows x64 through **Preferences > Extensions > Install from Disk**.
4. Restart Blender only when the diagnostic specifically reports that a loaded
   native module is stale or cannot be replaced in the current process.

Do not run pip, add the normal Python user site, or modify Blender's bundled
Python to repair Material Combiner.

### No module named 'material-combiner-addon-2'

You have installed the source code instead of the packaged extension. Download the packaged `.zip` from the
[Releases tab](https://github.com/Alrauna/material-combiner-addon/releases) and install it through
**Preferences > Extensions > Install from Disk**. A source checkout does not include the bundled Pillow wheel and will
not work.

Before doing so, remove any old add-on installation folder. The default locations are:

* **Windows**
    ```console
    C:\Users\YourUserName\AppData\Roaming\Blender Foundation\Blender\BlenderVersion\scripts\addons
    ```
  Replace ***YourUserName*** with your actual username and ***BlenderVersion*** with the version of Blender you are
  using.
* **MacOS**
    ```console
    /Users/YourUserName/Library/Application Support/Blender/BlenderVersion/scripts/addons
    ```
  Replace ***YourUserName*** with your actual username and ***BlenderVersion*** with the version of Blender you are
  using.

## BUGS / SUGGESTIONS

If you have found a bug or have suggestions to improve the tool, please report them via:
- **GitHub Issues**: [Report an issue](https://github.com/Alrauna/material-combiner-addon/issues)
- **Discord**: Coming soon.
