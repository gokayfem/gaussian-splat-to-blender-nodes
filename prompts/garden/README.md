# Garden reconstruction study

An experimental native Blender reconstruction of the Garden reference. Visually incomplete;
useful as measured scene decomposition, not proof of automatic or perfect reconstruction.

## Build

From the repository root, with Blender 5.0+ (locally verified on 5.0.1):

```sh
blender -b --factory-startup --python-exit-code 1 \
  --python prompts/garden/build.py -- --out outputs/garden.blend

blender -b --factory-startup outputs/garden.blend --python-exit-code 1 \
  --python skills/gaussian-splat-to-blender-nodes/scripts/audit_blend.py -- \
  --out outputs/garden-audit.json
```

No scan download is needed. Top-level parts: `ground,table,vase,tree,shrubs,boundary,structures`.
Use `--parts table,vase` for an isolated test. `--dump outputs/garden-graph.json` exports graphs.
The builder refuses to save if a part fails or node validation reports warnings.

Render sequentially; full-scene rendering can be expensive:

```sh
blender -b --factory-startup outputs/garden.blend --python-exit-code 1 \
  --python skills/gaussian-splat-to-blender-nodes/scripts/render_manifest.py -- \
  --manifest prompts/garden/data/cameras_world.json --views hero,opposite \
  --out outputs/garden-views --samples 32
```

Use a fresh directory each time. `--engine CYCLES` uses CPU by default; configure supported
GPU devices explicitly for production. The legacy `--with-reference` overlay requires locally
prepared arrays under `outputs/derived`; those arrays and the historical analysis pipeline
are not distributed. The default build excludes that overlay.

## Editability

| Part | Construction |
|---|---|
| Ground | Slab layout, bevels, joints, litter, soil and lawn |
| Table | Radial planks, slate center, supports and materials |
| Vase | Asymmetric vessel, opening and dried botanical arrangement |
| Tree | Trunk/branches, forks, bark and canopy |
| Shrubs | Coarse density controls, branches and leaf instances |
| Boundary | Garden edges and surrounding geometry |
| Structures | Beds, pots, soil, stakes, seating and props |

`data/params/*.json` holds semantic parameters. Builders in `garden/parts` return Geometry
Node groups on empty mesh hosts; material builders create Shader Nodes. QA contains helper
controls used by some graphs: it is not the scan and must not be indiscriminately removed.
The sparse shrub density field is a fitted control, not the original Gaussian cloud.

`vendor/nodekit` and `vendor/library` are pinned copies from video-to-blender. The local
compatibility adapter supports Blender 5.0 modifier inputs. Later APIs may need adaptation.

## Cameras and provenance

`data/frame.json` defines the scan-to-world transform. Scale assumes a 0.74 m table height.
`data/cameras_world.json` contains hero, side/opposite, overview and detail views;
`data/reference_cameras.json` stores corresponding scan-space definitions. See [source.json](source.json).

The root gallery and linked video are historical **r011** artifacts. This source contains
later experimental edits and is not an exact pixel-reproduction recipe for those artifacts.
Publish fresh build/audit/render evidence when changing the example.

Remaining differences include foliage distribution and plant morphology, inferred hidden
surfaces, table/vase construction, paving wear and material/lighting response. Reference
quality varies with viewpoint. Structural independence does not resolve visual differences.

Scans, reference captures, private review/session histories, binary blends and decoded arrays
are outside this repository. Dataset terms are separate from the MIT code license.
