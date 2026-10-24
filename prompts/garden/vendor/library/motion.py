"""Analytic animation as fields of a `Time` input (seconds): closed forms, not simulation zones, so any frame can
be evaluated on its own, scrubbed, rendered out of order or looped. Springs, a gait step, travelling wind gusts,
pendulum sway, time remaps and light flicker. Feed `Time` from Scene Time in the top-level modifier group only."""
import math
from nodekit.graph import Graph
from nodekit.library import nodegroup

TAU = 2.0 * math.pi


# ---- small node idioms (python helpers, not groups) ------------------------------------------------------------
def _chain(g, *ops):
    """Left-fold: _chain(g, a, ("MULTIPLY", b), ("ADD", c)) = a * b + c."""
    v = ops[0]
    for op, b in ops[1:]:
        v = g.math(op, v, b)
    return v


def _clamp(g, x, lo, hi):
    return g.math("MINIMUM", g.math("MAXIMUM", x, lo), hi)


def _smoothstep(g, e0, e1, x):
    return g.map_range(x, e0, e1, 0.0, 1.0, interp="SMOOTHSTEP")


def _doc(fn):
    return fn.__doc__.strip().split("\n\n")[0].replace("\n", " ")


# ---- groups ----------------------------------------------------------------------------------------------------
@nodegroup("NK Damped Spring", tags=["motion", "spring", "secondary", "oscillator", "animation"],
           use="ear flaps, scarves, satchels, antennae, hanging signs, tails, anything that bounces after a "
               "body or settles after a jolt")
def damped_spring():
    """A damped spring's steady response to a periodic drive (gain and phase lag) and its step response.

    Periodic: a part driven at Drive Frequency answers with Amplitude * Gain * cos(2 pi f t + Phase - Lag), where
    r = f / fn, Gain = 1 / sqrt((1 - r^2)^2 + (2 zeta r)^2) and Lag = atan2(2 zeta r, 1 - r^2): amplified near
    resonance, lagging behind the drive. Step: the exact response of x'' + 2 zeta wn x' + wn^2 x = wn^2 A to a step
    at Step Start (underdamped, critical and overdamped), which settles to Amplitude.
    """
    g = Graph("NK Damped Spring", description=_doc(damped_spring))
    t = g.input("Time", "FLOAT", 0.0, subtype="TIME_ABSOLUTE", desc="Time in seconds (field)")
    fd = g.input("Drive Frequency", "FLOAT", 1.0, min=0.0, max=50.0,
                 desc="Frequency of the periodic drive in Hz (step rate, gait rate, gust rate)")
    fn = g.input("Natural Frequency", "FLOAT", 2.0, min=0.01, max=50.0,
                 desc="The part's own bounce frequency in Hz (stiff = high, floppy = low)")
    zeta = g.input("Damping", "FLOAT", 0.3, min=0.001, max=5.0,
                   desc="Damping ratio: < 1 overshoots and rings, 1 settles fastest without overshoot, > 1 creeps")
    amp = g.input("Amplitude", "FLOAT", 1.0, desc="Drive amplitude: the response before the spring's gain, "
                                                    "and the value the step response settles to")
    phase = g.input("Phase", "FLOAT", 0.0, subtype="ANGLE", desc="Phase offset of the drive (radians, field: "
                                                                 "per-instance offsets desynchronise copies)")
    start = g.input("Step Start", "FLOAT", 0.0, subtype="TIME_ABSOLUTE",
                    desc="Time of the step for Step Response (0 before it)")
    with g.frame("Frequency ratio r = drive / natural, c = 2 zeta r"):
        z = g.math("MAXIMUM", zeta, 0.001, label="zeta (> 0)")
        r = g.math("DIVIDE", fd, g.math("MAXIMUM", fn, 0.001))
        one_m = g.math("SUBTRACT", 1.0, g.math("MULTIPLY", r, r))
        c = _chain(g, z, ("MULTIPLY", 2.0), ("MULTIPLY", r))
    with g.frame("Gain 1/sqrt((1-r^2)^2 + c^2), lag atan2(c, 1-r^2), response"):
        gain = g.math("INVERSE_SQRT", g.math("ADD", g.math("MULTIPLY", one_m, one_m), g.math("MULTIPLY", c, c)))
        lag = g.math("ARCTAN2", c, one_m)
        ang = g.math("SUBTRACT", g.math("ADD", _chain(g, t, ("MULTIPLY", fd), ("MULTIPLY", TAU)), phase), lag)
        resp = _chain(g, g.math("COSINE", ang), ("MULTIPLY", gain), ("MULTIPLY", amp))
    with g.frame("Step: tau = time since the step, a = zeta wn"):
        tau = g.math("MAXIMUM", g.math("SUBTRACT", t, start), 0.0)
        wn = g.math("MULTIPLY", g.math("MAXIMUM", fn, 0.001), TAU)
        a = g.math("MULTIPLY", z, wn)
        decay = g.math("EXPONENT", g.math("MULTIPLY", g.math("MULTIPLY", a, tau), -1.0))
    with g.frame("Underdamped (and critical as wd -> 0): 1 - e^(-a tau) (cos wd tau + a/wd sin wd tau)"):
        wd = g.math("MULTIPLY", wn, g.math("SQRT", g.math("MAXIMUM", g.math("SUBTRACT", 1.0, g.math(
            "MULTIPLY", z, z)), 1e-6)))
        wdt = g.math("MULTIPLY", wd, tau)
        osc = g.math("ADD", g.math("COSINE", wdt),
                     g.math("MULTIPLY", g.math("DIVIDE", a, wd), g.math("SINE", wdt)))
        x_u = g.math("SUBTRACT", 1.0, g.math("MULTIPLY", decay, osc))
    with g.frame("Overdamped: 1 - [(1 + a/wh) e^((wh-a) tau) + (1 - a/wh) e^((-wh-a) tau)] / 2"):
        wh = g.math("MULTIPLY", wn, g.math("SQRT", g.math("MAXIMUM", g.math("SUBTRACT", g.math(
            "MULTIPLY", z, z), 1.0), 1e-4)))
        k = g.math("DIVIDE", a, wh)
        e1 = g.math("EXPONENT", g.math("MULTIPLY", g.math("SUBTRACT", wh, a), tau))
        e2 = g.math("EXPONENT", g.math("MULTIPLY", g.math("MULTIPLY", g.math("ADD", wh, a), -1.0), tau))
        both = g.math("ADD", g.math("MULTIPLY", g.math("ADD", 1.0, k), e1),
                      g.math("MULTIPLY", g.math("SUBTRACT", 1.0, k), e2))
        x_o = g.math("SUBTRACT", 1.0, g.math("MULTIPLY", both, 0.5))
    with g.frame("Pick the regime, scale by Amplitude"):
        over = g.math("GREATER_THAN", z, 1.0)
        step = g.math("MULTIPLY", g.mix(over, x_u, x_o, clamp=False), amp)
    g.output("Response", "FLOAT", resp, desc="Steady periodic response: Amplitude * Gain * cos(drive - Lag)")
    g.output("Gain", "FLOAT", gain, desc="Amplitude gain of the spring at the drive frequency")
    g.output("Lag", "FLOAT", lag, desc="Phase lag behind the drive in radians (0 .. pi)")
    g.output("Step Response", "FLOAT", step, desc="Response to a step of Amplitude at Step Start; settles to "
                                                  "Amplitude")
    return g.finish()


@nodegroup("NK Gait Step", tags=["motion", "walk", "gait", "foot", "locomotion", "animation"],
           use="walking characters' feet, robot legs, animal paws, footprints, anything that plants and lifts "
               "without sliding")
def gait_step():
    """One leg's gait from distance travelled: the foot stays planted during stance and swings on a lifted arc.

    Distance travelled d = Distance + Speed * Time; gait phase = d / Stride (cycles, one cycle = one step of each
    foot). During stance the foot sits at a fixed distance along the path (no sliding: place it with NK Curve
    Frame at Foot Distance); in swing it travels one Stride with a smootherstep and lifts on a 1 - cos arc, so its
    velocity is zero when it leaves and when it lands. For varying speed, integrate the distance yourself and pass
    it as Distance with Speed 0: the phase then stays continuous.
    """
    g = Graph("NK Gait Step", description=_doc(gait_step))
    t = g.input("Time", "FLOAT", 0.0, subtype="TIME_ABSOLUTE", desc="Time in seconds (field)")
    speed = g.input("Speed", "FLOAT", 1.0, min=0.0, max=100.0,
                    desc="Constant travel speed (distance per second); 0 when Distance is integrated elsewhere")
    dist = g.input("Distance", "FLOAT", 0.0, subtype="DISTANCE",
                   desc="Distance travelled, added to Speed * Time (pass an integrated distance for varying speed)")
    stride = g.input("Stride", "FLOAT", 1.2, min=0.01, max=100.0, subtype="DISTANCE",
                     desc="Distance travelled per gait cycle (two steps: one of each foot)")
    offset = g.input("Offset", "FLOAT", 0.0, min=0.0, max=1.0, subtype="FACTOR",
                     desc="This leg's phase offset in cycles (0 and 0.5 for a biped; quarters for a quadruped)")
    stance = g.input("Stance", "FLOAT", 0.6, min=0.05, max=0.95, subtype="FACTOR",
                     desc="Share of the cycle the foot is planted (0.6 walk, 0.4 run)")
    lift_h = g.input("Lift", "FLOAT", 0.1, min=0.0, max=10.0, subtype="DISTANCE", desc="Peak foot lift in swing")
    reach = g.input("Reach", "FLOAT", 0.0, subtype="DISTANCE",
                    desc="Where the foot plants relative to the body at mid-stance (+ ahead)")
    with g.frame("Distance d, gait phase d / Stride, this leg's cycle k and fraction f"):
        d = g.math("MULTIPLY_ADD", speed, t, dist)
        phase = g.math("DIVIDE", d, stride)
        u = g.math("SUBTRACT", phase, offset)
        k = g.math("FLOOR", u)
        f = g.math("SUBTRACT", u, k)
        st = _clamp(g, stance, 0.05, 0.95)
    with g.frame("Plant: where the body is at this leg's mid-stance, plus Reach"):
        plant = _chain(g, g.math("ADD", k, offset), ("ADD", g.math("MULTIPLY", st, 0.5)), ("MULTIPLY", stride),
                       ("ADD", reach))
    with g.frame("Swing progress w (0 in stance), smootherstep travel e = w^3 (w (6w - 15) + 10)"):
        w = _clamp(g, g.math("DIVIDE", g.math("SUBTRACT", f, st), g.math("SUBTRACT", 1.0, st)), 0.0, 1.0)
        inner = _chain(g, w, ("MULTIPLY", 6.0), ("SUBTRACT", 15.0), ("MULTIPLY", w), ("ADD", 10.0))
        e = _chain(g, w, ("MULTIPLY", w), ("MULTIPLY", w), ("MULTIPLY", inner))
        foot = g.math("MULTIPLY_ADD", e, stride, plant)
    with g.frame("Lift (1 - cos 2 pi w) / 2 and stance weight"):
        lift = _chain(g, g.math("COSINE", g.math("MULTIPLY", w, TAU)), ("MULTIPLY", -0.5), ("ADD", 0.5),
                      ("MULTIPLY", lift_h))
        off_ground = g.math("MULTIPLY", _smoothstep(g, 0.0, 0.25, w), g.map_range(w, 0.75, 1.0, 1.0, 0.0,
                                                                                  interp="SMOOTHSTEP"))
        weight = g.math("SUBTRACT", 1.0, off_ground)
    g.output("Foot Distance", "FLOAT", foot, desc="Where the foot is along the path (constant while planted)")
    g.output("Foot Offset", "FLOAT", g.math("SUBTRACT", foot, d), desc="Foot Distance relative to the body")
    g.output("Lift", "FLOAT", lift, desc="Foot height above the ground")
    g.output("Stance Weight", "FLOAT", weight, desc="1 while planted, easing to 0 mid-swing (weight shift, "
                                                    "heel roll, dust)")
    g.output("Swing", "FLOAT", w, desc="Swing progress 0..1 (0 throughout stance)")
    g.output("Phase", "FLOAT", phase, desc="Gait phase in cycles (d / Stride), continuous")
    g.output("Distance", "FLOAT", d, desc="Distance travelled by the body")
    return g.finish()


@nodegroup("NK Wind Gust", tags=["motion", "wind", "gust", "noise", "animation"],
           use="flags, bunting, grass, trees, washing lines, lanterns, sails, smoke, anything moved by wind")
def wind_gust():
    """Smooth bounded gust strength from noise of time, travelling along a coordinate as a gust front.

    Gust = Strength * (1 - Gustiness + Gustiness * envelope), envelope = smoothstep of 1D noise at
    (Time - Lag - Position / Travel Speed) / Gust Period, so it stays in [0, Strength], is smooth in time, and a gust
    reaches a point further along the wind Position / Travel Speed seconds later.
    """
    g = Graph("NK Wind Gust", description=_doc(wind_gust))
    t = g.input("Time", "FLOAT", 0.0, subtype="TIME_ABSOLUTE", desc="Time in seconds (field)")
    pos = g.input("Position", "FLOAT", 0.0, subtype="DISTANCE",
                  desc="Coordinate along the wind direction (field: e.g. dot(position, wind direction))")
    speed = g.input("Travel Speed", "FLOAT", 5.0, min=0.01, max=200.0,
                    desc="How fast gust fronts travel along Position (distance per second)")
    strength = g.input("Strength", "FLOAT", 1.0, min=0.0, max=1000.0, desc="Maximum gust strength")
    gustiness = g.input("Gustiness", "FLOAT", 0.6, min=0.0, max=1.0, subtype="FACTOR",
                        desc="How much the wind comes and goes: 0 steady at Strength, 1 from calm to Strength")
    period = g.input("Gust Period", "FLOAT", 4.0, min=0.05, max=600.0, subtype="TIME_ABSOLUTE",
                     desc="Typical seconds between gusts")
    lag = g.input("Lag", "FLOAT", 0.0, min=0.0, max=60.0, subtype="TIME_ABSOLUTE",
                  desc="Response delay (s): heavier parts follow the gusts later")
    seed = g.input("Seed", "INT", 0, min=0, max=10000, desc="Random seed (field: per-object seeds decorrelate)")
    with g.frame("Retarded time (t - lag - x / speed) in gust periods, offset by seed"):
        tt = g.math("SUBTRACT", g.math("SUBTRACT", t, lag), g.math("DIVIDE", pos, g.math("MAXIMUM", speed, 0.01)))
        w = g.math("ADD", g.math("DIVIDE", tt, g.math("MAXIMUM", period, 0.05)), g.math("MULTIPLY", seed, 7.31))
    with g.frame("Envelope: smoothstep of 1D noise (bounded 0..1, smooth)"):
        n = g.node("ShaderNodeTexNoise", props={"noise_dimensions": "1D"}, W=w, Scale=1.0, Detail=1.5,
                   Roughness=0.5)
        env = _smoothstep(g, 0.25, 0.75, n["Factor"])
    with g.frame("Gust = Strength (1 - Gustiness + Gustiness env)"):
        gs = _clamp(g, gustiness, 0.0, 1.0)
        gust = g.math("MULTIPLY", g.math("ADD", g.math("SUBTRACT", 1.0, gs), g.math("MULTIPLY", gs, env)),
                      g.math("MAXIMUM", strength, 0.0))
    g.output("Gust", "FLOAT", gust, desc="Gust strength in [0, Strength]")
    g.output("Envelope", "FLOAT", env, desc="Normalised gust envelope in [0, 1]")
    return g.finish()


@nodegroup("NK Pendulum Sway", tags=["motion", "pendulum", "sway", "wind", "swing", "animation"],
           use="hanging signs, lanterns, chandeliers, wind chimes, bells, swings, hanging plants")
def pendulum_sway():
    """Small-angle pendulum sway: a lean pushed by the wind plus a ring at the pendulum's own period.

    Period T = 2 pi sqrt(Length / Gravity). Angle = Wind * (Lean + Swing * (sin(2 pi t / T + Phase) + Wobble *
    sin(2 (2 pi t / T + Phase) + 1.3))), so |Angle| <= |Wind| (Lean + Swing (1 + Wobble)). Feed Wind from NK Wind
    Gust and Phase per instance (random) so copies do not swing in step.
    """
    g = Graph("NK Pendulum Sway", description=_doc(pendulum_sway))
    t = g.input("Time", "FLOAT", 0.0, subtype="TIME_ABSOLUTE", desc="Time in seconds (field)")
    length = g.input("Length", "FLOAT", 1.0, min=0.001, max=1000.0, subtype="DISTANCE",
                     desc="Pendulum length from pivot to centre of mass, in metres (sets the period)")
    grav = g.input("Gravity", "FLOAT", 9.81, min=0.01, max=100.0,
                   desc="Gravity in m/s^2 (scale it if the scene is not in metres)")
    wind = g.input("Wind", "FLOAT", 1.0, min=0.0, max=1000.0, desc="Wind drive (field), e.g. NK Wind Gust.Gust")
    lean = g.input("Lean", "FLOAT", 0.03, min=-1.0, max=1.0, subtype="ANGLE",
                   desc="Steady deflection per unit wind (radians)")
    swing = g.input("Swing", "FLOAT", 0.05, min=0.0, max=1.0, subtype="ANGLE",
                    desc="Ring amplitude per unit wind (radians)")
    phase = g.input("Phase", "FLOAT", 0.0, subtype="ANGLE", desc="Per-instance phase (radians, field)")
    wobble = g.input("Wobble", "FLOAT", 0.15, min=0.0, max=1.0, subtype="FACTOR",
                     desc="Share of a second harmonic that breaks up the perfect sine")
    with g.frame("Period T = 2 pi sqrt(L / g), angle theta = 2 pi t / T + Phase"):
        period = g.math("MULTIPLY", g.math("SQRT", g.math("DIVIDE", g.math("MAXIMUM", length, 0.001),
                                                          g.math("MAXIMUM", grav, 0.01))), TAU)
        th = g.math("ADD", g.math("MULTIPLY", g.math("DIVIDE", t, period), TAU), phase)
    with g.frame("Ring sin(theta) + Wobble sin(2 theta + 1.3), scaled by the wind"):
        ring = g.math("ADD", g.math("SINE", th), g.math("MULTIPLY", wobble, g.math(
            "SINE", g.math("MULTIPLY_ADD", th, 2.0, 1.3))))
        ang = g.math("MULTIPLY", wind, g.math("MULTIPLY_ADD", ring, swing, lean))
    g.output("Angle", "FLOAT", ang, desc="Sway angle in radians (rotate about the pivot's hinge axis)")
    g.output("Period", "FLOAT", period, desc="Pendulum period in seconds")
    return g.finish()


@nodegroup("NK Time Remap", tags=["motion", "time", "loop", "retime", "ease", "animation"],
           use="seamless loops, ping-pong cycles, slow motion, staggered starts, eased one-shot moves")
def time_remap():
    """Retime a clock: offset and speed, then optionally loop (sawtooth or ping-pong) with ease in/out.

    u = (Time - Offset) * Speed. With Loop Length L > 0 the output is L * ease(fract(u / L)) (or a 0 -> L -> 0
    triangle of period 2L with Ping Pong), so anything driven by it repeats exactly every L (2L) seconds; with
    L = 0 the output is u. Ease blends linear progress toward smoothstep (slow in, slow out).
    """
    g = Graph("NK Time Remap", description=_doc(time_remap))
    t = g.input("Time", "FLOAT", 0.0, subtype="TIME_ABSOLUTE", desc="Input time in seconds (field)")
    offset = g.input("Offset", "FLOAT", 0.0, subtype="TIME_ABSOLUTE",
                     desc="Start time: the output is 0 here (field: per-instance stagger)")
    speed = g.input("Speed", "FLOAT", 1.0, min=-100.0, max=100.0, desc="Playback rate (2 = twice as fast)")
    loop = g.input("Loop Length", "FLOAT", 0.0, min=0.0, max=10000.0, subtype="TIME_ABSOLUTE",
                   desc="Loop period in output seconds; 0 = no loop")
    pp = g.input("Ping Pong", "BOOL", False, desc="Run forward then backward (period 2 x Loop Length)")
    ease = g.input("Ease", "FLOAT", 0.0, min=0.0, max=1.0, subtype="FACTOR",
                   desc="Ease in/out at the loop ends (0 linear, 1 smoothstep)")
    with g.frame("u = (Time - Offset) Speed; q = u / L"):
        u = g.math("MULTIPLY", g.math("SUBTRACT", t, offset), speed)
        lsafe = g.math("MAXIMUM", loop, 1e-6)
        q = g.math("DIVIDE", u, lsafe)
        cycle = g.math("FLOOR", q)
    with g.frame("Sawtooth fract(q) or ping-pong triangle 1 - |2 fract(q/2) - 1|"):
        saw = g.math("SUBTRACT", q, cycle)
        half = g.math("MULTIPLY", q, 0.5)
        p = g.math("SUBTRACT", half, g.math("FLOOR", half))
        tri = g.math("SUBTRACT", 1.0, g.math("ABSOLUTE", g.math("MULTIPLY_ADD", p, 2.0, -1.0)))
        f = g.mix(pp, saw, tri)
    with g.frame("Ease: blend toward smoothstep f^2 (3 - 2f)"):
        sm = g.math("MULTIPLY", g.math("MULTIPLY", f, f), g.math("MULTIPLY_ADD", f, -2.0, 3.0))
        fe = g.mix(ease, f, sm)
    with g.frame("Looped time L fe, or u when not looping"):
        looping = g.math("GREATER_THAN", loop, 0.0)
        out_t = g.mix(looping, u, g.math("MULTIPLY", fe, loop), clamp=True)
    g.output("Time", "FLOAT", out_t, desc="Remapped time in seconds")
    g.output("Factor", "FLOAT", g.math("MULTIPLY", fe, looping), desc="Progress through the loop 0..1 (0 when "
                                                                      "not looping)")
    g.output("Cycle", "FLOAT", cycle, desc="Index of the current loop (floor(u / L))")
    return g.finish()


@nodegroup("NK Flicker", tags=["motion", "light", "flicker", "noise", "animation"],
           use="lanterns, candles, torches, fires, neon signs, failing bulbs, screens")
def flicker():
    """Bounded smooth light flicker: noise of time plus a faint fast wobble, dipping below a steady strength.

    Value = Strength * (1 - Amount * v), v = 0.75 smoothstep(noise(t Rate)) + 0.25 (0.5 + 0.5 sin(2 pi 1.37 Rate
    t)), so Value stays in [Strength (1 - Amount), Strength] and is smooth. Use per-instance Seeds and store the
    Value as an attribute (e.g. nk_glow) for an emission shader to read.
    """
    g = Graph("NK Flicker", description=_doc(flicker))
    t = g.input("Time", "FLOAT", 0.0, subtype="TIME_ABSOLUTE", desc="Time in seconds (field)")
    seed = g.input("Seed", "INT", 0, min=0, max=100000, desc="Random seed (field: per-light flicker)")
    rate = g.input("Rate", "FLOAT", 1.5, min=0.0, max=60.0, desc="Flicker rate in Hz (candles 1-3, faults 8+)")
    amount = g.input("Amount", "FLOAT", 0.15, min=0.0, max=1.0, subtype="FACTOR",
                     desc="Depth of the dips (0 steady, 1 down to dark)")
    strength = g.input("Strength", "FLOAT", 1.0, min=0.0, max=100000.0, desc="Steady (maximum) strength")
    with g.frame("Slow noise and a fast wobble, both in 0..1"):
        w = g.math("MULTIPLY_ADD", t, rate, g.math("MULTIPLY", seed, 13.7))
        n = g.node("ShaderNodeTexNoise", props={"noise_dimensions": "1D"}, W=w, Scale=1.0, Detail=2.0,
                   Roughness=0.5)
        v1 = _smoothstep(g, 0.25, 0.75, n["Factor"])
        arg = g.math("ADD", _chain(g, t, ("MULTIPLY", rate), ("MULTIPLY", TAU * 1.37)),
                     g.math("MULTIPLY", seed, 2.3))
        wob = g.math("MULTIPLY_ADD", g.math("SINE", arg), 0.5, 0.5)
        v = g.math("ADD", g.math("MULTIPLY", v1, 0.75), g.math("MULTIPLY", wob, 0.25))
    with g.frame("Value = Strength (1 - Amount v)"):
        val = g.math("MULTIPLY", g.math("SUBTRACT", 1.0, g.math("MULTIPLY", _clamp(g, amount, 0.0, 1.0), v)),
                     strength)
    g.output("Value", "FLOAT", val, desc="Light strength in [Strength (1 - Amount), Strength]")
    g.output("Factor", "FLOAT", v, desc="Normalised flicker 0..1 (1 = deepest dip)")
    return g.finish()
