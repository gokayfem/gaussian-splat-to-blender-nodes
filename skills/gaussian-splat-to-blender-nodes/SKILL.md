---
name: gaussian-splat-to-blender-nodes
description: Reconstruct Gaussian splat scenes as editable native Blender Geometry Nodes meshes and Shader Node materials. Use for splat-to-procedural reconstruction, matched-camera analysis, semantic scene decomposition, detailed environment recreation, native-scene audits, optional hybrid capture-texture mapping onto reconstructed surfaces, and reference-versus-Blender comparison videos. This is an agent-guided measured workflow, not automatic splat-to-mesh conversion.
license: MIT
---

# World to World Mapping — Gaussian Splat to Blender Nodes

Build an editable scene that explains the reference through geometry, materials and light.
Use the splat as measurement and visual evidence. Deliver native source, parameters and
honest multi-view comparisons. Default to procedural materials. When captured appearance is
requested, use the optional hybrid workflow below and disclose its baked-surface limits.

## Prompting a complete project

For a full-scene task, use the [prompting workflow](references/prompting-workflow.md) and
[master project brief](templates/prompts/project-brief.md). They supply the actual brief,
capture, part-contract, detail, review and delivery prompt structure with project-specific
values left to measure. Read [whole-scene capture](references/whole-scene-capture.md) when
building the reference package: it explains the source-viewer, camera, coverage and close-up
capture procedure. These prompts work with one agent; delegation and recurring review are
optional, separately authorized modes.

## Start from evidence

1. Inspect current artifact versions and preserve user work.
2. Record asset URL, author/dataset, usage terms, byte size and SHA-256. Viewer software
   licensing does not establish dataset rights. Keep scans and decoded arrays local.
3. Identify the actual container and producer. `scripts/inspect_asset.py` fingerprints
   assets and reads limited metadata; it does not decode Gaussians into surfaces.
4. Establish one scan-to-world transform, scale, handedness and camera convention. Save
   position, target, up, vertical FOV and dimensions. Register stable landmarks first.
5. Read [acquisition and cameras](references/acquisition-and-cameras.md).

## Reconstruct coarse to fine

1. List major objects and occlusions. Separate measurements, estimates and invented hidden
   surfaces. Prioritize silhouette and spatial relationships.
2. Create collections: `GS_REFERENCE` (hidden from rendering), `SCENE_PROCEDURAL` (or a
   project-specific equivalent), `CAMERAS`, `LIGHTING`, and `QA`.
3. Use empty mesh hosts with live GN modifiers. Build meaningful primitives, profiles,
   curves, branches and instances. Document fitted control points. Instancing every
   Gaussian as the beauty scene is not procedural reconstruction.
4. Expose semantic controls with units, bounds and descriptions. Seed stochastic placement.
   Organize substantial graphs into documented subgroups and labeled frames.
5. Use Shader Nodes with part-local coordinates and physical feature scales. Splat color
   contains illumination; it is not automatically material albedo.
6. Produce an integrated matched-camera checkpoint before adding expensive detail.
7. Read [procedural construction](references/procedural-construction.md). Build joints,
   thickness, bevels, apertures, branch hierarchy and edge wear before micro-noise.

## Detail without inventing fidelity

More polygons, random noise or instances do not establish similarity. Require visible
meso-detail at the intended distance and fine detail in native-resolution crops. Preserve
improvements in newer versions. Omissions in isolated part tests are not missing integrated
objects.

Inspect the current project's identity-defining features and intended viewing scale. Rough
source edges and tiny seams need not block a ready-for-review result. Prioritize visible
structure, material assignment and multi-view fidelity over numerical residuals.

## Optional hybrid captured appearance

When the requested mode includes captured textures, read
[hybrid projection](references/hybrid-projection.md) and use the
[hybrid prompt](templates/prompts/hybrid-projection.md) with
[projection.json](templates/projection.json). Prepare reconstructed UV mesh copies in
Blender, project registered captures with depth/object/source-mask rejection, then assemble
packed appearance/mix images with original-material fallback. Per-project configuration
supplies all objects, material slots, cameras, world bounds and rejection rules.

Mapped copies are baked evaluated meshes, not live generated GN hosts. Preserve the source
and rebake after geometry/UV/frame changes. Captured radiance is an unlit appearance mode;
irradiance-divided albedo is only an approximation. Check wrong-object appearance, broad
ghosts/stretching, large color mismatch and missing coverage in full matched views. Rank
up to three current material issues; fewer or none is fine. Do not import another scene's
thresholds or restart edge polishing without a materially visible defect.

## Verify what actually exists

1. Build with `--python-exit-code 1`. Fail on missing parts, node warnings and invalid links.
2. Run `scripts/audit_blend.py` in a disposable background process. It removes the scan
   in memory and compares evaluated mesh/instance signatures. It never saves the blend.
   Apply it to live procedural collections; it intentionally rejects baked hybrid hosts.
   Verify hybrid packed images, UV/slot wiring, fallback and complementary renders separately.
3. Render with the reference removed. Inspect clay and beauty views, opposite/side/overview
   cameras and detail crops. Both renderers must use one shared camera manifest.
4. Record exact source/output hashes. An audit of an old blend does not validate a new one.
5. Read [validation and critique](references/validation-and-critique.md). Rank up to three
   materially visible differences with region, correction and verification view. Separate
   actual observations, hypotheses and agent-reported metrics.
6. If pixel-level independence matters, compare renders before/after scan removal too.
   The structural audit does not test shader, driver or compositor side effects.

## Compare stills and motion

`scripts/cameras.py` produces world/scan orbit poses. Render `world` poses with
`scripts/render_manifest.py`; render `scan` poses in the chosen reference viewer. The
reference side is viewer-specific and is not automated here.

`scripts/compare.py` pairs images and optionally encodes an MP4 with FFmpeg. See
[comparison videos](references/comparison-videos.md). Preserve framing and source labels.
Never invent missing reference angles. Serialize expensive renders and use immutable outputs.

## Tools and delivery

Resolve paths relative to this skill directory. Test Blender without a scan using
`templates/starter.py`. Basic helpers use the standard library; comparisons need Pillow,
and hybrid projection needs NumPy, SciPy and Pillow. MP4 encoding requires FFmpeg/libx264.
Blender tools target 5.0+; report the version actually tested.

Deliver the editable blend, deterministic source/parameters, camera manifests, provenance,
audit JSON and comparisons. Report remaining mismatches and unsupported views. Do not
promise perfect reconstruction or declare completion from script success.

The full repository includes an experimental `prompts/garden` builder and pinned nodekit
from `gokayfem/video-to-blender`. A skill-only install contains the portable tools and starter;
clone the repository for Garden.

Do not schedule reviews, contact other agents, publish assets or start API jobs implicitly.
Honor user authorization and stop queued work when asked to stop.
