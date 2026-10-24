# Prompt: capture and measure the whole reference scene

Use after the project brief when source evidence or calibration is incomplete. This is
capture **from an existing splat**, not instructions to photograph or train a new dataset.

---

Prepare the reference package for `{{PROJECT_NAME}}` in `{{PROJECT_ROOT}}` from
`{{REFERENCE_SOURCE}}`, preserving the selected view `{{APPROVED_VIEW}}` and scope
`{{WHOLE_SCENE_SCOPE}}`. Read the project's brief and the skill's whole-scene capture guide.

## Source identity and selection

If a source is already selected, use it. Otherwise find high-quality scenes that actually
cover the requested environment; compare real previews, source availability and capture
coverage. Do not substitute isolated objects for a whole-scene request. Resolve the choice
with the user when it is not established.

Identify the actual model used by the selected viewer through supported inspection tools.
Acquire it where authorized, preserve an unchanged master and record URL/provenance, usage
terms, bytes/hash, producer, quality, compression and available SH metadata. A screenshot,
an incomplete download and an HTML error document are not usable 3D inputs.

## Reference-render adapter

Use an existing compatible viewer or implement a small project-local capture adapter if
needed. Pin and record its version. The public toolkit does not provide a universal viewer
or format decoder; do not claim otherwise. Prefer the real asset's original rendering
semantics over a center-point preview for final reference comparisons.

Discover and record camera position/rotation or target, up, vertical FOV, aspect, viewport,
principal point/lens shift, clipping, pixel ratio, quality/SH and color/tone-mapping settings.
Disable automatic camera motion for deterministic captures. Load the actual complete asset,
apply a saved pose, update projection/matrices, wait for rendering/sorting to settle within
a bounded timeout, then save the actual scene pixels. Inspect them for loading placeholders,
holes and cropping. Report unsupported controls honestly.

Export canvas PNGs when supported, or capture the supported rendering surface with exact
viewport bounds. Do not include browser chrome or independently resize reference images.
Record image dimensions, camera ID, settings, timestamp and hash in a capture manifest.

## World frame and measurements

Decode only through a format-correct implementation. Check coordinate conventions, linear
versus log scale, opacity versus logit, quaternion order and RGB/SH semantics. Keep original
attributes aligned with positions. Validate decoded structure and projected landmarks.

Fit a stable frame from appropriate scene anchors, planes or known dimensions. Reject
floaters/outliers with documented filters; do not copy another scene's numerical thresholds.
Store origin, proper rotation, positive scale, units and assumptions in `data/frame.json`.
If absolute scale is unknowable, label the chosen scale explicitly.

Where useful, create orthographic color/height/density maps and region-specific projections
for measuring footprints, levels, spacing and extents. These are diagnostic maps, not
reference beauty renders or final generated meshes. Record map bounds and pixel-to-world
conversion so measurements can be reproduced.

## View coverage and registration

Create one canonical camera definition with both world and scan poses. Match the selected
hero first; compare the local reference render against the selected source screenshot using
dispersed landmarks and exact crop/aspect. This is reference-versus-reference calibration,
not evidence of reconstruction quality. Verify a second view before locking the frame.

Build a useful coverage set: hero, opposite/lateral, elevated overview, low/contact views,
wider context and focal details. Choose counts and positions based on the scene's actual
visibility. Inspect every view; add targeted captures for important gaps and mark uncaptured
or degraded regions. A 360° orbit does not guarantee valid source coverage.

Inventory all major and identity-defining components, including supports, openings,
peripheral objects, repeated populations and transitions. Record subparts, bounds/proportions,
adjacency/occlusion, observed materials, distributions and confidence. Cross-check measurements
between views; flag disagreement instead of averaging incompatible observations away.

For close-ups, target a measured region along an already useful viewing direction when
possible, store the new pose/FOV/resolution, and render it on both sides. Verify that the
closer view still has reliable source coverage. Crops use the same pixel rectangle in both
images; enlarging a preview is not a new detail capture.

## Hand off evidence

Write source provenance, `docs/REFERENCE.md`, `docs/COORDINATES.md`, `data/frame.json`,
`data/cameras.json`, `data/capture-manifest.json`, `data/scene-inventory.json`, the actual
reference PNGs and a labeled contact sheet. Include uncertainty, source coverage limits,
calibration residuals with their method, and adapter/decoder commands that actually ran.

Keep the approved source immutable. Freeze the frame/cameras for builders and state which
outputs must be regenerated if calibration changes. Then continue the authorized integrated
blockout; do not remain indefinitely in infrastructure or claim capture is reconstruction.
