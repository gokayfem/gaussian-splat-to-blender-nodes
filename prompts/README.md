# Prompting a whole-scene reconstruction

The working prompt structure is **a project brief + a shared evidence package + scoped
part contracts + repeated visual correction**. A single “make this in Blender” prompt
misses the camera calibration, scene coverage and integration work that make the result
resemble its reference.

These templates generalize the briefs, capture setup, part contracts, detail instructions
and review loop used in the Garden study. They are rewritten for any scene, not a verbatim
chat export. The procedural Garden builder remains an unfinished example; documenting its method does not imply
that it achieved exact replication. Private messages and session identities are not included.

## Start here

1. Copy the [project brief](../skills/gaussian-splat-to-blender-nodes/templates/prompts/project-brief.md)
   into your agent. Fill in the reference, full-scene scope and environment; let the agent
   measure values you do not know. This is the main prompt.
2. Use [capture and registration](../skills/gaussian-splat-to-blender-nodes/templates/prompts/capture-and-registration.md)
   to turn the existing splat into repeatable whole-scene evidence before detailed modeling.
3. Use the [part contract](../skills/gaussian-splat-to-blender-nodes/templates/prompts/part-contract.md)
   for each substantial component. It works with one agent; delegation is optional.
4. Send the [detail pass](../skills/gaussian-splat-to-blender-nodes/templates/prompts/detail-pass.md)
   once an integrated blockout exists, and the [review prompt](../skills/gaussian-splat-to-blender-nodes/templates/prompts/review-and-correction.md)
   at each new visual checkpoint.
5. For captured textures, use [hybrid projection](../skills/gaussian-splat-to-blender-nodes/templates/prompts/hybrid-projection.md)
   after registration and reconstruction. Its objects, materials, masks and rejection rules
   come from this project. Mapped surfaces are baked copies with procedural fallback.
6. Finish with [comparison and delivery](../skills/gaussian-splat-to-blender-nodes/templates/prompts/comparison-and-delivery.md).

Read [the prompting workflow](../skills/gaussian-splat-to-blender-nodes/references/prompting-workflow.md)
for the handoffs and artifact layout, and
[how we captured the whole scene](../skills/gaussian-splat-to-blender-nodes/references/whole-scene-capture.md)
for the actual capture method and its project-independent adaptation.

## The prompt anatomy

| Layer | What it pins down | Evidence needed before the next stage |
|---|---|---|
| Assignment | Whole environment, fidelity target, editable native output | Approved or already-selected source and scope |
| Reference/resources | Asset identity, viewer, original screenshot, tool versions | Valid local asset and provenance |
| Capture/calibration | World frame, exact cameras, view coverage, measured inventory | Reference contact sheet and registration check |
| Representation | GN-generated meshes, Shader Nodes, removable reference | Coarse integrated scene plus structural audit |
| Part contracts | Shared inputs, ownership, interfaces and verification views | Isolated evidence labeled with its scope |
| Integration | Every major component, consistent light and coordinate frame | Whole-scene pairs from locked cameras |
| Detail/critique | Observed mismatch → change → new evidence → remaining error | Reference/previous/current crops and multi-view checks |
| Delivery | Frozen snapshot, repeatable source and honest remaining limits | Native audit, matched views and optional orbit video |

“Capture” here means rendering and measuring views of an **existing Gaussian splat**.
It does not mean taking source photographs, running SfM or training a new splat. The local
reference-viewer adapter used in the study is not shipped as a universal capture tool.

The detailed prompts live inside the skill directory so a skill-only installation retains
them. [Garden](garden/README.md) is the concrete implementation example, not a required scene
layout, object list, camera path, color transform or resource budget.
