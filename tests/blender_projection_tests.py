"""Blender integration fixture. See tests/README.md; never downloads or modifies a scan."""
import argparse
import json
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Vector

SCRIPTS = Path(__file__).resolve().parents[1]/"skills/gaussian-splat-to-blender-nodes/scripts"
sys.path.insert(0, str(SCRIPTS))
from projection_blender import camera_object, render_setup, set_camera


def create(root):
    root.mkdir(parents=True, exist_ok=False)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = render_setup("CPU", 4)
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    world = bpy.data.worlds.new("Synthetic lighting"); world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (.6, .6, .6, 1)
    sc.world = world
    mats = []
    for name, color in (("Ochre", (.4, .12, .03, 1)), ("Teal", (.02, .28, .3, 1))):
        m = bpy.data.materials.new(name); m.use_nodes = True
        m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = color
        mats.append(m)
    # Arbitrarily named, transformed live GN host: independent of the study's objects/frame.
    host = bpy.data.objects.new("Archive Panel 37", bpy.data.meshes.new("Empty host"))
    sc.collection.objects.link(host); host.location = (2, -1, .6); host.rotation_euler.z = .37
    ng = bpy.data.node_groups.new("Synthetic parametric box", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    cube = ng.nodes.new("GeometryNodeMeshCube"); cube.inputs["Size"].default_value = (1.5, .8, .9)
    normal = ng.nodes.new("GeometryNodeInputNormal")
    sep = ng.nodes.new("ShaderNodeSeparateXYZ"); ng.links.new(normal.outputs[0], sep.inputs[0])
    compare = ng.nodes.new("ShaderNodeMath"); compare.operation = "GREATER_THAN"; compare.inputs[1].default_value = .5
    ng.links.new(sep.outputs["Z"], compare.inputs[0])
    first = ng.nodes.new("GeometryNodeSetMaterial"); first.inputs["Material"].default_value = mats[0]
    ng.links.new(cube.outputs["Mesh"], first.inputs["Geometry"])
    second = ng.nodes.new("GeometryNodeSetMaterial"); second.inputs["Material"].default_value = mats[1]
    ng.links.new(first.outputs[0], second.inputs["Geometry"]); ng.links.new(compare.outputs[0], second.inputs["Selection"])
    instance = ng.nodes.new("GeometryNodeGeometryToInstance")
    ng.links.new(second.outputs[0], instance.inputs["Geometry"])
    out = ng.nodes.new("NodeGroupOutput"); ng.links.new(instance.outputs[0], out.inputs[0])
    host.modifiers.new("Live box", "NODES").node_group = ng
    bpy.ops.mesh.primitive_plane_add(size=2, location=(2, -1, 0))
    floor = bpy.context.object; floor.name = "Display Platform 92"; floor.data.materials.append(mats[0].copy())
    # Exercise a pre-existing UV texture with a source-blend-relative dependency.
    image = bpy.data.images.new("Original fallback", 4, 4)
    image.pixels = [.4, .12, .03, 1]*16
    image.filepath_raw = str(root/"fallback.png"); image.file_format = "PNG"; image.save()
    nt = floor.data.materials[0].node_tree
    tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = image
    nt.links.new(tex.outputs["Color"], nt.nodes["Principled BSDF"].inputs["Base Color"])
    # An opaque independent object to test full-scene visibility rather than isolated-target depth.
    bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=8, radius=.15, location=(2, -1.65, .5))
    bpy.context.object.name = "Unmapped occluder"
    bpy.context.object.data.materials.append(mats[1])
    cam = camera_object(); sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_mode = "RGBA"
    views = {}
    for name, pos in (("front", [4, -4, 3]), ("back", [0, 2, 2.5])):
        c = dict(position=pos, look_at=[2, -1, .4], up=[0, 0, 1], fov_y_deg=45, width=128, height=96)
        set_camera(cam, c); sc.render.filepath = str(root/f"{name}.png")
        bpy.ops.render.render(write_still=True)
        views[name] = dict(camera=c, image=f"{name}.png")
    config = dict(schema_version=1, reference_collections=[], views=views, targets=[
        dict(name="box", object=host.name, object_id=5, texture_size=64, appearance="captured_radiance",
             projection=dict(mode="robust", border=1, mix_feather=1, padding=2)),
        dict(name="base", object=floor.name, object_id=9, texture_size=64, appearance="estimated_albedo",
             projection=dict(border=1, mix_feather=1, padding=2))])
    (root/"mapping.json").write_text(json.dumps(config, indent=2)+"\n")
    bpy.ops.wm.save_as_mainfile(filepath=str(root/"source.blend"))
    image.filepath = "//fallback.png"
    bpy.ops.wm.save_as_mainfile(filepath=str(root/"source.blend"))


def verify(root):
    prep = json.loads((root/"prepared/prepared.json").read_text())
    report = json.loads((root/"mapped/projection.json").read_text())
    # Negative world coordinates and normals must survive float baking without color clipping.
    pos = np.load(root/"prepared/box_position.npy")
    normals = np.load(root/"prepared/box_normal.npy")
    valid = np.load(root/"prepared/box_valid.npy")
    assert pos[valid, 1].max() < 0
    assert normals[valid].min() < -.8
    indices = np.load(root/"prepared/box_material.npy")
    names = prep["targets"]["box"]["materials"]
    assert {names[i] for i in np.unique(indices[valid])} == {"Ochre", "Teal"}
    assert (np.load(root/"prepared/depth/front_id.npy") == 32767).any(), "Occluder missing from ID pass"
    for name, entry in prep["targets"].items():
        obj = bpy.data.objects[entry["object"]]; source = bpy.data.objects[entry["source_object"]]
        assert source.hide_render and not obj.hide_render
        assert np.allclose(obj.matrix_basis, source.matrix_basis)  # Hidden sources are not evaluated on reopen.
        assert "Baked evaluated mesh" in obj["mapping_editability"]
        if entry["fallback_uv"]:
            assert obj.data.uv_layers[entry["fallback_uv"]].active_render
            assert entry["mapping_uv"] != entry["fallback_uv"]
        assert 0 < report["targets"][name]["direct"] < 1
        assert report["targets"][name]["unseen_fallback"] > 0
        assert np.count_nonzero(np.load(root/f"mapped/{name}_coverage.npy") == 1) > 10
        for i in entry["selected_slots"]:
            nodes = obj.data.materials[i].node_tree.nodes
            images = [n.image for n in nodes if n.type == "TEX_IMAGE"]
            mapped_images = [im for im in images if "_appearance" in im.name or "_mix" in im.name]
            assert len(mapped_images) == 2 and all(im.packed_file for im in mapped_images)
            for im in images:
                if im not in mapped_images:
                    assert Path(bpy.path.abspath(im.filepath)).resolve() == root/"fallback.png"
            mix = next(n for n in nodes if n.type == "MIX_SHADER")
            assert all(mix.inputs[i].is_linked for i in range(3))
            assert any(n.type == "UVMAP" and n.uv_map == entry["mapping_uv"] for n in nodes)
    assert any(m.type == "NODES" for m in bpy.data.objects["Archive Panel 37"].modifiers)
    sc = render_setup("CPU", 4)
    cfg = json.loads((root/"mapping.json").read_text())
    for name, view in cfg["views"].items():
        set_camera(sc.camera, view["camera"])
        sc.render.image_settings.file_format = "PNG"; sc.render.filepath = str(root/f"hybrid-{name}.png")
        bpy.ops.render.render(write_still=True)
    print("PROJECTION_INTEGRATION_OK", flush=True)


parser = argparse.ArgumentParser()
parser.add_argument("action", choices=("create", "verify"))
parser.add_argument("--root", type=Path, required=True)
args = parser.parse_args(sys.argv[sys.argv.index("--")+1:])
(create if args.action == "create" else verify)(args.root.resolve())
