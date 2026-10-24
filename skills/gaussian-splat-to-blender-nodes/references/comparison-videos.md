# Matched 360-degree comparison

Run from the repository root; substitute the installed Blender executable if needed.

```sh
S=skills/gaussian-splat-to-blender-nodes
python3 "$S/scripts/cameras.py" --frame prompts/garden/data/frame.json \
  --target 0 0 0.7 --radius 3 --elevation 30 --frames 240 --fps 24 \
  --width 640 --height 640 --out outputs/orbit.json

blender -b --factory-startup outputs/garden.blend --python-exit-code 1 \
  --python "$S/scripts/render_manifest.py" -- \
  --manifest outputs/orbit.json --out outputs/orbit-native --samples 32
```

This produces 240 poses at fixed distance/elevation. The closing pose is not duplicated.
The manifest's FPS defines duration; the Blender scene remains at its current frame.
This is a static-scene camera orbit, not animation evaluation.

Render the manifest's **scan** cameras in the reference viewer with exact position, target,
up, vertical FOV, dimensions and six-digit PNG filenames. Record quality, SH degree,
background and exposure. Disable auto-rotation and let the viewer settle. A universal
reference renderer/browser driver is not included.

Do not reframe either side, interpolate missing frames or approximate the reference orbit
by eye. With limited scan coverage, select and label a supported arc instead of claiming 360°.

```sh
python3 -m pip install -r requirements.txt
python3 "$S/scripts/compare.py" outputs/orbit-reference outputs/orbit-native \
  --out outputs/comparison --video --fps 24
```

Requires FFmpeg with libx264 on PATH. Output: H.264/yuv420p, CRF 18, faststart, no audio.
Pairing rejects missing names, inconsistent dimensions and existing output directories.
Labels occupy a separate 32-pixel strip. The encoder pads at most one pixel at the right
or bottom for even dimensions. It does not resize or auto-align the scene images.

`evidence.json` records input/output hashes, frame count and FPS. Equal image sizes do not
prove camera matching: verify manifests and landmark projections. Inspect quarter turns
and the seam for clipping, missing frames, labels and changing occlusion.

For a still pair, give two image files and omit `--video`.
