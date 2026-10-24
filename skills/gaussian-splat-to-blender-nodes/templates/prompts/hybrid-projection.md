# Prompt: project-independent hybrid appearance mapping

Use after a reconstructed scene and registered reference captures exist. Fill the project
inputs; retain decisions already established. This prompt authorizes only the work requested
by the user and does not schedule reviews or contact other sessions.

---

Use **gaussian-splat-to-blender-nodes** and read its hybrid-projection reference.

- Project: `{{PROJECT_ROOT_AND_NAME}}`
- Frozen reconstructed blend/source: `{{SOURCE_CHECKPOINT}}`
- Reference captures, provenance and calibrated cameras: `{{CAPTURE_PACKAGE}}`
- Selected reconstructed objects/materials: `{{TARGET_SCOPE_OR_INSPECT_AND_IDENTIFY}}`
- Appearance mode: `{{CAPTURED_RADIANCE_OR_ESTIMATED_ALBEDO}}`
- Intended viewing distance, output views and resource budget: `{{REVIEW_TARGET}}`

Add captured appearance to the selected reconstructed surfaces. Preserve the original
procedural source. Derive object names, material slots, coordinates, source masks, tolerances
and camera poses from this project. Do not copy another scene's object list, hue filters,
world-space rejection boxes, lighting gains or fitted camera path. The shipped projection
JSON is a configuration template, not a calibrated preset.

1. Inspect current source/config/report hashes and capture dimensions. Confirm one world
   frame, vertical FOV and identical source/reconstruction cameras. Inspect hero and
   opposite/oblique images before fitting any texture. Identify source-only occluders.
2. Configure evaluated mesh targets and actual face material slots. Keep meaningful object
   boundaries and the source Shader Node materials as fallback. Set source-valid masks for
   wrong-object pixels; use scoped color/region rejection only with visual evidence.
3. Run a small serialized prepare → project → assemble pilot with the supplied scripts.
   Use fresh versioned outputs. Do not launch competing expensive renders. Inspect actual
   appearance, mix and coverage artifacts; successful scripts and high coverage are not
   evidence of visual fidelity.
4. Compare matched reference/procedural/hybrid full frames at normal viewing size. Rank only
   material current mismatches, up to three: wrong-object projection, broad ghosts/stretches,
   large material/color errors and materially missing coverage. Preserve improvements.
   Separate geometry and camera errors from projection defects. Use crops/masks only when
   they explain a visible problem. Accept rough scan edges and minor seams unless they
   create conspicuous wrong-object appearance; do not optimize residuals for their own sake.
5. Correct the highest-impact cause and verify the same complementary views. Unseen or
   rejected samples must fall back to the source material, never inherit a neighbor's
   captured texture. Check material boundaries using actual face slots, not normal direction.
6. Reopen the packed hybrid file and verify UV/material wiring, source-copy visibility and
   fallback behavior. Audit untouched live GN collections separately. Report the selected
   surfaces as baked evaluated meshes: later geometry/UV/frame changes require rebaking.

Captured radiance includes shadows/highlights and is not clean albedo. Label the unlit mode
and any emitted-light effect. Treat irradiance-divided albedo as an approximation; inspect
lit views for baked lighting and double lighting. Do not claim universal relightability.

When no major defect remains in this scope, package the accepted result as ready for review
with exact artifact paths/hashes, source/coverage limitations and remaining visible
mismatches. Reuse current evidence and avoid duplicate renders. If a release comparison is
requested, include clearly labeled reference, clay/grey and hybrid views on one shared full
360° path; label unsupported coverage honestly. No claim of perfect replication from one
view, a coverage percentage or a passing script.
