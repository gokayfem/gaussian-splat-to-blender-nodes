# Optional hybrid appearance mapping

Use this mode when the user wants captured appearance on reconstructed surfaces. The
procedural scene remains the geometric source. Selected surfaces become **baked evaluated
meshes with packed textures**, while untouched parts retain their original node graphs.
Keep the source blend and label that distinction. This is not automatic splat meshing,
material recovery or a texture that follows later Geometry Nodes edits.

## Contents

- [Inputs and configuration](#inputs-and-configuration)
- [Run the pipeline](#run-the-pipeline)
- [Visibility and fallback](#visibility-and-fallback)
- [Appearance and material slots](#appearance-and-material-slots)
- [Review and delivery](#review-and-delivery)

## Inputs and configuration

Start from [the hybrid prompt](../templates/prompts/hybrid-projection.md) and copy
[projection.json](../templates/projection.json) into the project. Its object name, cameras,
paths and distances are **illustrative values to replace**, not fitted defaults for a scene.
No Garden object list, coordinates, semantic labels, hue filters or texture files are built
into the tools.

Supply a saved reconstructed `.blend` and calibrated, opaque RGB sRGB PNG/JPEG captures from the
chosen reference renderer. Composite transparent captures deliberately before use; the
projector ignores alpha. Images must have the declared dimensions, with no lens distortion,
crop, camera shift or UI overlay. Cameras use world-space position/look_at/up, vertical FOV
in degrees, square pixels, and a top-left image origin. Register geometry in the same world
frame. The tools do not estimate poses or run a splat viewer. See
[whole-scene capture](whole-scene-capture.md).

Configure:

| Field | Meaning |
|---|---|
| `targets[].name` | Unique safe output stem |
| `object` / `object_id` | Exact reconstructed Blender object name / unique integer 1–32766 |
| `texture_size` | Square atlas size, 8–8192; start small and measure memory/time |
| `material_slots` | Optional selected **zero-based evaluated face material slots**; omitted means all |
| `uv_mode` | `unwrap` for a new smart unwrap; `existing` for an already valid nonoverlapping active UV map |
| `appearance` | `captured_radiance` (unlit) or `estimated_albedo` (approximate lit surface) |
| `views` | Named calibrated images and cameras; paths relative to the config file |
| `source_valid_masks` | Per-view mapping from target name to grayscale source mask; white allows that surface |
| `reference_collections` | Reference collections hidden during preparation/assembly; default `GS_REFERENCE` |

Targets are mesh objects, including generating GN mesh hosts. Instances are realized on a
copy; points/curves that do not evaluate to faces are not supported. Object transforms and
actual material-slot identities are preserved. A missing slot gets a neutral fallback without
renumbering faces. Existing non-node materials must be converted before preparation. Unwrapping adds a new
mapping UV layer; existing layers and the original render UV selection are preserved for
fallback shaders. Explicit mapping nodes use the new layer. Original fallback image
dependencies are resolved to their source paths; only new appearance/mix images are packed
automatically. Keep external fallback assets available or package them with the deliverable.

Tune distances to the project's units. `depth_absolute` is world-space tolerance;
`depth_relative` is dimensionless. `border` and `depth_erode` are pixel filter widths,
`mix_feather` is an atlas-pixel Gaussian sigma, and `padding` is atlas pixels. Optional
`resolution_cap` limits pixels per world unit and `edge_feather` fades camera-edge weights.
`min_cos` rejects grazing views; `vertical_min_cos` applies where `abs(normal.z) < 0.4`
in a Z-up Blender world. Leave these equal for orientation-independent weighting.
All these controls belong to the configuration, not scene-specific code.

## Run the pipeline

Use Python 3.10+ with `numpy`, `scipy` and `Pillow` (the repository's requirements include
them), and Blender 5.0+ with its bundled NumPy. Tested versions are recorded in the repository
validation notes. Run sequentially in disposable background processes; do not run scripts
against an unsaved interactive scene.

```sh
S=skills/gaussian-splat-to-blender-nodes

# Freeze geometry, bake world positions/normals/material IDs and scene visibility.
blender -b --factory-startup project/source.blend --python-exit-code 1 \
  --python "$S/scripts/projection_blender.py" -- prepare \
  --config project/mapping.json --out project/outputs/prepared-v01 --samples 32

# Project calibrated captures, reject contaminated samples, write textures + coverage.
python3 "$S/scripts/project_textures.py" \
  --config project/mapping.json --prepared project/outputs/prepared-v01 \
  --out project/outputs/mapped-v01

# Assemble packed appearance/mix images on copies with the original shaders as fallback.
blender -b --factory-startup project/source.blend --python-exit-code 1 \
  --python "$S/scripts/projection_blender.py" -- assemble \
  --config project/mapping.json --prepared project/outputs/prepared-v01 \
  --textures project/outputs/mapped-v01 --out project/outputs/hybrid-v01.blend
```

Each output must be new. Preparation fingerprints the config and source blend; projection
checks all prepared arrays and records capture/mask hashes; assembly verifies prepared and
mapped artifacts. Changing the config, geometry, materials, transforms or lighting means a
new prepared checkpoint. Unchanged captures may be reused. Reprojecting changed captures
requires a new mapped directory. Reports describe the files actually used, not a mutable
“latest” alias. Changing the source after assembly does not update the mapped copies.

CPU is the default. `prepare --device GPU` requires the user's existing Cycles device setup;
the tool does not alter device preferences. `--chunk-size` on the projector controls the
texel batch size, not the full cached capture/atlas memory. Visibility needs two renders per
view; each target needs three UV bakes, plus irradiance for estimated albedo. Pilot with a
small atlas and a few views before scaling.

## Visibility and fallback

Projection combines facing-angle/resolution weighting, reconstructed scene distance and
object-ID rejection, and conservative object boundaries. Only the first opaque reconstructed
surface is modeled by the visibility pass. Transparent/transmissive surfaces, volumes,
animation, view-dependent splat geometry and overlapping UVs need a separate validated
workflow; they are not solved here.

**Reconstructed depth cannot detect an occluder that exists only in the source capture.**
For example, if an unmodeled prop covers a surface in the scan, its pixels may be assigned
to that surface. Add per-target source masks, a better aligned reconstruction, or another
clean view. Masks use the same dimensions/camera as the capture. The allowed region is
shrunk to avoid bilinear sampling through rejected pixels.

When masks are impractical, `reject_rules` can explicitly reject samples in a bounded world
region. A rule requires `bounds_min` and `bounds_max` vectors, and optionally `rgb_min`,
`rgb_max`, `channel_ratios` (triples such as `["g", "r", 1.5]`) and
`min_sum` (`{"channels": ["g", "b"], "value": 0.5}`). Color values use sRGB 0–1.
Conditions within one rule are ANDed; multiple rules are ORed. An empty condition set rejects
the entire bounded region. These are **user-configured heuristics**, not segmentation.
Do not copy a study's hue/coordinate thresholds to another scene. Verify any such rejection
from a second view so legitimate surface color is not erased.

No acceptable sample means original-material fallback. The projector never copies nearby
captured color into unseen faces. Filtering uses real material IDs; padding affects only
pixels outside the selected UV surface. Keep adequate island spacing for the chosen padding
and texture filtering. Inspect mapping at normal size before chasing subpixel UV artifacts.

Coverage PNGs contain raw class values (0–4), so they look nearly black in an ordinary image
viewer; display them with discrete colors when diagnosing a visible defect. NumPy copies and
the legend are also saved:

| Value | Interpretation |
|---|---|
| 0 | Outside the selected UV surface |
| 1 | Direct accepted capture; edge texels may blend toward fallback |
| 2 | Geometrically visible candidate rejected by a mask/rule; fallback |
| 3 | No acceptable geometric visibility/facing sample; fallback |
| 4 | Padding outside the selected surface |

Percentages use selected valid UV texels, not scene area, image pixels or fidelity. The
`*_mix.png` image is the actual shader blend weight; class 1 alone does not imply 100% mix.

## Appearance and material slots

`weighted` averages in linear light. `robust` adds a diffuse-consensus heuristic that reduces
bright view outliers and rejects sufficiently dark outliers. It can still blur details or
choose the wrong view. `robust_q` controls that heuristic; it is not a measured quantile or
an image-quality score. Preserve actual face/material separation instead of inferring it
from “horizontal” or “vertical” normals.

`material_overrides` is keyed by actual slot index as a string. Supported values are
`robust_q`, `color_scale`, and, for estimated albedo, `roughness` and `specular`. Inspect
`prepared.json` to see the evaluated slot names. Configure any needed overrides, then
prepare a fresh checkpoint. Unselected slots retain their source materials.

- **Captured radiance:** emission avoids applying scene light a second time. Captured
  shadows/highlights remain fixed, and the mapped object can contribute emitted light in
  Cycles. This is an appearance display mode, not a relightable material.
- **Estimated albedo:** a white diffuse irradiance bake under the source scene's lighting
  divides out approximate illumination with a floor to limit shadow amplification. The
  captured image may include specular response, baked shadows and view dependence that this
  approximation cannot remove. It feeds a Principled shader and can still show double lighting.

Neither mode recovers physical albedo. Compare unlit/lit diagnostics when a broad brightness
mismatch appears; do not solve it by blindly increasing texture gains.

## Review and delivery

First inspect matched reference, procedural/clay and hybrid hero plus opposite/oblique views
at normal viewing size. Rank up to three material defects: wrong-object appearance on another
surface, broad ghosts/stretching, large color/material errors or materially missing coverage.
Use atlas/mask crops only to explain those defects. Separate geometry/camera mismatch from
projection errors, and plausible cast shadows from false textures. Rough source boundaries
and tiny seams alone need not block a scoped ready-for-review result.

Reopen the saved hybrid and verify packed images, intended UV map/slot wiring, hidden source
copies and fallback coverage. Audit live procedural collections separately:
`audit_blend.py` intentionally rejects baked hosts and is **not** a hybrid acceptance test.
The synthetic [integration procedure](../../../tests/README.md) tests the mapping pipeline
in a full repository checkout; a skill-only install does not include repository tests.
Remove reference data in a disposable copy and render representative views to establish
independence from the original scan; packed appearance remains intentionally derived from it.

Deliver exact source/config/texture/blend/report paths and hashes, matched views and the
editability contract. Record source permissions, unobserved surfaces and lighting limits.
A full 360° comparison must use the same poses and labels on all sides; do not synthesize
missing reference evidence. Package once major scoped mismatches are addressed instead of
running an unbounded edge-polish loop. The generalized implementation derives from the
c11b/c22s/c26b study, but it does not reproduce that fitted scene without its local inputs.
