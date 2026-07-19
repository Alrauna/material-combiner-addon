# Material Combiner compatibility tests

These tests preserve the public and behavioral contract characterized before
the Blender 5.2 implementation work began.

The tests must run with an isolated Blender profile. The PowerShell runner
creates that profile under a caller-provided temporary directory, copies the
working tree into an isolated extension repository, disables the normal Python
user site, and invokes Blender with factory startup and auto-execution disabled.

Example:

```powershell
.\tests\run_blender_tests.ps1 `
  -Blender "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" `
  -WorkDirectory "..\.codex-assessment\implementation\public-api" `
  -PillowRoot "..\.codex-assessment\blender-5.2\python-packages\Python313\site-packages"
```

The optional `PillowRoot` argument is only for the approved Stage 0 controlled
dependency path. Release-package tests must omit it and verify Blender's
extension-managed wheel path instead.

Use the runner's `-Foreground` switch only for tests that require Blender's UI
undo context, such as the atlas undo/repeatability checkpoint. The profile is
still isolated, but Blender briefly opens a foreground window. Ordinary tests
must remain in the default background mode.

`public_api_contract.json` is the compatibility gate for registered classes,
operators, RNA properties, CATS-facing Python symbols, naming behavior, and
saved-file identifiers. `stage0_behavior.json` records golden outputs and
confirmed historical defects. Corrected expectations belong in
`corrected_behavior.json`; retain the old evidence and add a regression test
for every corrected behavior.
