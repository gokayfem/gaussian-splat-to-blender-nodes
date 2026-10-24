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

## Project-independent hybrid mapping

Python tests also cover linear-light interpolation, rigid camera transforms, object/depth
occlusion, source masks, bounded rejection, robust blending, material-slot feathering,
unseen fallback, irradiance requirements and immutable CLI fingerprints.

Run this synthetic two-view integration sequence with Blender 5.0+. It creates a transformed
GN box with multiple material slots, an independently mapped platform and an occluder.
These tiny synthetic reference renders test the pipeline, not scan fidelity. Use a fresh
output directory and execute each command only after the previous one succeeds.

```sh
S=skills/gaussian-splat-to-blender-nodes
T=outputs/projection-smoke
blender -b --factory-startup --python-exit-code 1 \
  --python tests/blender_projection_tests.py -- create --root "$T"
blender -b --factory-startup "$T/source.blend" --python-exit-code 1 \
  --python "$S/scripts/projection_blender.py" -- prepare \
  --config "$T/mapping.json" --out "$T/prepared" --samples 4
python3 "$S/scripts/project_textures.py" --config "$T/mapping.json" \
  --prepared "$T/prepared" --out "$T/mapped"
blender -b --factory-startup "$T/source.blend" --python-exit-code 1 \
  --python "$S/scripts/projection_blender.py" -- assemble \
  --config "$T/mapping.json" --prepared "$T/prepared" \
  --textures "$T/mapped" --out "$T/hybrid.blend"
blender -b --factory-startup "$T/hybrid.blend" --python-exit-code 1 \
  --python tests/blender_projection_tests.py -- verify --root "$T"
```

Verification checks negative world coordinates/normals, real material-slot IDs, foreground
occlusion IDs, coverage/fallback, preserved transforms/source graphs, packed images and
linked shader/UV inputs, realized GN instances and original relative texture dependencies.
Inspect `front.png`, `back.png`, `hybrid-front.png` and
`hybrid-back.png`. A synthetic pass does not validate arbitrary scene geometry, masks,
transparent surfaces or material recovery. Live-GN audits remain intentionally separate
from hybrid baked-copy checks.

The hybrid integration sequence was run locally with Blender **5.0.1**, including both
appearance modes and a source-relative fallback texture. Both saved-view renders were
inspected; the unchanged procedural starter also built and passed its native audit. This
validates the synthetic workflow, not a full rebuild of the fitted Garden release.
