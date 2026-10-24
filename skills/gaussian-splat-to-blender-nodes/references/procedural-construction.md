# Procedural reconstruction patterns

| Subject | Construction | Verification |
|---|---|---|
| Round table | Radial plank wedges, separate slate disc, frame, braces and feet | Top, low side, rim crop |
| Irregular vase | Radius profile, azimuth deformation, thick rim and inner wall | Side silhouette and mouth |
| Dried arrangement | Stem hierarchy, broad fans, curled leaves and seedhead clusters | Hero outline, side and close-up |
| Tree | Measured branch paths, taper, continuous forks, bark displacement | Backlit outline, fork crop |
| Shrubs | Coarse occupancy controls, branches and oriented leaf families | Gaps, overlap and depth from two sides |
| Paving | Measured slab layout, bevels/chips, recessed joints and constrained litter | Overview and grazing close-up |
| Lawn/beds | Uneven density, blade clumps, bare patches and soil | Ground-level edge and overhead patches |
| Pots/structures | Profiles, lips, soil surfaces, supports, stakes and contents | Paired views with correct occlusion |

## Spatial frequencies

**Macro:** placement, silhouette, supports and canopy envelope.
**Meso:** joinery, plank gaps, vase mouth, leaves, forks, slab edges and soil clumps.
**Micro:** grain pores, scratches, roughness breakup and small bark fissures.

Use geometry when a feature changes silhouette, parallax or shadows. Shading can carry
small surface response. Micro-noise cannot compensate for absent meso-geometry. Fit
structure with curves/parameters, then use seeded randomness inside bounded distributions.

Do not make all foliage spheres or identical flat leaves. Use species-like profiles,
curl/thickness where visible, branch-scale clustering and coherent orientation. Preserve
negative spaces; indiscriminate density often makes matching worse.

## Materials and lighting

Splat appearance includes captured illumination and view dependence. Sampling it as albedo
then lighting it again can double shadows. Keep camera, color management and exposure fixed
while testing one variable at a time. Convert sRGB picks to linear shader values.

Use local coordinates for grain, bark and slate. Match grain direction and joint dirt before
adding noise. Tune roughness independently of color. Check wet highlights, metallic response,
black cavities and leaf translucency. Use neutral clay to isolate geometry/light errors.
Match key direction, sky fill and contact shadows before applying a global tint.

## Editability

Keep semantic JSON parameters, deterministic seeds, named groups and documented controls.
A sparse fitted occupancy field is useful; the full scan as a hidden geometry source is not
an independent reconstruction. Document required helper data.

Keep instances until needed. Zero evaluated mesh vertices on an instancer does not mean
empty output: inspect dependency-graph instances. A baked mesh with a pass-through GN
modifier is not a native procedural builder.
