# Prompt: frozen-checkpoint comparison and handoff

Use after the desired checkpoint is chosen. A comparison video can document an unfinished
scene; exporting it is not acceptance of the reconstruction.

---

Prepare the agreed deliverables for `{{PROJECT_NAME}}` from `{{CHECKPOINT}}`.
Requested media: `{{MATCHED_STILLS_DETAILS_AND_OPTIONAL_ORBIT_SPEC}}`.
Reference asset/camera package: `{{REFERENCE_PACKAGE}}`.
Destination: `{{LOCAL_OUTPUT_DIRECTORY}}`. Publishing/uploading is separate unless explicitly
included in the user's request.

Freeze the source/parameters, cameras and exact saved blend in an immutable checkpoint.
Record hashes, source identity, Blender version and render/color settings. Do not read a live
file that another build may overwrite midway through export. Keep review and media outputs
versioned so later corrections cannot silently replace the compared scene.

Audit that exact blend in a disposable process with the actual procedural collection name.
Check live GN generation, Shader Nodes, warnings/links and removal of `GS_REFERENCE`.
Preserve legitimate sparse QA helpers that are not the scan. If required, render before/after
scan removal too; a structural audit alone does not test every shader/compositor dependency.

## Matched stills and optional orbit

Render the agreed canonical views and detail crops from the frozen version. Pair them with
the same camera IDs, dimensions and projection in the reference renderer. Retain full frames,
label sources and report remaining mismatches.

If an orbit is requested, define one camera manifest: target, radius/path, height/elevation,
start azimuth, vertical FOV, image dimensions, unique pose count and FPS. A full 360° orbit
has no duplicated closing pose; any start/end holds are additional encoded frames and must
be documented. Do not change canonical review cameras to manufacture the export path.

Test several cardinal/important poses before the expensive run. Check reference coverage,
clipping, framing, occlusions and lighting at those angles. If a full orbit exposes unreliable
source regions, state the limitation; do not synthesize missing reference images or quietly
replace the requested comparison with a supported-looking carousel.

Render the same manifest on both sides, with the source removed from native beauty. Use the
project's shared render queue/lock; coordinate a temporary hold on other expensive project
renders when authorized. Never terminate unrelated jobs or delete their locks. Save frames
with stable matching IDs. Validate counts, dimensions and correspondence before encoding.

Use the bundled comparison tool or a documented equivalent. No independent crops/resizing,
interpolation to conceal missing poses, source swaps or camera-specific hiding. Label
reference/native and the checkpoint. Record output hash, codec, dimensions, FPS, unique poses,
encoded frames, duration and holds. Decode-check the movie and visually inspect cardinal
views, the seam and detail regions. Do not treat a successful encoder exit as visual QA.

## Final handoff

Provide source/build commands, parameters/presets, native blend, camera/frame/provenance,
actual validation results, control documentation, node screenshots and agreed media.
Reopen the saved deliverable; verify representative controls affect geometry/materials and
report any supported-range or resource limits.

Distinguish verified structural properties, inspected visual differences and untested claims.
Name remaining mismatches and uncertain/unseen surfaces. Avoid invented fidelity percentages
or “perfect replication.” Preserve the last working artifacts and honor any user stop;
completion of this export does not authorize restarting reconstruction or recurring review.
