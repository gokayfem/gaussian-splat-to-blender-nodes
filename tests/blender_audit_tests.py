"""Blender-only regression checks for audit false positives.

blender -b --factory-startup --python-exit-code 1 --python tests/blender_audit_tests.py
"""
from pathlib import Path
import sys
import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/gaussian-splat-to-blender-nodes/scripts"))
from audit_blend import audit


def fixture(dependent=False, baked=False):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    coll = bpy.data.collections.new("GARDEN_PROCEDURAL")
    ref = bpy.data.collections.new("GS_REFERENCE")
    sc.collection.children.link(coll)
    sc.collection.children.link(ref)
    ref.hide_render = True
    rm = bpy.data.meshes.new("Scan mesh")
    rm.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
    ro = bpy.data.objects.new("Scan object", rm)
    ref.objects.link(ro)
    mesh = bpy.data.meshes.new("Host")
    if baked:
        mesh.from_pydata([(0, 0, 0)], [], [])
    ob = bpy.data.objects.new("Native candidate", mesh)
    coll.objects.link(ob)
    group = bpy.data.node_groups.new("Test builder", "GeometryNodeTree")
    group.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    out = group.nodes.new("NodeGroupOutput")
    if dependent:
        src = group.nodes.new("GeometryNodeObjectInfo")
        src.inputs["Object"].default_value = ro
        group.links.new(src.outputs["Geometry"], out.inputs["Geometry"])
    else:
        src = group.nodes.new("GeometryNodeMeshCube")
        group.links.new(src.outputs["Mesh"], out.inputs["Geometry"])
    ob.modifiers.new("Builder", "NODES").node_group = group


fixture()
result = audit("GARDEN_PROCEDURAL", "GS_REFERENCE")
assert result["passed"], result
assert result["reference_objects_removed"] == 1
assert result["before"] == result["after"]
print("PASS: independent geometry survives real reference deletion")

fixture(dependent=True)
result = audit("GARDEN_PROCEDURAL", "GS_REFERENCE")
assert not result["passed"], result
assert any("changed after removing" in f for f in result["failures"]), result
print("PASS: scan-dependent Object Info geometry is rejected")

fixture(baked=True)
result = audit("GARDEN_PROCEDURAL", "GS_REFERENCE")
assert not result["passed"], result
assert any("base mesh is nonempty" in f for f in result["failures"]), result
print("PASS: nonempty baked host is rejected")
