# Validation

## Python (CI)

```sh
python3 -m pip install -r requirements.txt
python3 -m unittest discover -s tests -v
python3 tests/check_repository.py
```

Tests exercise similarity-transform round trips, handedness, camera projection invariance,
orbit seams, malformed/truncated format headers, frame pairing and pixel preservation.
The repository check inspects tracked and non-ignored candidate files, Python syntax,
local Markdown links and packaging metadata. It is not a comprehensive secret scanner.

## Blender (local integration)

Run the starter build, audit and render commands in the root README. Then build the full
Garden example and audit it. Always use `--python-exit-code 1` and a disposable background
process. Run expensive jobs sequentially. Do not overwrite an existing checkpoint.

Inspect the rendered starter and a matched Garden checkpoint when changing appearance.
Run the negative audit regression suite:

```sh
blender -b --factory-startup --python-exit-code 1 --python tests/blender_audit_tests.py
```

It verifies reference deletion preserves independent geometry, rejects scan-dependent
Object Info geometry, and rejects a nonempty baked host carrying a GN modifier.

Use FFmpeg/ffprobe to test optional MP4 encoding and verify actual dimensions, duration,
FPS and frame count. CI does not install Blender or FFmpeg and makes no rendering claims.

The initial release was locally checked with Blender 5.0.1: starter and seven-part Garden
builds completed, node lint/warnings were empty, and both native audits passed. Garden had
92 Geometry Node groups and 59 Shader Node materials. These are structural observations,
not a visual fidelity score. Historical r011 gallery/video predates this source snapshot.
