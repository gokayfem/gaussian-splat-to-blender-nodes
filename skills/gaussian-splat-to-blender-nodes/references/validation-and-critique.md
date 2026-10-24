# Validation and candid critique

## Evidence ladder

1. **Build:** exit status, parts, warnings and valid links.
2. **Native structure:** empty hosts, generating graphs, Shader Nodes and documented helpers.
3. **Independence:** delete GS_REFERENCE in memory and compare evaluated output; compare
   before/after beauty renders when render equivalence is required.
4. **Registration:** shared poses, FOV, dimensions and matching landmark projections.
5. **Fidelity:** whole-scene pairs, opposite/side views and native-resolution detail crops.
6. **Repeatability:** rebuild the source commit with identical parameters/seeds.

The audit checks the named procedural collection at the current frame. It hashes evaluated
mesh coordinates/topology, material assignments, instance geometry and transforms before
and after deleting reference objects. It checks empty hosts, enabled GN modifiers, warnings,
invalid links, material node trees and reference render hiding. Texture nodes and explicit
scan dependencies are reported for manual inspection. It never saves the blend.

It does not prove visual similarity or test shader/driver/compositor effects, animation,
external dependencies, all non-mesh geometry or pixel equality. Run it in a disposable
background process, never in the user's unsaved interactive scene.

For hybrid delivery, apply the native audit only to untouched live-GN collections. Verify
mapped baked copies separately: packed images, exact UV/material slots, original-material
fallback, source/config hashes and complementary rendered views. See
[hybrid projection](hybrid-projection.md). Captured textures are intentional in that mode;
unlit radiance and approximate albedo must be labeled, not treated as clean relightable data.

## Review record

Record UTC time, source commit, blend hash/mtime, render hashes, camera hash, engine,
samples, dimensions, color management and reference identity. State integrated/isolated,
clay/beauty scope. Keep outputs immutable.

Example:

> Observed: the hero's upper-right canopy is one opaque mass; the reference has three
> openings and visible branches. Adjust the clump envelope and measured gaps before
> increasing leaf density. Verify hero and right views plus the same foliage crop.
> Hypothesis: excessive sky fill may also flatten depth; test after geometry.

Rank up to three materially visible current mismatches; fewer or none is fine. Give region, evidence, correction and
verification view. Start with framing/silhouettes, then construction/occlusion, material/light
and detail. Preserve improvements; never repeat superseded defects. Avoid unsupported
similarity scores and generic praise. Rough source edges and minor seams alone do not
justify an unbounded polish loop; prioritize normal-size multi-view appearance.

No new render means no new visual finding. Record the blocker without inventing critique
or repeating requests already acknowledged. An agent's description is not image evidence.

## Completion and scope

Deliver editable source/blend, provenance, cameras, native audit, multi-view comparisons
and remaining limits. A beautiful generic scene is not close replication. Weakly captured
backside views expose coverage limits, not correctness.

Serialize expensive renders. Schedule recurring critique or message another agent only
with explicit authorization and correct session identity. Honor stops; never restart a
stopped reconstruction merely to write a report.
