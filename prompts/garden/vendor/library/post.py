"""Compositor node groups for the finishing pass. Render with a transparent film so geometry carries its own
antialiased (premultiplied) alpha, then haze it by depth and lay it over a sky drawn in screen space; EEVEE world
volumes swallow the sun, so distance haze belongs here. Use a group in the scene's compositor tree:

    sc.render.film_transparent = True
    sc.view_layers[0].use_pass_mist = True
    tree = bpy.data.node_groups.new("Post", "CompositorNodeTree"); sc.compositing_node_group = tree
    rl = tree.nodes.new("CompositorNodeRLayers"); gn = tree.nodes.new("CompositorNodeGroup")
    gn.node_tree = haze_over_sky(); link rl Image -> Image, rl Mist -> Mist, gn Image -> Group Output
"""
from nodekit.graph import Graph
from nodekit.library import nodegroup


def lin(hexstr, a=1.0):
    """'#RRGGBB' (sRGB) -> linear RGBA."""
    h = hexstr.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return (*[x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c], a)


def _doc(fn):
    return fn.__doc__.strip().split("\n\n")[0].replace("\n", " ")


def _mixc(g, fac, a, b, blend="MIX", label=None):
    n = g.node("ShaderNodeMix", label, props={"data_type": "RGBA", "blend_type": blend, "clamp_factor": True})
    return n.set(Factor=fac, A=a, B=b)["Result"]


@nodegroup("NK Haze Over Sky", kind="COMPOSITOR", tags=["compositor", "haze", "mist", "sky", "depth", "post"],
           use="street scenes, landscapes, cityscapes, aerial perspective, foggy mornings, stylised skies")
def haze_over_sky():
    """Distance haze by the Mist pass on premultiplied geometry, laid over a screen-space sky gradient.

    The haze colour is multiplied by the render's alpha before mixing, so antialiased silhouettes never pick up a
    halo; the Mix node also blends alpha, so the render's own alpha is put back before the geometry is laid over
    the sky. The sky runs from Sky Horizon at screen height Horizon to Sky Top at Top (0 = bottom, 1 = top).
    """
    g = Graph("NK Haze Over Sky", kind="COMPOSITOR", description=_doc(haze_over_sky))
    img = g.input("Image", "COLOR", (0.0, 0.0, 0.0, 0.0),
                  desc="Render with a transparent film (premultiplied colour and alpha)")
    mist = g.input("Mist", "FLOAT", 0.0, min=0.0, max=1.0, subtype="FACTOR",
                   desc="Mist pass (0 near, 1 at the mist distance); set its start and depth in World > Mist")
    haze_c = g.input("Haze Color", "COLOR", lin("#E8D2BE"), desc="Colour distant geometry fades toward")
    amount = g.input("Haze Amount", "FLOAT", 0.9, min=0.0, max=1.0, subtype="FACTOR",
                     desc="Haze at full mist depth")
    horizon_c = g.input("Sky Horizon", "COLOR", lin("#E8D2BE"), desc="Sky colour at the horizon")
    top_c = g.input("Sky Top", "COLOR", lin("#9EC6D5"), desc="Sky colour at the top")
    horizon = g.input("Horizon", "FLOAT", 0.5, min=-1.0, max=2.0, subtype="FACTOR",
                      desc="Screen height of the horizon (0 bottom, 1 top)")
    top = g.input("Top", "FLOAT", 0.78, min=-1.0, max=2.0, subtype="FACTOR",
                  desc="Screen height where the sky reaches Sky Top")
    with g.frame("Haze: mix toward Haze Color x alpha by mist depth (premultiplied)"):
        alpha = g.node("CompositorNodeSeparateColor", Image=img)["Alpha"]
        f = g.math("MULTIPLY", mist, amount, clamp=True)
        haze_pm = _mixc(g, 1.0, haze_c, g.node("CompositorNodeCombineColor", Red=alpha, Green=alpha, Blue=alpha,
                                                Alpha=1.0)["Image"], "MULTIPLY", label="Haze x Alpha")
        hazed_rgb = _mixc(g, f, img, haze_pm, label="Hazed")
        hazed = g.node("CompositorNodeSetAlpha", Image=hazed_rgb, Alpha=alpha, Type="Replace Alpha")
    with g.frame("Sky: smooth gradient by normalised screen height"):
        coords = g.node("CompositorNodeImageCoordinates", Image=img)
        y = g.separate(coords["Normalized"])["Y"]
        t = g.map_range(y, horizon, top, 0.0, 1.0, interp="SMOOTHSTEP", label="Height above horizon")
        sky = _mixc(g, t, horizon_c, top_c, label="Sky")
    with g.frame("Geometry over the sky"):
        over = g.node("CompositorNodeAlphaOver", Background=sky, Foreground=hazed["Image"])
    g.output("Image", "COLOR", over["Image"], desc="Hazed geometry over the sky (opaque)")
    g.output("Hazed", "COLOR", hazed["Image"], desc="Hazed geometry alone, premultiplied, with the render's alpha")
    g.output("Sky", "COLOR", sky, desc="The sky gradient alone")
    return g.finish()


@nodegroup("NK Soft Glow", kind="COMPOSITOR", tags=["compositor", "glow", "bloom", "glare", "post"],
           use="lanterns, street lights, candles, sunlit highlights, neon, magic effects, dreamy looks")
def soft_glow():
    """A soft bloom around bright pixels, tinted, added over the image.

    Pixels brighter than Threshold spread a wide, soft glow (Bloom glare) of Size, coloured by Tint and scaled by
    Strength; everything darker than Threshold is left untouched.
    """
    g = Graph("NK Soft Glow", kind="COMPOSITOR", description=_doc(soft_glow))
    img = g.input("Image", "COLOR", (0.0, 0.0, 0.0, 1.0), desc="Image to glow (linear, scene-referred)")
    thresh = g.input("Threshold", "FLOAT", 1.0, min=0.0, max=1000.0, desc="Brightness above which pixels glow")
    smooth = g.input("Smoothness", "FLOAT", 0.2, min=0.0, max=1.0, subtype="FACTOR",
                     desc="Soft knee around the threshold")
    strength = g.input("Strength", "FLOAT", 0.3, min=0.0, max=10.0, desc="Glow strength")
    size = g.input("Size", "FLOAT", 0.5, min=0.0, max=1.0, subtype="FACTOR",
                   desc="Glow radius as a share of the image size")
    tint = g.input("Tint", "COLOR", (1.0, 0.85, 0.7, 1.0), desc="Glow colour (warm by default)")
    with g.frame("Bloom of the pixels above the threshold"):
        gl = g.node("CompositorNodeGlare", Image=img, Type="Bloom", Quality="Medium", Threshold=thresh,
                    Smoothness=smooth, Strength=strength, Size=size, Tint=tint, Saturation=1.0)
    g.output("Image", "COLOR", gl["Image"], desc="Image with the glow added")
    g.output("Glow", "COLOR", gl["Glare"], desc="The glow alone")
    return g.finish()
