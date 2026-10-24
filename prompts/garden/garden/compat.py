"""Blender 5.0.1 adapter for nodekit (written for 5.2+).

Verified during the Blender 5.0.1 study: Geometry Nodes modifiers have no ``mod.properties``; inputs are
ID properties keyed by socket identifier (``mod[ident]``, ``mod[ident + "_use_attribute"]``,
``mod[ident + "_attribute_name"]``). Everything else nodekit uses (interface item flags, menu sockets for
Transform/Resample modes, ``scene.compositing_node_group``) exists in 5.0.1. ``install()`` swaps nodekit's
modifier-input accessors for ID-property versions when ``properties`` is missing and leaves 5.2+ untouched.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILL = ROOT / "vendor"
if str(SKILL) not in sys.path:
    sys.path.insert(0, str(SKILL))

import bpy  # noqa: E402
from nodekit import inspect as nk_inspect  # noqa: E402


def _needs_idprops():
    return bpy.app.version < (5, 2, 0)


def _resolve(value, current):
    if isinstance(value, str) and not isinstance(current, str):
        return bpy.data.objects.get(value) or bpy.data.materials.get(value) or bpy.data.collections.get(value)
    return value


def set_modifier_inputs(mod, values):
    """Set Geometry Nodes modifier inputs by display name using 5.0 ID properties."""
    ids = nk_inspect.modifier_inputs(mod)
    for name, v in values.items():
        if name not in ids:
            raise KeyError(f"{mod.node_group.name} has no input {name!r}")
        ident = ids[name]
        if isinstance(v, dict):
            if "attribute" in v:
                mod[ident + "_use_attribute"] = True
                mod[ident + "_attribute_name"] = v["attribute"]
                continue
            mod[ident + "_use_attribute"] = False
            v = v["value"]
        current = mod.get(ident)
        v = _resolve(v, current)
        if isinstance(v, (tuple, list)):
            v = list(v)
        mod[ident] = v
    mod.node_group.interface_update(bpy.context)
    mod.show_viewport = mod.show_viewport
    return mod


def get_modifier_inputs(mod):
    out = {}
    for name, ident in nk_inspect.modifier_inputs(mod).items():
        if ident not in mod.keys():
            continue
        v = mod[ident]
        out[name] = v.name if isinstance(v, bpy.types.ID) else nk_inspect._val(v) if not hasattr(v, "to_list") \
            else list(v.to_list())
    return out


def install():
    """Patch nodekit for this Blender; returns a short description of what was adapted."""
    if not _needs_idprops():
        return "native (5.2+)"
    nk_inspect.set_modifier_inputs = set_modifier_inputs
    nk_inspect.get_modifier_inputs = get_modifier_inputs
    return "5.0 ID-property modifier inputs"
