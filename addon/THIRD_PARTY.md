# Third-party software

## Pillow

Material Combiner packages Pillow for image decoding, resizing, composition,
and PNG output.

- Project: Pillow
- Version: 12.3.0
- Upstream release: https://pypi.org/project/pillow/12.3.0/
- License expression: MIT-CMU
- Python/ABI tag: CPython 3.13 / CPython 3.13

One reviewed wheel is packaged per supported platform.

Windows x64:

- Wheel: `pillow-12.3.0-cp313-cp313-win_amd64.whl`
- Wheel SHA-256:
  `1cca606cd25738df4ed873d5ad46bbdb3d83b5cbca291f6b4ff13a4df6b0bbe8`
- License file SHA-256:
  `4f7866a74802c6326f81faff59a56546b6aec2b10b91973e0e9308de95e79857`

Linux x64:

- Wheel:
  `pillow-12.3.0-cp313-cp313-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl`
- Wheel SHA-256:
  `0847a763afefb695bc912d7c131e7e0632d4edc1d8698f58ddabec8e46b8b6d3`
- License file SHA-256:
  `dda12a98c1979cf3d94df1cff45d27a4cb3f04a60c76f76902ac54cac03ec0ce`

macOS arm64:

- Wheel: `pillow-12.3.0-cp313-cp313-macosx_11_0_arm64.whl`
- Wheel SHA-256:
  `d69141514cc30b774ceea5e3ed3a6635c8d8a96edf664689b890f4089111fb35`
- License file SHA-256:
  `dda12a98c1979cf3d94df1cff45d27a4cb3f04a60c76f76902ac54cac03ec0ce`

There is no macOS Intel wheel because Blender 5.2 ships no macOS Intel build.

The two license files differ because each wheel bundles the notices of the
native libraries built into it. Both are covered by the same MIT-CMU
expression.

The official wheel is retained byte-for-byte, including its license material
and CycloneDX software bill of materials. Pillow is distributed under its own
terms and is not relicensed under Material Combiner's package license.

The dependency provenance and hash are also recorded in
`addon/dependencies.lock.json`. The wheel must be revalidated and its security
advisories reviewed before every release.
