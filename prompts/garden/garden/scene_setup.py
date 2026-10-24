"""Collections, cameras, render settings and the GS_REFERENCE point cloud for the garden scene."""
import json

import bpy
import numpy as np
from mathutils import Matrix, Vector

from garden.util import ROOT

COLLECTIONS = ["GS_REFERENCE", "GARDEN_PROCEDURAL", "CAMERAS", "LIGHTING", "QA"]


def collections(sc):
    out = {}
    for name in COLLECTIONS:
        c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
        if c.name not in sc.collection.children:
            sc.collection.children.link(c)
        out[name] = c
    out["GS_REFERENCE"].hide_render = True
    out["QA"].hide_render = True
    return out


def camera_matrix(pos, look, up):
    p, t, u = Vector(pos), Vector(look), Vector(up)
    z = (p - t).normalized()
    x = u.cross(z).normalized()
    y = z.cross(x)
    m = Matrix.Identity(4)
    for i in range(3):
        m[i][0], m[i][1], m[i][2], m[i][3] = x[i], y[i], z[i], p[i]
    return m


def cameras(coll):
    data = json.load(open(ROOT / "data/cameras_world.json"))["world"]
    made = {}
    for name, c in data.items():
        cd = bpy.data.cameras.new("CAM_" + name)
        cd.sensor_fit = "VERTICAL"
        cd.angle_y = np.radians(c["fov_y_deg"])
        cd.clip_start, cd.clip_end = 0.05, 300
        ob = bpy.data.objects.new("CAM_" + name, cd)
        ob.matrix_world = camera_matrix(c["position"], c["look_at"], c["up"])
        ob["width"], ob["height"] = c["width"], c["height"]
        coll.objects.link(ob)
        made[name] = ob
    return made


def reference_cloud(coll, count=300000, seed=0):
    """Subsampled splat centres (world space, colour attribute) for A/B inspection; never rendered."""
    W = np.load(ROOT / "outputs/derived/world_pos.npy")
    rgba = np.load(ROOT / "outputs/derived/garden.npz")["rgba"]
    keep = np.nonzero((rgba[:, 3] > 120) & (np.abs(W).max(1) < 25))[0]
    idx = np.random.default_rng(seed).choice(keep, min(count, len(keep)), replace=False)
    me = bpy.data.meshes.new("GS_Reference_Points")
    me.vertices.add(len(idx))
    me.vertices.foreach_set("co", W[idx].ravel())
    col = me.color_attributes.new("splat_rgb", "FLOAT_COLOR", "POINT")
    c = np.c_[rgba[idx, :3] / 255.0, np.ones(len(idx))].astype(np.float32)
    col.data.foreach_set("color", c.ravel())
    ob = bpy.data.objects.new("GS_Reference_Points", me)
    ob.hide_render = True
    coll.objects.link(ob)
    return ob


def render_settings(sc, engine="BLENDER_EEVEE", samples=64):
    sc.render.engine = engine
    if engine == "CYCLES":
        sc.cycles.samples = samples
        sc.cycles.use_denoising = True
        sc.cycles.device = "CPU"  # Portable default; select a GPU explicitly for production.
    else:
        sc.eevee.taa_render_samples = samples
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    sc.render.film_transparent = False
    sc.render.image_settings.file_format = "PNG"
