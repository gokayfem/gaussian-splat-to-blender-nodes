"""Shared helpers for part builders: parameter files, colours and material scaffolding."""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_params(name):
    """Fitted parameters for one part: data/params/<name>.json (empty dict when absent)."""
    p = ROOT / "data" / "params" / f"{name}.json"
    return json.load(open(p)) if p.exists() else {}


def srgb_to_linear(rgb):
    """sRGB 0-1 (or 0-255 ints) -> linear RGBA tuple for shader defaults."""
    vals = [v / 255.0 if max(rgb) > 1.0 else v for v in rgb[:3]]
    lin = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in vals]
    return (*lin, 1.0)


def new_material(name):
    """Get-or-create a material with an emptied node tree; returns (material, nodes, links, output node)."""
    import bpy
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    return m, nt.nodes, nt.links, out
