"""Ground fields shared by the ground sub-groups: radial Fourier outlines, the fitted ground height and polylines.

All numbers come from data/params/ground.json (scripts/analyze_ground.py); the graphs only evaluate them.
"""
import math

from nodekit.graph import Graph, once

from garden.util import load_params

P = load_params("ground")


def chain(g, x, *ops):
    """Apply (op, operand) math steps to x in order: chain(g, x, ("MULTIPLY", 2), ("ADD", 1))."""
    for op, v in ops:
        x = g.math(op, x, v)
    return x


def smooth01(g, x, a, b):
    """Smoothstep from 0 at a to 1 at b."""
    return g.map_range(x, a, b, 0.0, 1.0, interp="SMOOTHSTEP")["Result"]


def _fourier(g, phi, coef):
    """a0 + sum_k (a_k cos k phi + b_k sin k phi), one Multiply-Add per term."""
    acc = g.value(coef[0], label="a0")
    for k in range(1, (len(coef) - 1) // 2 + 1):
        kphi = g.math("MULTIPLY", phi, float(k))
        acc = g.math("MULTIPLY_ADD", g.math("COSINE", kphi), coef[2 * k - 1], acc)
        acc = g.math("MULTIPLY_ADD", g.math("SINE", kphi), coef[2 * k], acc)
    return acc


def _radial_group(name, coef, what):
    g = Graph(name, description=f"Radial outline of the {what}: r(phi) = fitted Fourier series about the table "
                                f"centre; Margin > 0 inside")
    pos = g.input("Position", "VECTOR", (0.0, 0.0, 0.0), subtype="TRANSLATION",
                  desc="World position to test (Z ignored)")
    off = g.input("Offset", "FLOAT", 0.0, min=-5.0, max=5.0, subtype="DISTANCE",
                  desc="Grow (+) or shrink (-) the outline radially")
    with g.frame("Angle and radius of the position about the origin"):
        xyz = g.separate(pos)
        phi = g.math("ARCTAN2", xyz["Y"], xyz["X"])
        rho = g.vmath("LENGTH", g.combine(xyz["X"], xyz["Y"], 0.0))["Value"]
    with g.frame("Fitted Fourier series r(phi) plus Offset; Margin = r - rho"):
        r = g.math("ADD", _fourier(g, phi, coef), off)
        margin = g.math("SUBTRACT", r, rho)
    g.output("Radius", "FLOAT", r, desc="Outline radius in this direction")
    g.output("Margin", "FLOAT", margin, desc="Distance inside the outline along the ray (negative outside)")
    g.output("Angle", "FLOAT", phi, desc="Azimuth of the position (radians)")
    return g.finish()


@once
def paving_boundary():
    return _radial_group("Garden Ground Paving Boundary", P["paving"]["boundary_fourier"], "paved area")


@once
def lawn_outline():
    return _radial_group("Garden Ground Lawn Outline", P["lawn"]["outline_fourier"], "lawn")


def _box(g, a, b, ar, br, feather):
    """Soft 0..1 mask of the box ar x br in the (a, b) frame."""
    m = g.math("MULTIPLY", smooth01(g, a, ar[0] - feather, ar[0] + feather),
               smooth01(g, a, ar[1] + feather, ar[1] - feather))
    m = g.math("MULTIPLY", m, smooth01(g, b, br[0] - feather, br[0] + feather))
    return g.math("MULTIPLY", m, smooth01(g, b, br[1] + feather, br[1] - feather))


@once
def ground_height():
    """Ground height: paving level inside the paving, the fitted lawn plane outside, the raised bed terrace beyond
    the kerb (with the steps notch) and the shallow pond hole, in the structures' 18-degree garden frame."""
    pz = P["paving"]["level_z"]
    c0, c1, c2 = P["lawn"]["plane"]
    t = P["terrace"]
    th = math.radians(t["frame_deg"])
    g = Graph("Garden Ground Height", description="Fitted ground height: paving level, lawn plane (5th-percentile "
                                                  "splat heights), raised bed terrace with steps notch, pond hole")
    pos = g.input("Position", "VECTOR", (0.0, 0.0, 0.0), subtype="TRANSLATION", desc="World position (Z ignored)")
    soil = g.input("Lawn Soil Drop", "FLOAT", 0.025, min=0.0, max=0.2, subtype="DISTANCE",
                   desc="How far the lawn soil sits below the fitted grass-base plane")
    ramp = g.input("Edge Ramp", "FLOAT", 0.3, min=0.01, max=2.0, subtype="DISTANCE",
                   desc="Width over which the ground rises from the paving to the lawn")
    xyz = g.separate(pos)
    with g.frame("Lawn plane fitted to the 5th-percentile splat heights, minus the soil drop"):
        lawn = g.math("MULTIPLY_ADD", xyz["X"], c1, g.math("MULTIPLY_ADD", xyz["Y"], c2, c0))
        lawn = g.math("SUBTRACT", lawn, soil)
    with g.frame("Blend from paving level to lawn just outside the paving outline"):
        margin = g.group(paving_boundary(), Position=pos)["Margin"]
        w = smooth01(g, g.math("MULTIPLY", margin, -1.0), 0.28, g.math("ADD", ramp, 0.28))  # past the outer slabs
        z = g.mix(w, pz, lawn)["Result"]
    with g.frame("Garden frame: a = x cos + y sin, b = -x sin + y cos (18 degrees)"):
        fa = g.math("MULTIPLY_ADD", xyz["X"], math.cos(th), g.math("MULTIPLY", xyz["Y"], math.sin(th)))
        fb = g.math("MULTIPLY_ADD", xyz["X"], -math.sin(th), g.math("MULTIPLY", xyz["Y"], math.cos(th)))
    with g.frame("Terrace: kerb step at kerb_b, then a linear rise in -b, capped; notch kept low for the steps"):
        on = smooth01(g, fb, t["kerb_b"] + t["kerb_width"] * 0.5, t["kerb_b"] - t["kerb_width"] * 0.5)
        slope = (t["z_end"] - t["z_start"]) / (t["b_start"] - t["b_end"])
        tz = g.math("MULTIPLY_ADD", g.math("SUBTRACT", t["b_start"], fb), slope, t["z_start"])
        tz = g.math("MINIMUM", g.math("MAXIMUM", tz, t["z_start"]), t["z_max"])
        nt = t["notch"]
        notch = _box(g, fa, fb, nt["a"], nt["b"], nt["feather"])
        tz = g.mix(notch, tz, nt["z"])["Result"]
        z = g.mix(on, z, tz)["Result"]
    with g.frame("Pond hole: box lowered to the pond floor"):
        pd = t["pond"]
        pond = _box(g, fa, fb, pd["a"], pd["b"], pd["feather"])
        z = g.mix(pond, z, pd["floor_z"])["Result"]
    g.output("Height", "FLOAT", z, desc="Ground surface Z at this XY")
    g.output("Terrace", "FLOAT", on, desc="0 on the lawn side, 1 on the raised bed terrace")
    g.output("Paving Margin", "FLOAT", margin, desc="Distance inside the paving outline (negative outside)")
    g.output("Pond", "FLOAT", pond, desc="1 inside the pond hole")
    return g.finish()


def polyline(g, points, label):
    """A poly curve through fitted (x, y) points, built inside the graph (Mesh Line + Index Switch + Mesh to Curve)."""
    n = len(points)
    with g.frame(f"{label}: {n} fitted control points -> poly curve"):
        line = g.node("GeometryNodeMeshLine", props={"mode": "OFFSET"}, Count=n)
        sw = g.node("GeometryNodeIndexSwitch", props={"data_type": "VECTOR"})
        def socks():
            return [s for s in sw.b.inputs if s.enabled and s.type != "CUSTOM"]
        while len(socks()) - 1 < n:
            sw.b.index_switch_items.new()
        g.connect(g.node("GeometryNodeInputIndex"), socks()[0])
        for k, (x, y) in enumerate(points):
            socks()[k + 1].default_value = (x, y, 0.0)
        mesh = g.node("GeometryNodeSetPosition", Geometry=line["Mesh"], Position=sw["Output"])
        curve = g.node("GeometryNodeMeshToCurve", Mesh=mesh["Geometry"])
    return curve["Curve"]


def _poly(g, x, y, coef):
    """Cubic polynomial in (x, y) with terms 1, x, y, xx, xy, yy, xxx, xxy, xyy, yyy."""
    terms = [None, x, y, g.math("MULTIPLY", x, x), g.math("MULTIPLY", x, y), g.math("MULTIPLY", y, y)]
    terms += [g.math("MULTIPLY", terms[3], x), g.math("MULTIPLY", terms[3], y), g.math("MULTIPLY", terms[5], x),
              g.math("MULTIPLY", terms[5], y)]
    acc = g.value(coef[0], label="c0")
    for t, c in zip(terms[1:], coef[1:]):
        acc = g.math("MULTIPLY_ADD", t, c, acc)
    return acc


@once
def lawn_tone():
    tf = P["lawn"]["tone_field"]
    g = Graph("Garden Ground Lawn Tone", description="Fitted cubic fields over the lawn: brightness relative to the "
                                                     "lawn median and yellowness (dry grass), clamped")
    pos = g.input("Position", "VECTOR", (0.0, 0.0, 0.0), subtype="TRANSLATION", desc="World position")
    with g.frame("Scaled coordinates (x / 4, y / 4), clamped to the fitted region"):
        xyz = g.separate(pos)
        x = g.math("MINIMUM", g.math("MAXIMUM", g.math("DIVIDE", xyz["X"], tf["coord_scale"]), -1.5), 1.15)
        y = g.math("MINIMUM", g.math("MAXIMUM", g.math("DIVIDE", xyz["Y"], tf["coord_scale"]), -0.65), 1.05)
    with g.frame("Tone and dryness polynomials, clamped to plausible ranges"):
        tone = g.math("MINIMUM", g.math("MAXIMUM", _poly(g, x, y, tf["tone"]), 0.6), 1.3)
        dry = g.math("MINIMUM", g.math("MAXIMUM", _poly(g, x, y, tf["dry"]), -0.2), 0.3)
    g.output("Tone", "FLOAT", tone, desc="Brightness multiplier (1 = lawn median)")
    g.output("Dry", "FLOAT", dry, desc="Yellowness offset from the lawn median (positive = drier)")
    return g.finish()
