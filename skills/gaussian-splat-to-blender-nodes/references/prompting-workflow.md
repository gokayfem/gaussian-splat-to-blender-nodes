# Prompt structure and handoffs

## Contents

- [Use the templates](#use-the-templates)
- [The actual structure behind the study](#the-actual-structure-behind-the-study)
- [Project inputs and artifacts](#project-inputs-and-artifacts)
- [Stage exits and scope](#stage-exits-and-scope)

## Use the templates

Start with [project-brief.md](../templates/prompts/project-brief.md). It contains the full
assignment, resource context, representation rules, sequence, review contract and delivery
bar. Send the narrower prompts only when their stage applies:

| Prompt | When to use it |
|---|---|
| [Capture and registration](../templates/prompts/capture-and-registration.md) | Source discovery or reference capture/calibration is incomplete |
| [Part contract](../templates/prompts/part-contract.md) | A component needs focused measurement/building under the shared scene contract |
| [Detail pass](../templates/prompts/detail-pass.md) | Complete composition exists but construction/material detail remains weak |
| [Review and correction](../templates/prompts/review-and-correction.md) | Fresh matched renders are ready for critique |
| [Hybrid appearance mapping](../templates/prompts/hybrid-projection.md) | Captured appearance is requested on selected reconstructed surfaces |
| [Comparison and delivery](../templates/prompts/comparison-and-delivery.md) | A frozen version needs final evidence or a comparison video |

Replace `{{...}}` placeholders with project values. Blank measurements mean **measure and
record uncertainty**, not fabricate values or stop at a questionnaire. Keep previous human
choices; an already-approved reference does not need another approval cycle. If the desired
scene has not been selected, collect candidates with actual previews and resolve that choice
before building the wrong subject.

## The actual structure behind the study

The original project used a short project instruction file pointing to a longer brief.
The brief defined the entire environment, source identity, known tool/API differences,
representation rules, measurement tasks, build sequence and live review outputs. A separate
part contract froze coordinates/cameras and assigned module ownership. A later detail brief
responded to inspected images, preserving earlier fixes while specifying construction and
surface corrections. Review messages named current artifacts and concrete verification views.

Reference capture was its own stage: a high-quality source was selected; the live viewer's
camera and asset were identified; a local viewer rendered the untouched asset from explicit
cameras; geometry analysis established a world frame and per-part parameters; reference
contact sheets and close-ups were supplied to the builder. See
[whole-scene capture](whole-scene-capture.md) for the method.

The final orbit used a frozen native checkpoint and one shared camera path for both renderers.
This prevents a long export from silently mixing versions. Several lessons are retained:
integrate all major parts early, judge detail at native resolution, preserve improvements,
serialize heavy renders and distinguish a working graph from a faithful image.

The generic templates preserve these contracts without carrying over the study's object
list, metric assumptions, exact view count, fixed iteration count, machine limits or blanket
recurring-review permission. They are suitable for environments, rooms, streets, machinery,
landscapes and object assemblies.

## Project inputs and artifacts

Fill the master brief with the project root/name/prefix, reference source, selected view,
whole-scene scope, must-keep elements, allowed omissions, Blender environment, output target
and resource budget. Scope is spatial and semantic: define the surrounding context as well
as the focal subject, and inventory small objects that materially establish identity.

Suggested **generated project** layout (these are output conventions, not files bundled for
every scene):

```text
project/
  PROJECT_BRIEF.md                filled master prompt
  docs/REFERENCE.md              inventory, source identity, coverage, uncertainty
  docs/COORDINATES.md            frame, units, cameras, display conventions
  docs/PART_CONTRACT.md          shared interfaces and ownership
  docs/DETAIL_PASS.md            current region-specific targets
  docs/review-log.md             timestamped evidence and corrections
  assets/source.json            provenance; original binary remains local
  data/frame.json                validated scan-to-world transform
  data/cameras.json              {world: {...}, scan: {...}} from one definition
  data/capture-manifest.json     image paths/hashes, camera IDs, viewer settings
  data/scene-inventory.json      parts, relations, coverage and confidence
  data/params/<part>.json        measurements and fitted controls
  scene/parts/<part>.py          project builders
  build.py                       integrated deterministic entry point
  outputs/reference/<view>.png   actual reference-render pixels
  outputs/derived/               local analysis, maps and decoder products
  outputs/checkpoints/<version>/ immutable blend, graph/audit and source identity
  outputs/review/<version>/      full comparisons, crops and status
  outputs/review/latest_status.json
```

Use project-relative artifact paths in prompts and reports. Include file hashes, camera IDs,
version and mtime in review evidence; avoid user-specific filesystem paths or session logs
in reusable/public prompts. Keep decoded attributes row-aligned with positions if analysis
uses them. A frame change invalidates derived positions, part fits and affected reference
captures; update those as one versioned change rather than letting parts drift independently.

`GS_REFERENCE` is the default reference collection used by the tools. Use
`SCENE_PROCEDURAL` as a generic native collection, or choose a project-specific name and
pass it explicitly to `audit_blend.py --collection ...`. The shipped Garden example's default
name is not a requirement for other projects. The build and capture adapters described by
these prompts must be implemented for the chosen project; the toolkit supplies only the
generic helpers documented in the README.

## Stage exits and scope

| Stage | Continue when | If evidence is insufficient |
|---|---|---|
| Source | Identity and selected scene are established | Resolve source/scope, not a procedural guess |
| Capture | Landmarks align; useful views cover the inventory | Add targeted views or record a coverage gap |
| Blockout | All major masses exist in one native scene | Integrate missing parts before polishing |
| Geometry/look | Same cameras show corrected structure/response | Change the highest-impact cause and verify again |
| Detail | Actual close-ups show the claimed feature | Correct form/scale; do not upscale a small preview |
| Delivery | Exact saved version has audit and visual evidence | Deliver as incomplete with explicit limits |

These are evidence checks, not mandatory human approval gates. Work through stages already
authorized by the user. Do not interpret “perfect replication” as a promise of an exact
inverse solution or an unbounded budget. Agree practical scope when necessary and report
uncertainty honestly. Optional part delegation and recurring external critique require their
own authorization; a single agent can perform every stage with the same contracts.
