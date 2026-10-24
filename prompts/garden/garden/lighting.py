"""Garden lighting (owner: lighting/look agent): overcast daylight fitted to the Garden splat reference.

Model (all physically based, no grading):
  * Sky dome   R(dir) = sky_color * s * (h + (1-h) * z^g)  for z > 0, plus a broad "bright cloud" lobe toward
                the hidden sun (s_l * max(dir.d, 0)^n) and a ground-bounce colour below the horizon.
  * Soft sun   a Sun lamp with a very large angular diameter (diffuse sun behind cloud) from the same direction.
Strengths are *derived* from artist-facing fractions so that an unoccluded, upward-facing Lambertian surface of
base colour C renders at ~ key_level * C (display-linear). With key_level = 1.0 material agents can set base colours
straight from reference linear colours of open, top-lit surfaces.

Parameters: data/params/lighting.json (fitted reference preset). Variations: data/params/lighting_presets.json,
selected with env var GARDEN_LIGHT_PRESET=<name> (merged over the reference preset).
"""
import json
import math
import os

import bpy
import numpy as np

from garden.util import ROOT, load_params

DEFAULTS = dict(key_level=1.0, sun_fraction=0.30, lobe_fraction=0.12, horizon_ratio=0.75, zenith_gamma=0.6,
                lobe_exponent=4.0, sun_azimuth_deg=70.0, sun_elevation_deg=35.0, sun_angle_deg=60.0,
                sky_color=[1.0, 1.0, 0.95], sun_color=[1.0, 0.98, 0.94], ground_color=[0.20, 0.19, 0.11],
                camera_sky_gain=1.0, exposure=0.0, eevee=dict(raytracing=True, fast_gi=True, fast_gi_distance=1.2,
                                                              shadow_rays=2, shadow_steps=8, ao_quality=0.5))


def params():
    """Reference preset merged with an optional named variation preset (env GARDEN_LIGHT_PRESET)."""
    p = {**DEFAULTS, **{k: v for k, v in load_params("lighting").items() if not k.startswith("_")}}
    name = os.environ.get("GARDEN_LIGHT_PRESET", "").strip()
    if name and name != "reference":
        presets = json.load(open(ROOT / "data/params/lighting_presets.json"))
        if name not in presets:
            raise KeyError(f"GARDEN_LIGHT_PRESET={name!r} not in lighting_presets.json ({sorted(presets)})")
        p = {**p, **{k: v for k, v in presets[name].items() if not k.startswith("_")}}
    p["preset"] = name or "reference"
    return p


def sun_dir(p):
    az, el = math.radians(p["sun_azimuth_deg"]), math.radians(p["sun_elevation_deg"])
    return np.array([math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)])


def lobe_dir(p):
    """Bright-cloud lobe direction; defaults to the sun direction unless lobe_azimuth/elevation are set."""
    q = {"sun_azimuth_deg": p.get("lobe_azimuth_deg", p["sun_azimuth_deg"]),
         "sun_elevation_deg": p.get("lobe_elevation_deg", p["sun_elevation_deg"])}
    return sun_dir(q)


def unit_irradiances(p):
    """Horizontal irradiance / pi of the unit-strength dome and unit-strength lobe (deterministic quadrature)."""
    mu = (np.arange(256) + 0.5) / 256  # cos(theta) of upper hemisphere
    ph = (np.arange(512) + 0.5) / 512 * 2 * math.pi
    M, P = np.meshgrid(mu, ph, indexing="ij")
    st = np.sqrt(1 - M ** 2)
    dirs = np.stack([st * np.cos(P), st * np.sin(P), M], -1)
    w = M * (1 / 256) * (2 * math.pi / 512) / math.pi  # cos-weighted solid angle / pi
    h, g = p["horizon_ratio"], p["zenith_gamma"]
    dome = float(((h + (1 - h) * M ** g) * w).sum())
    lobe = float((np.maximum(dirs @ lobe_dir(p), 0) ** p["lobe_exponent"] * w).sum())
    return dome, lobe


def strengths(p):
    K, fs, fl = p["key_level"], p["sun_fraction"], p["lobe_fraction"]
    dome_u, lobe_u = unit_irradiances(p)
    return dict(dome=(1 - fs - fl) * K / dome_u, lobe=fl * K / lobe_u,
                sun=fs * K * math.pi / max(math.sin(math.radians(p["sun_elevation_deg"])), 0.05))


def _math(nt, op, a, b=None, loc=(0, 0), clamp=False):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation, n.use_clamp, n.location = op, clamp, loc
    for i, v in enumerate((a, b)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            n.inputs[i].default_value = v
        else:
            nt.links.new(v, n.inputs[i])
    return n.outputs[0]


def _rgb_scale(nt, color, factor, loc):
    n = nt.nodes.new("ShaderNodeVectorMath")
    n.operation, n.location = "SCALE", loc
    n.inputs[0].default_value = color
    nt.links.new(factor, n.inputs["Scale"])
    return n.outputs[0]


def build_world(p, s):
    """World shader: dome gradient + bright-cloud lobe + ground bounce; camera rays optionally rescaled."""
    w = bpy.data.worlds.get("Garden Sky") or bpy.data.worlds.new("Garden Sky")
    w.use_nodes = True
    w.sun_threshold = 1000.0  # never auto-extract a sun from the world; the explicit Sun lamp carries shadows
    nt = w.node_tree
    nt.nodes.clear()
    tc = nt.nodes.new("ShaderNodeTexCoord")
    tc.location = (-1400, 0)
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    sep.location = (-1200, 200)
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    z = sep.outputs["Z"]
    # dome: s * (h + (1-h) * max(z,0)^g)
    zp = _math(nt, "MAXIMUM", z, 0.0, (-1000, 300))
    zg = _math(nt, "POWER", zp, p["zenith_gamma"], (-850, 300))
    dome = _math(nt, "MULTIPLY_ADD", zg, 1 - p["horizon_ratio"], (-700, 300))
    dome.node.inputs[2].default_value = p["horizon_ratio"]
    dome = _math(nt, "MULTIPLY", dome, s["dome"], (-550, 300))
    # lobe: s_l * max(dot(dir, d), 0)^n
    dot = nt.nodes.new("ShaderNodeVectorMath")
    dot.operation, dot.location = "DOT_PRODUCT", (-1000, 0)
    nt.links.new(tc.outputs["Generated"], dot.inputs[0])
    dot.inputs[1].default_value = tuple(lobe_dir(p))
    lob = _math(nt, "MAXIMUM", dot.outputs["Value"], 0.0, (-850, 0))
    lob = _math(nt, "POWER", lob, p["lobe_exponent"], (-700, 0))
    lob = _math(nt, "MULTIPLY", lob, s["lobe"], (-550, 0))
    sky = nt.nodes.new("ShaderNodeVectorMath")
    sky.operation, sky.location = "ADD", (-300, 150)
    nt.links.new(_rgb_scale(nt, (*p["sky_color"],), dome, (-420, 300)), sky.inputs[0])
    nt.links.new(_rgb_scale(nt, (*p["sun_color"],), lob, (-420, 0)), sky.inputs[1])
    # horizon blend to ground bounce (soft over ~3 degrees)
    gfac = _math(nt, "MULTIPLY_ADD", z, 20.0, (-1000, -300), clamp=True)
    gfac.node.inputs[2].default_value = 0.5
    ground = tuple(c * p["key_level"] for c in p["ground_color"])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type, mix.location = "RGBA", (-120, 0)
    nt.links.new(gfac, mix.inputs["Factor"])
    mix.inputs["A"].default_value = (*ground, 1.0)
    nt.links.new(sky.outputs[0], mix.inputs["B"])
    # camera rays see the same radiance unless camera_sky_gain != 1 (kept 1.0 in the reference preset)
    lp = nt.nodes.new("ShaderNodeLightPath")
    lp.location = (-120, -300)
    gain = _math(nt, "MULTIPLY_ADD", lp.outputs["Is Camera Ray"], p["camera_sky_gain"] - 1.0, (60, -250))
    gain.node.inputs[2].default_value = 1.0
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.location = (240, 0)
    nt.links.new(mix.outputs["Result"], bg.inputs["Color"])
    nt.links.new(gain, bg.inputs["Strength"])
    out = nt.nodes.new("ShaderNodeOutputWorld")
    out.location = (440, 0)
    nt.links.new(bg.outputs[0], out.inputs["Surface"])
    return w


def eevee_settings(sc, e):
    """Soft contact occlusion in EEVEE: screen-space ray tracing + horizon-scan GI, soft jittered shadows."""
    ee = sc.eevee
    ee.use_shadows = True
    ee.shadow_ray_count = int(e["shadow_rays"])
    ee.shadow_step_count = int(e["shadow_steps"])
    ee.use_raytracing = bool(e["raytracing"])
    ee.ray_tracing_method = "SCREEN"
    ee.use_fast_gi = bool(e["fast_gi"])
    ee.fast_gi_method = "GLOBAL_ILLUMINATION"
    ee.fast_gi_distance = float(e["fast_gi_distance"])
    ee.fast_gi_quality = float(e["ao_quality"])


def setup(sc, coll):
    p = params()
    s = strengths(p)
    sc.world = build_world(p, s)
    sun = bpy.data.lights.get("Garden Sun") or bpy.data.lights.new("Garden Sun", "SUN")
    sun.energy = s["sun"]
    sun.angle = math.radians(p["sun_angle_deg"])
    sun.color = p["sun_color"]
    sun.use_shadow = True
    sun.use_shadow_jitter = True
    ob = bpy.data.objects.get("Garden Sun") or bpy.data.objects.new("Garden Sun", sun)
    ob.rotation_euler = (math.radians(90 - p["sun_elevation_deg"]), 0, math.radians(p["sun_azimuth_deg"] + 90))
    if ob.name not in coll.objects:
        coll.objects.link(ob)
    eevee_settings(sc, {**DEFAULTS["eevee"], **p.get("eevee", {})})
    sc.view_settings.exposure = p["exposure"]
    sc["garden_light_preset"] = p["preset"]
    sc["garden_light_strengths"] = json.dumps({k: round(v, 4) for k, v in s.items()})
    return ob
