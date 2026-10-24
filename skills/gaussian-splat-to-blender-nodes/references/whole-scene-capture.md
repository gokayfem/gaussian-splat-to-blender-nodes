# How the whole scene was captured for reconstruction

This describes **reference-view capture from an existing splat**, not photographic acquisition
or splat training. The study used the original asset as a stable measurement source and
captured several views of it. A hero screenshot alone did not describe the whole environment.

## 1. Select the scene and preserve its identity

The source-selection pass inspected real high-quality previews and distinguished a complex
environment from isolated assets. Once the user selected the scene, its viewer, model URL,
quality setting and approved screenshot became the reference contract. The exact downloaded
binary was preserved with byte size/hash, container version and available SH metadata.

For another project, use its already-selected asset if one exists. Otherwise compare scenes
on scope, coverage, visible geometry and usable source quality. More splats alone is not a
quality ranking. Verify a download is complete and actually a model, not an error document.
Keep the source unchanged; derived conversions get separate paths and provenance.

## 2. Reproduce the reference renderer before modeling

The study inspected the deployed viewer's asset and initial camera configuration, then
rendered the untouched asset in a local GaussianSplats3D viewer. Its adapter used explicit
position/target/up/FOV, a controlled canvas size and direct canvas PNG export. It disabled
built-in camera controls and progressive loading for that capture path. Both the deployed
and local reference images were inspected for alignment before trusting the local renderer.

Generalize the **contract**, not that viewer's API or version:

| Capture setting | What to record/control |
|---|---|
| Asset | Source hash, producer/container and conversion identity |
| Viewer | Renderer/library version, quality/LOD and SH degree |
| Camera | Position, target or rotation, up, vertical FOV, lens shift if present, clipping |
| Canvas | Pixel width/height, pixel ratio, aspect, viewport crop and principal point |
| Appearance | Background/alpha, exposure, output color space and tone mapping |
| Readiness | Asset loading complete, camera fixed, renderer/sort updated and output settled |
| Image | Camera ID, native dimensions, timestamp, file path and SHA-256 |

The original adapter repeatedly updated/rendered after each camera change before exporting
the canvas. That settling loop was a pragmatic implementation choice, not a universal timing
guarantee. A new adapter should use available load/sort completion signals, bounded waiting
and actual image checks. Record a timeout as a failed capture; do not accept a loading frame.

Capture the rendering canvas where the tool permits it, or use its supported screenshot
surface and account for the exact viewport. Do not include browser chrome, resize one side
independently, or mistake device pixels for CSS pixels. A browser UI that cannot expose exact
poses provides approximate registration; label that limitation rather than claiming a match.

Adapter pseudocode (a specification, **not** bundled executable functions):

```text
load_unchanged_asset_and_wait()
for view in shared_manifest.scan:
    set_canvas_dimensions_and_pixel_ratio(view)
    set_camera_position_target_up_and_vertical_fov(view)
    update_camera_matrices_and_projection()
    wait_for_loading_and_sorting_then_render_until_settled(timeout)
    export_reference_png(view.id)
    verify_dimensions_and_record_hash_settings_and_readiness(view.id)
```

## 3. Establish the shared world frame

The study decoded positions and attributes with the source format's conventions, filtered
candidate measurements by opacity, fitted a support plane, identified a stable central form,
and defined an origin/axes/scale. Top-down color and height maps and screen projections helped
locate surrounding objects. These were **analysis aids**, not replacement beauty renders.

Choose appropriate evidence for a new scene: floors/walls, surveyed anchors, a measured
dimension or known camera calibration. Plane fitting and robust shape fits can help; a lowest
point layer need not be a floor, and opacity thresholds are scene/format dependent. Check
outliers and uncertainty. State when metric scale is assumed rather than measured.

Store one proper scan-to-world transform and derive both renderers' cameras from it. See
[the coordinate conventions](acquisition-and-cameras.md). Keep all parts in that same frame.
When decoding, preserve attribute alignment, scale/opacity encodings and quaternion order;
a point projection is only a layout diagnostic and does not reproduce SH splat rendering.

## 4. Capture coverage, not just attractive angles

The initial study set contained a hero, opposite and side views, an elevated overview, a low
view and a focal detail. Later, matched close-ups targeted newly identified problems. Use
the following roles as a starting coverage plan, not a fixed required number of cameras:

| View role | What it reveals |
|---|---|
| Selected/hero | Composition, projected landmarks and the main silhouette |
| Opposite + lateral | Hidden supports, depth, overlap and missing surrounding context |
| Elevated/overview | Footprints, spacing, boundaries and repeated-layout structure |
| Low/grazing | Contact, thickness, joints, support geometry and shadow depth |
| Region close-ups | Meso/fine construction and material response at useful pixel scale |
| Wider context | Background planes, peripheral objects and scene extent |

Build an inventory across all views: foreground, middle ground, background, surfaces,
structural supports, repeated populations, secondary props and transitions. Record each
part's identifying features, coordinates/bounds, adjacency/occlusion and best verification
views. Include small context-defining objects; a screen-area cutoff must not silently drop
them. Mark regions as observed, partially observed or inferred.

Create a labeled contact sheet and add views where the inventory has gaps. “Whole scene”
means the requested environment and its visible relationships; a full orbit cannot recover
uncaptured surfaces or turn blurry background splats into known geometry.

## 5. Match the camera before critiquing reconstruction

Compare the local reference hero against the selected source view. Check several dispersed
landmarks, their distances/occlusions, crop and aspect; verify another view too. Preserve any
measured residual and its method. In the study this was a reference-versus-reference check,
**not** proof that the native reconstruction matched.

Lock the calibrated poses. Use exactly those world-space poses for Blender, with the same
projection and pixel dimensions. Record display transforms instead of assuming a particular
one is correct for every viewer. No independent zoom/crop or camera-specific object hiding
to make a comparison look closer. Fix material, light and geometry as separate variables.

## 6. Capture additional detail and the final orbit

For close-ups the study moved toward an observed region along a useful existing line of
sight and stored the resulting camera, target, FOV and resolution. Both renderers then used
that camera. This preserves familiar coverage better than freely orbiting into unseen sides,
but it still requires checking for newly exposed holes. Render close-ups at actual evaluation
resolution; enlarging a preview cannot reveal fine detail. Use identical pixel rectangles
for reference/previous/current crops and retain the uncropped frames.

For the comparison video, freeze a source checkpoint and share one orbit manifest between
reference and native renderers. Inspect cardinal views and coverage before rendering the
sequence. Record any start/end holds separately from unique camera poses. Keep frames paired
by camera ID, remove the scan from native beauty, serialize heavy rendering and inspect the
encoded output. See [the video procedure](comparison-videos.md).

The public toolkit provides fingerprinting, camera math, a native renderer, auditing and
pairing/encoding. It does **not** bundle the study's local viewer, automatic scene segmentation,
format decoder or a universal screenshot driver. The
[capture prompt](../templates/prompts/capture-and-registration.md) tells an agent what to
implement and prove with the tools available for a new project.
