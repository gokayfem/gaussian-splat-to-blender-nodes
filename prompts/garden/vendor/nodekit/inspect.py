"""Read back what was actually built: node groups as JSON, structural checks, modifier inputs by name.

Inside Blender:
    from nodekit import inspect
    inspect.dump_groups("out/graph.json")     # every node group: interface, nodes, links, frames
    problems = inspect.check_groups()         # list of strings; empty means clean
    inspect.set_modifier_inputs(obj.modifiers["Storybook Street"], {"Street Width": 5.0})
"""
import json
import bpy

_SKIP_PROPS = {"rna_type", "name", "label", "location", "width", "height", "dimensions", "inputs", "outputs",
               "internal_links", "parent", "select", "show_options", "show_preview", "hide", "mute",
               "show_texture", "type", "bl_idname", "bl_label", "bl_description", "bl_icon", "bl_static_type",
               "bl_width_default", "bl_width_min", "bl_width_max", "bl_height_default", "bl_height_min",
               "bl_height_max", "color", "use_custom_color", "location_absolute", "warning_propagation",
               "color_tag", "is_active_output", "interface", "active_item", "active_index", "label_size",
               "shrink", "text", "debug_zone_body_lazy_function_graph", "debug_zone_lazy_function_graph"}


def _val(v):
    if hasattr(v, "__len__") and not isinstance(v, str):
        try:
            return [round(float(x), 5) for x in v]
        except (TypeError, ValueError):
            return str(v)
    if isinstance(v, float):
        return round(v, 5)
    if isinstance(v, bpy.types.ID):
        return f"ID:{v.name}"
    return v if isinstance(v, (int, bool, str)) or v is None else str(v)


def node_record(n):
    props = {}
    for p in n.bl_rna.properties:
        if p.identifier in _SKIP_PROPS or p.type in {"POINTER", "COLLECTION"} and p.identifier != "node_tree":
            continue
        try:
            props[p.identifier] = _val(getattr(n, p.identifier))
        except Exception:
            pass
    if getattr(n, "node_tree", None):
        props["node_tree"] = n.node_tree.name
    ins = {}
    for s in n.inputs:
        if s.enabled and not s.is_linked and hasattr(s, "default_value"):
            ins[s.name if s.name not in ins else s.identifier] = _val(s.default_value)
    return {"name": n.name, "type": n.bl_idname, "label": n.label,
            "frame": n.parent.label if n.parent else None, "props": props, "inputs": ins}


def group_record(ng):
    iface = []
    for it in ng.interface.items_tree:
        if it.item_type == "PANEL":
            iface.append({"panel": it.name})
            continue
        rec = {"io": it.in_out, "name": it.name, "type": it.socket_type, "description": it.description,
               "panel": it.parent.name if it.parent and it.parent.name else None}
        for k in ("default_value", "min_value", "max_value", "subtype"):
            if hasattr(it, k):
                rec[k] = _val(getattr(it, k))
        iface.append(rec)
    links = [[l.from_node.name, l.from_socket.identifier, l.to_node.name, l.to_socket.identifier]
             for l in ng.links]
    return {"name": ng.name, "type": ng.bl_idname, "description": ng.description, "interface": iface,
            "nodes": [node_record(n) for n in ng.nodes if n.bl_idname != "NodeFrame"],
            "frames": sorted({n.label for n in ng.nodes if n.bl_idname == "NodeFrame"}), "links": links}


def dump_groups(path, prefix=""):
    data = [group_record(ng) for ng in sorted(bpy.data.node_groups, key=lambda g: g.name)
            if ng.name.startswith(prefix)]
    with open(path, "w") as f:
        json.dump(data, f, indent=1)
    return data


def check_groups(prefix=""):
    """Structural lint: undocumented inputs, dangling nodes, invalid links, unframed big graphs."""
    out = []
    for ng in bpy.data.node_groups:
        if not ng.name.startswith(prefix):
            continue
        if not ng.description:
            out.append(f"{ng.name}: group has no description")
        for it in ng.interface.items_tree:
            if it.item_type == "SOCKET" and it.in_out == "INPUT" and not it.description:
                out.append(f"{ng.name}: input '{it.name}' has no description")
        for l in ng.links:
            if not l.is_valid:
                out.append(f"{ng.name}: invalid link {l.from_node.name}.{l.from_socket.name} -> "
                           f"{l.to_node.name}.{l.to_socket.name}")
        used = {l.from_node for l in ng.links}
        for n in ng.nodes:
            if n.bl_idname in {"NodeFrame", "NodeGroupOutput", "NodeGroupInput", "NodeReroute"}:
                continue
            if n.bl_idname.startswith("ShaderNodeOutput") or n.bl_idname == "ShaderNodeOutputMaterial":
                continue
            if n not in used and any(s.enabled for s in n.outputs):
                out.append(f"{ng.name}: node '{n.label or n.name}' ({n.bl_idname}) output unused")
        real = [n for n in ng.nodes if n.bl_idname not in {"NodeFrame", "NodeGroupInput", "NodeGroupOutput"}]
        if len(real) > 25 and not any(n.bl_idname == "NodeFrame" for n in ng.nodes):
            out.append(f"{ng.name}: {len(real)} nodes and no frames")
    return out


def modifier_inputs(mod):
    """{input name: identifier} for a Geometry Nodes modifier."""
    return {it.name: it.identifier for it in mod.node_group.interface.items_tree
            if it.item_type == "SOCKET" and it.in_out == "INPUT"}


def _slot(mod, ident):
    """Blender 5.2 keeps modifier inputs at mod.properties.inputs.<identifier> (.value, .type, .attribute_name)."""
    return getattr(mod.properties.inputs, ident)


def set_modifier_inputs(mod, values):
    """Set modifier inputs by name. A value of ``{"attribute": "name"}`` switches a field input to read that
    named attribute (attribute mode); ``{"value": x}`` switches it back to a plain value."""
    ids = modifier_inputs(mod)
    for name, v in values.items():
        if name not in ids:
            raise KeyError(f"{mod.node_group.name} has no input {name!r}")
        slot = _slot(mod, ids[name])
        if isinstance(v, dict):
            if "attribute" in v:
                slot.type, slot.attribute_name = "ATTRIBUTE", v["attribute"]
                continue
            slot.type, v = "VALUE", v["value"]
        if isinstance(v, str) and not isinstance(slot.value, str):
            v = bpy.data.objects.get(v) or bpy.data.materials.get(v) or bpy.data.collections.get(v)
        slot.value = v
    mod.node_group.interface_update(bpy.context)
    return mod


def get_modifier_inputs(mod):
    out = {}
    for name, ident in modifier_inputs(mod).items():
        try:
            v = _slot(mod, ident).value
        except AttributeError:
            continue
        out[name] = v.name if isinstance(v, bpy.types.ID) else _val(v)
    return out


def evaluated_stats(obj, scene=None):
    """Counts on the evaluated geometry: proves the graph evaluates to something at the current frame."""
    dg = scene.view_layers[0].depsgraph if scene else bpy.context.evaluated_depsgraph_get()
    if scene:
        dg.update()
    ev = obj.evaluated_get(dg)
    m = ev.to_mesh()
    stats = {"verts": len(m.vertices), "faces": len(m.polygons),
             "materials": sorted({ev.material_slots[p.material_index].name for p in m.polygons
                                  if p.material_index < len(ev.material_slots)})}
    ev.to_mesh_clear()
    try:                                       # point clouds and curves are not part of to_mesh()
        gs = ev.evaluated_geometry()
        pc = gs.pointcloud
        stats["points"] = len(pc.points) if pc else 0
        stats["curves"] = len(gs.curves.curves) if gs.curves else 0
    except (AttributeError, RuntimeError):
        pass
    return stats
