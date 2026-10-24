# Prompt: evidence-based visual review and correction

Use for self-review or an explicitly authorized reviewer. This template does not create an
automation, authorize contacting a session, or assume a fixed review interval.

---

Review `{{PROJECT_NAME}}` at `{{CHECKPOINT_OR_CURRENT_STATUS}}` against the selected reference.
The goal is resemblance of the entire requested scene through actual native Blender geometry
and materials. Be candid and specific; an attractive generic approximation is not acceptance.

## Establish what is current

Read the brief, frame/camera definitions, previous review and current status. Identify the
exact source commit/snapshot, blend, render/crop paths and reference captures. Record hashes,
mtime, camera IDs and render settings. State whether each image is integrated, isolated, clay
or beauty. Native evidence from an older blend does not automatically apply to a newer one.

Open the actual current matched images with image tools. Start with framing and landmarks,
then object silhouettes/proportions, placement and occlusion, missing components, construction,
material color/roughness/specular behavior, illumination/shadows and detail. Inspect opposite
or lateral views and close-ups, not just the hero. Separate source capture artifacts and
unseen areas from reconstruction defects.

If no new image exists, inspect status without inventing findings. Do not repeat an already
acknowledged critique or checkpoint request. Record the concrete blocker and next evidence
needed. If a newer image corrected a defect, preserve that improvement and remove the old
allegation. An isolated test's omitted context is not evidence that the integrated scene
lacks those objects.

For hybrid mode, inspect obvious wrong-object textures, broad projection ghosts/stretches,
large material/color errors and missing coverage first. Captured appearance is intentional.
Separate unlit radiance from approximate lit materials; neither is clean albedo. Use the
hybrid guide for baked-copy verification instead of requiring live GN on mapped surfaces.
Rough source edges and minor seams alone do not justify another polish loop.

## Report up to three materially visible current differences

Fewer or none is fine. Do not fill a quota.

For each finding provide:

1. **Evidence:** artifact/version, view and precise region or landmark.
2. **Observation:** the visible mismatch, phrased independently of a guessed cause.
3. **Priority:** why it materially affects the scene's identity or resemblance.
4. **Correction:** a concrete geometry, distribution, shader, light or registration change.
5. **Verification:** exact matched views/crops and what should visibly change.
6. **Confidence:** observed fact, hypothesis to test, or agent-reported/unverified claim.

Example structure, not a finding about this project:

> P1 — `{{CURRENT_IMAGE}}`, `{{VIEW}}`, `{{REGION}}`: the main assembly reads as one solid
> block while the reference exposes separate components and background gaps. Preserve the
> corrected outer dimensions; rebuild the measured internal separations before increasing
> surface texture. Verify `{{SECOND_VIEW}}` and the same native-resolution crop. Excess fill
> light might also reduce depth, but that is a separate hypothesis to test after geometry.

Check that native beauty excludes the scan and inspect the current native audit. Report what
was verified and what was not; geometry counts, correct average RGB, similarity diagnostics
and script success are not completion. A before/after render test is needed for claims of
pixel-level independence beyond the structural audit's scope.

## Correction handoff

Append a timestamped evidence entry to the review log and update the next correction targets.
Fix or request the highest-impact current correction within the agreed scope. Keep the
camera/frame and valid improvements fixed; re-render the verification views before accepting
the change. Use reference/previous/current sheets for detail comparisons.

If the user authorized feedback to a specific implementation session, identify that exact
session, send a concise actionable message through its normal channel, and verify delivery.
Queue appropriately if active; do not interrupt unrelated work. If idle and continued work
is authorized, ask it to resume the highest-priority correction. Otherwise keep the review
local. A user stop/pause overrides continuation; no timer or template grants new authority.

Report meaningful visual changes, failures, needed user action or verified delivery. Do not
fill unchanged review cycles with repeated critique. Keep the scene marked incomplete while
substantial visible differences remain.
