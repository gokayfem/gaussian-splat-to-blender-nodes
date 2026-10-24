"""Scene scaffolding shared by the build and by per-group tests: path curves, light, world, camera, render setup.

Owned by the integrator. Groups never import this; only build scripts and tools do.
"""
import math
import bpy

FPS = 24


def reset():
    """Empty the file. This frees every datablock, including node groups built before it: call it first, then
    build groups (build-once caches from before a reset point at freed trees)."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = FPS
    sc.frame_start, sc.frame_end = 1, 481
    return sc


def path_curve(kind="reference", name="Street Path", sc=None):
    """A path curve in the XY plane. 'reference' is the gentle S-bend of the reference street; the others are
    transfer inputs used to show the graph working on new paths."""
    pts = {
        # ~110 H gently winding street, travel along +Y (bend amplitude from the vanishing-point drift)
        "reference": [(0, -6, 0), (0.6, 8, 0), (-0.9, 24, 0), (0.6, 42, 0), (-1.2, 62, 0), (0.8, 84, 0), (0, 104, 0)],
        "straight": [(0, -10, 0), (0, 50, 0)],
        "s_bend": [(0, -10, 0), (6, 8, 0), (-6, 26, 0), (4, 44, 0), (0, 60, 0)],
        "hill": [(0, -10, 0), (0, 10, 1.5), (2, 30, 4.0), (-1, 50, 4.5)],
        # inward spiral with ~15 H between turns so two rows of houses fit back to back
        "spiral": [((40 - 15 * a / (2 * math.pi)) * math.cos(a), (40 - 15 * a / (2 * math.pi)) * math.sin(a), 0)
                   for a in [i * 0.3 for i in range(38)]],
    }[kind]
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    sp = cu.splines.new("BEZIER")
    sp.bezier_points.add(len(pts) - 1)
    for bp, p in zip(sp.bezier_points, pts):
        bp.co = p
        bp.handle_left_type = bp.handle_right_type = "AUTO"
    ob = bpy.data.objects.new(name, cu)
    (sc or bpy.context.scene).collection.objects.link(ob)
    return ob


def holder(name, curve_obj, group, sc=None):
    """A mesh-less object carrying the Geometry Nodes modifier, with the path curve fed in through an Object
    Info node inside the top-level group (input socket 'Path')."""
    me = bpy.data.meshes.new(name)
    ob = bpy.data.objects.new(name, me)
    (sc or bpy.context.scene).collection.objects.link(ob)
    mod = ob.modifiers.new(group.name, "NODES")
    mod.node_group = group
    return ob, mod


def srgb(hexstr):
    h = hexstr.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


def light_world(sun_elev=30.0, sun_azim=145.0, strength=4.0, sun_color="#FFE2BC", sky_top="#9EC6D5",
                sky_horizon="#E0CFC1", sky_strength=1.0, haze=0.0, haze_color="#E0CFC1", sun_angle=2.0, sc=None):
    """Sun + gradient sky (+ optional uniform haze volume). sun_azim rotates the sun about Z: 180 = light
    travelling straight back toward a camera looking down +Y, 145 = from ahead and to the right."""
    sc = sc or bpy.context.scene
    sun = bpy.data.lights.new("Sun", "SUN")
    sun.energy = strength
    sun.angle = math.radians(sun_angle)
    sun.color = srgb(sun_color)
    ob = bpy.data.objects.new("Sun", sun)
    ob.rotation_euler = (math.radians(90 - sun_elev), 0, math.radians(sun_azim))
    sc.collection.objects.link(ob)
    w = bpy.data.worlds.new("Sky")
    w.use_nodes = True
    nt = w.node_tree
    bg = nt.nodes["Background"]
    grad = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    nt.links.new(grad.outputs["Generated"], sep.inputs[0])
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value, mr.inputs["From Max"].default_value = 0.0, 0.3
    nt.links.new(sep.outputs["Z"], mr.inputs["Value"])
    nt.links.new(mr.outputs[0], ramp.inputs[0])
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (*srgb(sky_horizon), 1)
    ramp.color_ramp.elements[1].color = (*srgb(sky_top), 1)
    nt.links.new(ramp.outputs[0], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = sky_strength
    if haze > 0:
        vol = nt.nodes.new("ShaderNodeVolumeScatter")
        vol.inputs["Color"].default_value = (*srgb(haze_color), 1)
        vol.inputs["Density"].default_value = haze
        nt.links.new(vol.outputs[0], nt.nodes["World Output"].inputs["Volume"])
    from nodekit.graph import layout
    layout(nt, None, nt.nodes.get("World Output"))
    sc.world = w
    return ob


def camera(name="Camera", lens=24.0, loc=(0, -8, 1.6), target=(0, 10, 1.2)):
    cam = bpy.data.cameras.new(name)
    cam.lens = lens
    cam.clip_end = 400
    ob = bpy.data.objects.new(name, cam)
    ob.location = loc
    bpy.context.scene.collection.objects.link(ob)
    t = bpy.data.objects.new(name + " Target", None)
    t.location = target
    bpy.context.scene.collection.objects.link(t)
    c = ob.constraints.new("TRACK_TO")
    c.target, c.track_axis, c.up_axis = t, "TRACK_NEGATIVE_Z", "UP_Y"
    bpy.context.scene.camera = ob
    return ob, t


def render_setup(width=1280, height=704, samples=16, engine="BLENDER_EEVEE", sc=None, look="None",
                 exposure=0.0, raytrace=True, glare=0.0):
    """EEVEE with ray-traced reflections/fast GI (warm bounce light into the shade), AgX, optional glare."""
    sc = sc or bpy.context.scene
    sc.render.engine = engine
    sc.render.resolution_x, sc.render.resolution_y = width, height
    sc.render.resolution_percentage = 100
    ee = sc.eevee
    ee.taa_render_samples = samples
    for attr, val in (("use_raytracing", raytrace), ("use_shadows", True), ("shadow_ray_count", 2),
                      ("shadow_step_count", 8), ("fast_gi_method", "GLOBAL_ILLUMINATION")):
        if hasattr(ee, attr):
            setattr(ee, attr, val)
    if hasattr(ee, "ray_tracing_options"):
        ee.ray_tracing_options.use_denoise = True
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = look if look == "None" else f"AgX - {look}"
    sc.view_settings.exposure = exposure
    sc.render.image_settings.file_format = "PNG"
    return sc


def post(sc=None, haze_color="#E8D2BE", haze_start=4.0, haze_depth=150.0, haze_amount=0.9, glare=0.25,
         sky_top="#9EC6D5", sky_horizon="#E8D2BE"):
    """Compositor 'SS Post <scene>': the film is transparent, so geometry carries its own antialiased alpha.
    Geometry is hazed toward the warm horizon colour by the Mist pass (premultiplied, so silhouettes never get
    halos), then laid over a sky gradient drawn by screen height (the follow camera is level), then a soft glow.
    The world shader still lights the scene; only the visible sky comes from here."""
    from nodekit.graph import Graph
    sc = sc or bpy.context.scene
    sc.render.film_transparent = True
    sc.view_layers[0].use_pass_mist = True
    w = sc.world
    w.mist_settings.start, w.mist_settings.depth, w.mist_settings.falloff = haze_start, haze_depth, "QUADRATIC"
    g = Graph(f"SS Post {sc.name}", kind="COMPOSITOR",
              description="Haze by mist depth on premultiplied geometry, over a screen-space sky gradient, glow")
    rl = g.node("CompositorNodeRLayers")
    rl.b.scene = sc

    def mix(fac, a, b, blend="MIX", label=None):
        m = g.node("ShaderNodeMix", label, props={"data_type": "RGBA", "blend_type": blend, "clamp_factor": True})
        g.connect(fac, m.i("Factor"))
        ins = [s for s in m.b.inputs if s.enabled and s.name in ("A", "B")]
        g.connect(a, ins[0])
        g.connect(b, ins[1])
        return [s for s in m.b.outputs if s.enabled][0]

    with g.frame("Haze: premultiplied geometry toward the horizon colour by mist depth"):
        f = g.math("MULTIPLY", rl["Mist"], haze_amount, label="Haze Amount")
        haze_premul = mix(1.0, (*srgb(haze_color), 1.0), rl["Alpha"], "MULTIPLY", label="Haze x Alpha")
        hazed_rgb = mix(f, rl["Image"], haze_premul, label="Hazed")
        # Mix also blends alpha; put the render's own antialiased alpha back
        hazed = g.node("CompositorNodeSetAlpha", Image=hazed_rgb, Alpha=rl["Alpha"])
        try:
            g.connect("Replace Alpha", hazed.i("Type"))
        except (KeyError, TypeError, ValueError):
            pass
    with g.frame("Sky: gradient by screen height, behind the geometry"):
        coords = g.node("CompositorNodeImageCoordinates", Image=rl["Image"])
        sep = g.separate(coords["Normalized"])
        t = g.map_range(sep["Y"], 0.5, 0.78, 0.0, 1.0, interp="SMOOTHSTEP", label="Height above horizon")
        sky = mix(t, (*srgb(sky_horizon), 1.0), (*srgb(sky_top), 1.0), label="Sky")
        over = g.node("CompositorNodeAlphaOver")
        ins = [s for s in over.b.inputs if s.enabled and s.type == "RGBA"]
        g.connect(sky, ins[0])
        g.connect(hazed.out, ins[1])
    out_img = over.out
    if glare > 0:
        with g.frame("Soft glow on bright lanterns and highlights"):
            gl = g.node("CompositorNodeGlare")
            g.connect(out_img, gl.i("Image"))
            for name, v in (("Type", "Fog Glow"), ("Quality", "Medium"), ("Strength", glare),
                            ("Threshold", 0.9)):
                try:
                    g.connect(v, gl.i(name))
                except (KeyError, TypeError, ValueError):
                    pass
            out_img = gl["Image"]
    g.output("Image", "COLOR", out_img)
    g.finish()
    sc.compositing_node_group = g.nt
    return g.nt


def ground(sc=None, size=600.0, color="#7E8A4E"):
    """A plain meadow under overview shots, so a street seen from above sits in a landscape, not a void.
    Not part of the generator; it only frames the transfer scenes."""
    from nodekit.materials import flat
    sc = sc or bpy.context.scene
    me = bpy.data.meshes.new(f"{sc.name} Ground")
    h = size / 2
    me.from_pydata([(-h, -h, -0.03), (h, -h, -0.03), (h, h, -0.03), (-h, h, -0.03)], [], [(0, 1, 2, 3)])
    me.materials.append(flat("SS Meadow", srgb(color), 0.95))
    ob = bpy.data.objects.new(f"{sc.name} Ground", me)
    sc.collection.objects.link(ob)
    return ob
