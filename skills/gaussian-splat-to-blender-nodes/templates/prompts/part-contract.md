# Prompt: measured component contract

Use per part with one agent or, when explicitly authorized, with delegated workers. The
contract keeps every component compatible with one integrated scene; it does not itself
authorize spawning agents or contacting sessions.

---

Build/refine `{{PART_NAME}}` for `{{PROJECT_NAME}}`. Read `PROJECT_BRIEF.md`, the shared
coordinate/reference documents and the current review targets before editing.

## Fixed inputs and ownership

- Shared immutable inputs: `data/frame.json`, `data/cameras.json`, source identity and the
  reference captures listed in `data/capture-manifest.json`.
- Measurement inputs: `{{REGION_BOUNDS_DECODED_ARRAYS_MAPS_OR_LANDMARK_FILES}}`.
- Your files: `scene/parts/{{PART_ID}}.py`, optional `{{PART_ID}}_*.py` modules,
  `data/params/{{PART_ID}}.json` and part-specific analysis scripts.
- Shared framework owner: `{{INTEGRATOR_OR_THIS_AGENT_IN_INTEGRATOR_ROLE}}`.
- Required neighboring/context parts: `{{CONTEXT_PARTS}}`.
- Verification views/crops: `{{VIEW_IDS_AND_REGIONS}}`.
- Resource budget: `{{PART_BUDGET_BASED_ON_CURRENT_MACHINE}}`.

Do not independently change units, canonical cameras, shared light/color settings,
compatibility helpers, other parts or official integration outputs to improve your image.
Report a required framework correction to the integrator. If calibration changes centrally,
rebase your measurements onto the new version before proceeding.

## Build interface

Use the project's existing interface; if establishing one, use this simple contract:

```python
def materials():
    """Create/update this part's named native Shader Node materials."""

def build():
    """Return the part's top GeometryNodeTree; the integrator attaches it to an empty host."""
```

Keep host transforms and part-local/world-space placement consistent with the shared frame.
Prefix groups/materials `{{PROJECT_PREFIX}} {{PART_NAME}}`; preserve library namespaces.
Name/version any anchors or attributes consumed by neighboring parts. Store per-piece
variation once and pass it into shaders where useful. Document controls and fitted defaults.

## Measure, build and prove

1. Fit bounds, profiles, locations, counts/distributions and material observations from the
   supplied evidence. Record each measurement's method, source views and uncertainty in the
   part parameter JSON. Do not treat captured radiance as unlit material color.
2. Produce a complete coarse version of your part early. Include its supports, inner surfaces,
   openings and contact relationships visible in the reference, not just its obvious shell.
3. Generate actual geometry through nodes. Use instancing for repetitions and meaningful
   parameters/curves for structure. No baked scan or splat proxy in the beauty result.
4. Build the part, check warnings/links, render the locked verification views and inspect
   actual images. Include neighboring context where needed for scale/contact judgment.
5. Refine silhouette/proportion → distribution/occlusion → material/light response → detail.
   Use the scene's shared lighting; request a global lighting fix instead of compensating
   with a view-specific material hack.

Use distinct versioned directories under `outputs/parts/{{PART_ID}}/`. Preserve previous
evidence and label isolated/integrated scope. Follow the shared render queue/lock: no concurrent
heavy renders or deletion of another job's lock. Keep the module buildable between iterations.

Report: files/groups/controls changed; measurements; actual build/audit/render outcomes;
evidence paths with versions/hashes; remaining visible mismatches; framework requests.
An isolated part test proves only its stated scope. The integrator must still render and
review the whole scene before the part is accepted in context.
