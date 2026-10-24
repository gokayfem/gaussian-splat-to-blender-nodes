# Master prompt: reconstruct a complete splat scene as native Blender nodes

Fill the known fields and send this whole prompt to the implementation agent. Replace
placeholders, or leave unknown measurements explicitly “to be measured.” This prompt works
with one agent. Companion prompts add detail at individual stages; they are not mandatory
separate agent sessions.

---

Use the **gaussian-splat-to-blender-nodes** skill. Read its `SKILL.md` and relevant capture,
construction and validation references before implementation.

## 1. Assignment and input context

- Project root/name: `{{PROJECT_ROOT}}` / `{{PROJECT_NAME}}`
- Node/material prefix: `{{PROJECT_PREFIX}}`
- Reference asset or viewer: `{{REFERENCE_SOURCE}}`
- Selected source image/view, if already established: `{{APPROVED_VIEW}}`
- Source selection status: `{{ALREADY_SELECTED_OR_NEEDS_SELECTION}}`
- Entire spatial/semantic scope: `{{WHOLE_SCENE_SCOPE}}`
- Must preserve: `{{IDENTITY_DEFINING_OBJECTS_RELATIONSHIPS_AND_QUALITIES}}`
- Explicitly allowed omissions: `{{ALLOWED_OMISSIONS_OR_NONE}}`
- Blender executable/version and available tools: `{{ENVIRONMENT_OR_DISCOVER_LOCALLY}}`
- Render/delivery target: `{{ENGINE_RESOLUTION_VIEWS_AND_OPTIONAL_VIDEO}}`
- Representation mode: `{{PROCEDURAL_DEFAULT_OR_EXPLICIT_HYBRID}}`
- Resource/time budget: `{{KNOWN_LIMITS_OR_MEASURE_AND_PROPOSE}}`
- Existing artifacts and current state: `{{START_FRESH_OR_CHECKPOINT_PATHS}}`

Deliver an actual editable `.blend` and reproducible builders. Reconstruct the full requested
environment and its relationships, not only the most prominent object. Derive the inventory
from the reference; do not replace it with a generic attractive scene. Aim for close,
multi-view visual resemblance and report the remaining differences honestly.

Respect decisions already made. Proceed with authorized analysis, construction, rendering
and correction. Resolve a genuinely missing source/scope choice before committing to the
wrong subject, but do not add another approval pause for an already-selected reference.

## 2. Inspect the source and tool environment

Identify the actual high-quality asset behind the reference, its provenance and usage terms.
Preserve the original binary. Record bytes, SHA-256, producer/container, compression and
available SH metadata. Validate that it downloaded completely. Do not reinterpret one splat
format as another. Use the producer's decoder or a validated conversion; document scale,
rotation, opacity and color encodings. The bundled inspector is not a semantic decoder.

Inspect the installed Blender version and relevant node/socket APIs. Use small executable
probes for uncertain capabilities and a project-local adapter where needed. Keep existing
applications and source assets intact. Reuse applicable node-building helpers, but native
Blender graphs are the deliverable; code or GLSL in text blocks is not a shader-node result.

## 3. Capture the whole scene before detailed modeling

Follow the capture-and-registration prompt. Reproduce the selected source view in an
appropriate reference renderer and save exact cameras. Capture a useful spread of views:
hero, opposite/lateral, elevated overview, low/contact and region details. Add wider context
or targeted views where coverage is missing. Do not infer the entire scene from one image.

Create `docs/REFERENCE.md` and `data/scene-inventory.json`. For each part/region record its
component construction, shape/proportion, bounds, adjacent surfaces, depth/occlusion,
material family, repeated-element distributions and best views. Include secondary props
and background structure that determine the scene's identity. Mark measured, estimated and
unseen/inferred features separately.

Establish `data/frame.json` and `docs/COORDINATES.md`: units, origin, axes, handedness, scale
assumptions and conversion. Derive reference and Blender poses from one `data/cameras.json`
with `world` and `scan` entries. Record vertical FOV, viewport dimensions, crop, clipping and
display settings. Validate dispersed landmarks and a second view, then lock the cameras.
Keep derived measurement arrays aligned and versioned with the frame/source.

## 4. Representation and editability contract

The following live-node rules govern procedural mode. If the selected mode is hybrid,
also follow the hybrid-projection prompt: captured appearance is allowed on explicitly
selected reconstructed mesh copies. Preserve source graphs, disclose baked copies and
rebake requirements, and audit procedural collections separately. Do not mislabel a hybrid
as wholly live/procedural. Objects, cameras, material slots and rejection rules must be
measured/configured for this project, never copied from the Garden study.

Separate `GS_REFERENCE`, `SCENE_PROCEDURAL`, `CAMERAS`, `LIGHTING` and `QA`, or document
equivalent names. Reference imagery and splats belong only in explicitly labeled comparisons.
The native beauty scene must survive removal of the source reference.

Use empty mesh hosts with live Geometry Nodes that generate the principal forms from
primitives, profiles, curves, structured parameters and spatial fields. Python may analyze
the scan, fit dimensions/curves, build graphs and orchestrate renders. A baked scan wrapped
in a pass-through modifier, splat instances or textured billboards do not meet this brief.
Sparse fitted helper data is acceptable when documented and independent of the original scan.

Use native procedural Shader Node materials responding to scene lighting. Captured colors
contain illumination and view dependence; they are not ground-truth albedo. Model openings,
gaps and relief when they change silhouette, parallax or shadow. Noise cannot replace form.

Store fitted values and uncertainty in `data/params/<part>.json`, separate from graph code.
Expose semantic controls with units, useful ranges, descriptions and stable seeds. Keep the
fitted preset as the default. Reuse instances for repeated components; realize only where
needed. Organize readable named groups and frames. Variation demonstrates editability but
does not replace the reference-matched scene.

## 5. Construction sequence

1. **Reference foundation:** establish source, frame, cameras, inventory and comparison
   setup. Produce a visible native checkpoint early; do not spend the entire task on tooling.
2. **Complete blockout:** place every major mass, surface, support and context layer. Render
   an integrated hero and complementary views before polishing one isolated asset.
3. **Geometry fidelity:** refine footprints, silhouettes, proportions, thickness, joints,
   openings, contacts, repeated layouts and occlusion. Verify against more than one view.
4. **Materials/light:** match display conventions; tune broad illumination, contact shadows,
   regional value/color and roughness/specular response. Use clay diagnostics to separate
   structural/light errors from material errors. Keep one coherent setup across views.
5. **Detail:** add evidenced meso-structure and then fine surface response. Evaluate at the
   intended pixel scale with matched close-ups, not enlarged low-resolution previews.
6. **Correction:** inspect reference/previous/current pairs; rank current mismatches, correct
   the highest-impact causes, and re-render the same views. Preserve successful changes.
7. **Delivery:** freeze the reviewed source/blend, audit native independence, inspect saved
   output and representative controls, and produce the agreed evidence and documentation.

Use part contracts to keep modules in the shared frame. One integrator owns cameras,
lighting, compatibility and official review artifacts. Work sequentially by default; use
parallel agents only if authorized. Serialize expensive renders and measure the machine's
resource cost before increasing resolution, density or samples.

## 6. Evidence and review while working

Preserve numbered immutable checkpoints and comparisons. Publish
`outputs/review/latest_status.json` only when it describes the actual artifacts. Include:
timestamp, stage, source/version, source and blend hashes, integrated/isolated scope,
reference/camera identities, actual render paths/settings, changes, known mismatches,
validation results and blocker. Before a render exists, say `render_available: false`.

Show labeled full-frame reference/native comparisons plus same-region detail crops. Include
the previous version for a correction pass. Do not crop away a mismatch. View the actual
images, not only a script's report. A structure audit is not visual acceptance.

For each correction report: **observed mismatch → geometric/shader/light change → what the
new image proves → what still differs → verification view**. Rank up to three materially visible current
deviations; fewer or none is fine. Accept rough source edges unless they materially harm
the intended view. Do not extend the task just to polish microscopic seams. Distinguish observations from hypotheses. Do not reuse critique against newer
artifacts without checking them, and do not treat an isolated part's omissions as absent
objects in the integrated scene.

Self-review at milestones. Recurring external review or messages to another agent are
optional and require explicit authorization; this brief does not schedule them. If a new
render is unavailable, record the state without inventing findings or duplicating an already
acknowledged checkpoint request. Honor user stop/pause instructions.

## 7. Acceptance and delivery

Deliver deterministic builders and parameters, the saved native blend, camera/frame and
provenance files, node/control documentation, actual audit results and agreed matched images.
Include an orbit comparison only when requested and supported by source coverage. Reopen
the saved version for inspection, report warning/link checks and test meaningful controls.

Verify GN hosts generate real geometry/instances and materials are editable Shader Nodes.
Run the native audit with the actual procedural collection name. If render independence
matters, compare before/after reference-removal beauty too; a stable geometry hash does not
cover shader, driver or compositor effects.

Success requires visible resemblance across the agreed views as well as structural validity.
Do not call the result perfect, complete or photorealistic because a script ran, a metric
improved or the object count increased. List remaining deviations, assumptions, unobserved
surfaces, performance limits and untested claims. If fidelity remains incomplete, label it
work in progress. Start with the source and complete-scene capture/calibration now.
