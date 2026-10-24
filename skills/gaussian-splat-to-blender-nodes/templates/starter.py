"""Small synthetic GN table for testing the workflow without downloading any scan.

blender -b --factory-startup --python-exit-code 1 --python starter.py -- --out outputs/starter.blend
"""
import argparse
from pathlib import Path
import sys
import bpy


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args(sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else [])
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    coll = bpy.data.collections.new("GARDEN_PROCEDURAL")
    sc.collection.children.link(coll)
    ref = bpy.data.collections.new("GS_REFERENCE")
    sc.collection.children.link(ref)
    ref.hide_render = True
    # A harmless hidden point verifies that the removal audit actually deletes an object.
    ref_mesh = bpy.data.meshes.new("Synthetic reference point")
    ref_mesh.from_pydata([(0, 0, 0)], [], [])
    ref.objects.link(bpy.data.objects.new("Synthetic reference point", ref_mesh))
    mat = bpy.data.materials.new("Procedural wood study")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Roughness"].default_value = 0.65
    tex = nt.nodes.new("ShaderNodeTexNoise")
    tex.location = (-500, 40)
    tex.inputs["Scale"].default_value = 8
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.location = (-250, 40)
    ramp.color_ramp.elements[0].color = (0.08, 0.035, 0.014, 1)
    ramp.color_ramp.elements[1].color = (0.38, 0.20, 0.08, 1)
    nt.links.new(tex.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    g = bpy.data.node_groups.new("Study • Editable table", "GeometryNodeTree")
    g.description = "Synthetic table: native cube primitives and four instanced legs"
    g.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    for name, value, desc in (("Width", 1.6, "Tabletop width in metres"), ("Depth", 1.0, "Tabletop depth in metres")):
        s = g.interface.new_socket(name=name, in_out="INPUT", socket_type="NodeSocketFloat")
        s.default_value, s.min_value, s.max_value, s.description = value, 0.5, 5, desc
    def node(kind, label, x, y):
        n = g.nodes.new(kind)
        n.label, n.location = label, (x, y)
        return n
    gi = node("NodeGroupInput", "Dimensions", -900, 300)
    xyz = node("ShaderNodeCombineXYZ", "Top dimensions", -680, 300)
    xyz.inputs["Z"].default_value = 0.07
    g.links.new(gi.outputs["Width"], xyz.inputs["X"])
    g.links.new(gi.outputs["Depth"], xyz.inputs["Y"])
    top = node("GeometryNodeMeshCube", "Tabletop", -470, 300)
    g.links.new(xyz.outputs["Vector"], top.inputs["Size"])
    trans = node("GeometryNodeTransform", "Top height", -250, 300)
    trans.inputs["Translation"].default_value = (0, 0, 0.735)
    g.links.new(top.outputs["Mesh"], trans.inputs["Geometry"])
    grid = node("GeometryNodeMeshGrid", "Four support locations", -470, -40)
    grid.inputs["Vertices X"].default_value = grid.inputs["Vertices Y"].default_value = 2
    for axis, socket in (("X", "Width"), ("Y", "Depth")):
        math = node("ShaderNodeMath", f"Inset {axis}", -680, -40 if axis == "X" else -230)
        math.operation = "SUBTRACT"
        math.inputs[1].default_value = 0.25
        g.links.new(gi.outputs[socket], math.inputs[0])
        g.links.new(math.outputs[0], grid.inputs[f"Size {axis}"])
    leg = node("GeometryNodeMeshCube", "Leg primitive", -470, -340)
    leg.inputs["Size"].default_value = (0.08, 0.08, 0.70)
    inst = node("GeometryNodeInstanceOnPoints", "Four legs", -250, -40)
    g.links.new(grid.outputs["Mesh"], inst.inputs["Points"])
    g.links.new(leg.outputs["Mesh"], inst.inputs["Instance"])
    lift = node("GeometryNodeTransform", "Leg height", -30, -40)
    lift.inputs["Translation"].default_value = (0, 0, 0.35)
    g.links.new(inst.outputs["Instances"], lift.inputs["Geometry"])
    join = node("GeometryNodeJoinGeometry", "Assemble", 180, 250)
    g.links.new(trans.outputs["Geometry"], join.inputs["Geometry"])
    g.links.new(lift.outputs["Geometry"], join.inputs["Geometry"])
    realize = node("GeometryNodeRealizeInstances", "Assign one study material", 390, 250)
    g.links.new(join.outputs["Geometry"], realize.inputs["Geometry"])
    material = node("GeometryNodeSetMaterial", "Wood", 600, 250)
    material.inputs["Material"].default_value = mat
    g.links.new(realize.outputs["Geometry"], material.inputs["Geometry"])
    go = node("NodeGroupOutput", "Native mesh", 810, 250)
    g.links.new(material.outputs["Geometry"], go.inputs["Geometry"])
    ob = bpy.data.objects.new("Study_Table", bpy.data.meshes.new("Empty GN host"))
    coll.objects.link(ob)
    ob.modifiers.new("Editable table", "NODES").node_group = g
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    sc.world = bpy.data.worlds.new("Study world")
    sc.world.use_nodes = True
    sc.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.22, 0.25, 0.30, 1)
    light = bpy.data.lights.new("Key", "AREA")
    light.energy, light.shape, light.size = 700, "DISK", 4
    lo = bpy.data.objects.new("Key", light)
    sc.collection.objects.link(lo)
    lo.location = (1, -1, 4)
    sc.view_settings.view_transform = "AgX"
    a.out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(a.out.resolve()), compress=True)
    print("STARTER_SAVED", a.out)


if __name__ == "__main__":
    main()
