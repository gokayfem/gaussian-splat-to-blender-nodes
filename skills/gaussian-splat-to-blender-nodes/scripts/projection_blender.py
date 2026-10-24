"""Prepare or assemble project-agnostic hybrid texture mapping in a disposable Blender process.

blender -b scene.blend --python-exit-code 1 --python projection_blender.py -- prepare --config mapping.json --out prepared
blender -b scene.blend --python-exit-code 1 --python projection_blender.py -- assemble --config mapping.json --prepared prepared --textures mapped --out hybrid.blend

Source geometry is evaluated from reconstructed objects, never from a reference splat.
Assembly saves baked copies and retains hidden source graphs; later GN edits require rebaking.
"""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from projection_config import load_config, sha256


def material(name):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.node_tree.nodes.clear()
    out = mat.node_tree.nodes.new("ShaderNodeOutputMaterial")
    return mat, mat.node_tree, out


def emission(name, value=None):
    mat, nt, out = material(name)
    shader = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(shader.outputs[0], out.inputs["Surface"])
    if value is not None:
        shader.inputs["Color"].default_value = (*value, 1)
    return mat, nt, shader


def disable_reference(cfg):
    for name in cfg.get("reference_collections", ["GS_REFERENCE"]):
        col = bpy.data.collections.get(name)
        if col:
            col.hide_render = True
            col.hide_viewport = True


def render_setup(device, samples):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device, sc.cycles.samples = device, samples
    sc.render.resolution_percentage = 100
    sc.render.pixel_aspect_x = sc.render.pixel_aspect_y = 1
    sc.render.use_border = False
    sc.render.film_transparent = True
    sc.render.use_compositing = False
    sc.render.use_sequencer = False
    if hasattr(sc.render, "use_motion_blur"):
        sc.render.use_motion_blur = False
    return sc


def evaluated_copy(source, name):
    if source.type != "MESH":
        raise ValueError(f"Target must be a mesh host (including GN): {source.name}")
    # Realize GN instances before requesting the evaluated mesh component.
    ng = bpy.data.node_groups.new("Mapping Realize", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    gi, go = ng.nodes.new("NodeGroupInput"), ng.nodes.new("NodeGroupOutput")
    realize = ng.nodes.new("GeometryNodeRealizeInstances")
    ng.links.new(gi.outputs[0], realize.inputs["Geometry"])
    ng.links.new(realize.outputs[0], go.inputs[0])
    mod = source.modifiers.new("Mapping temporary realize", "NODES"); mod.node_group = ng
    try:
        bpy.context.view_layer.update()
        mesh = bpy.data.meshes.new_from_object(source.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    finally:
        source.modifiers.remove(mod)
        bpy.data.node_groups.remove(ng)
    if not mesh.polygons:
        raise ValueError(f"Target evaluates to no mesh faces: {source.name}")
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.matrix_world = source.matrix_world.copy()
    return obj


def select(obj):
    for other in bpy.context.view_layer.objects:
        other.select_set(False)
    obj.hide_set(False); obj.hide_render = False
    obj.select_set(True); bpy.context.view_layer.objects.active = obj


def bake(obj, mats, size, kind, samples):
    originals = list(obj.data.materials)
    indices = np.array([p.material_index for p in obj.data.polygons], np.int32)
    obj.data.materials.clear()
    for mat in mats:
        obj.data.materials.append(mat)
    obj.data.polygons.foreach_set("material_index", indices)
    image = bpy.data.images.new(f"MAP_{obj.name}_{kind}", size, size, float_buffer=True, alpha=True)
    image.colorspace_settings.name = "Non-Color"
    nodes = []
    for mat in set(mats):
        tex = mat.node_tree.nodes.new("ShaderNodeTexImage"); tex.image = image
        mat.node_tree.nodes.active = tex; nodes.append((mat, tex))
    select(obj)
    sc = bpy.context.scene
    sc.cycles.samples = samples if kind == "irradiance" else 1
    sc.render.bake.margin = 0
    if kind == "irradiance":
        sc.render.bake.use_pass_direct = True
        sc.render.bake.use_pass_indirect = True
        sc.render.bake.use_pass_color = False
    try:
        bpy.ops.object.bake(type="DIFFUSE" if kind == "irradiance" else "EMIT")
        array = np.array(image.pixels[:], np.float32).reshape(size, size, 4)[::-1, :, :3].copy()
    finally:
        for mat, tex in nodes:
            mat.node_tree.nodes.remove(tex)
        bpy.data.images.remove(image)
        obj.data.materials.clear()
        for mat in originals:
            obj.data.materials.append(mat)
        obj.data.polygons.foreach_set("material_index", indices)
    return array


def camera_object():
    obj = bpy.data.objects.new("MAP_camera", bpy.data.cameras.new("MAP_camera"))
    bpy.context.scene.collection.objects.link(obj)
    obj.data.sensor_fit = "VERTICAL"
    obj.data.clip_start, obj.data.clip_end = 0.001, 10000
    return obj


def set_camera(obj, c):
    pos, target, up = (Vector(c[k]) for k in ("position", "look_at", "up"))
    z = (pos-target).normalized(); x = up.cross(z).normalized(); y = z.cross(x)
    obj.matrix_world = Matrix(((x.x, y.x, z.x, pos.x), (x.y, y.y, z.y, pos.y),
                               (x.z, y.z, z.z, pos.z), (0, 0, 0, 1)))
    obj.data.angle_y = math.radians(c["fov_y_deg"])
    sc = bpy.context.scene; sc.camera = obj
    sc.render.resolution_x, sc.render.resolution_y = c["width"], c["height"]


def visibility(cfg, out):
    sc = bpy.context.scene
    sc.cycles.samples = 1; sc.cycles.use_denoising = False
    sc.cycles.pixel_filter_type = "BOX"; sc.cycles.filter_width = 0.01
    sc.world = None
    sc.render.image_settings.file_format = "OPEN_EXR"; sc.render.image_settings.color_depth = "32"
    ids = {t["object"]: t["object_id"] for t in cfg["targets"]}
    for obj in sc.objects:
        obj.pass_index = ids.get(obj.name, 32767)
    depth, nt, shader = emission("MAP_distance")
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    origin = nt.nodes.new("ShaderNodeCombineXYZ")
    dist = nt.nodes.new("ShaderNodeVectorMath"); dist.operation = "DISTANCE"
    nt.links.new(geo.outputs["Position"], dist.inputs[0]); nt.links.new(origin.outputs[0], dist.inputs[1])
    nt.links.new(dist.outputs["Value"], shader.inputs["Color"])
    ident, it, ish = emission("MAP_object_ID")
    info = it.nodes.new("ShaderNodeObjectInfo")
    it.links.new(info.outputs["Object Index"], ish.inputs["Color"])
    cam = camera_object()
    (out/"depth").mkdir()
    for name, view in cfg["views"].items():
        c = view["camera"]; set_camera(cam, c)
        for i, value in enumerate(c["position"]):
            origin.inputs[i].default_value = value
        for suffix, mat in (("", depth), ("_id", ident)):
            bpy.context.view_layer.material_override = mat
            path = out/"depth"/f"{name}{suffix}.exr"
            sc.render.filepath = str(path)
            bpy.ops.render.render(write_still=True)
            image = bpy.data.images.load(str(path), check_existing=False)
            pixels = np.array(image.pixels[:], np.float32).reshape(c["height"], c["width"], 4)[::-1]
            values = np.where(pixels[..., 3] > 0.5, pixels[..., 0], 0 if suffix else np.inf)
            values = np.rint(values).astype(np.uint16) if suffix else values.astype(np.float32)
            np.save(out/"depth"/f"{name}{suffix}.npy", values)
            bpy.data.images.remove(image); path.unlink()
        print("VISIBILITY", name, flush=True)
    bpy.context.view_layer.material_override = None


def prepare(args, cfg):
    args.out.mkdir(parents=True, exist_ok=False)
    sc = render_setup(args.device, args.samples)
    disable_reference(cfg)
    report = dict(schema_version=1, config_sha256=sha256(args.config),
                  source_blend_sha256=sha256(bpy.data.filepath), blender_version=bpy.app.version_string, targets={})
    copies = []
    for target in cfg["targets"]:
        source = bpy.data.objects[target["object"]]
        if source.hide_render or not source.visible_get():
            raise ValueError(f"Target is not visible in the current view layer: {source.name}")
        name = target["name"]
        obj = evaluated_copy(source, "MAP_"+name)
        copies.append(obj)
        source.hide_render = True
        select(obj)
        fallback_uv = next((uv.name for uv in obj.data.uv_layers if uv.active_render), None)
        if target.get("uv_mode", "unwrap") == "unwrap":
            obj.data.uv_layers.new(name="MappingUV")
            obj.data.uv_layers.active_index = len(obj.data.uv_layers)-1
            bpy.ops.object.mode_set(mode="EDIT"); bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.003, scale_to_bounds=True)
            bpy.ops.object.mode_set(mode="OBJECT")
        elif target["uv_mode"] != "existing" or not obj.data.uv_layers.active:
            raise ValueError("uv_mode must be unwrap or existing with a valid nonoverlapping UV map")
        mapping_uv = obj.data.uv_layers.active.name
        obj.data.uv_layers.active.active_render = True
        if not obj.data.materials:
            fallback = bpy.data.materials.new("MAP neutral fallback"); fallback.use_nodes = True
            obj.data.materials.append(fallback)
        for i, mat in enumerate(obj.data.materials):
            if mat is None:
                # GN can retain an unused empty slot before its assigned materials.
                # Keep the slot index; removing it would remap face identities.
                mat = bpy.data.materials.new(f"MAP neutral slot {i}"); mat.use_nodes = True
                obj.data.materials[i] = mat
            if not mat.use_nodes:
                raise ValueError(f"Target needs node materials in every slot: {name}, slot {i}")
        count = len(obj.data.materials); size = target.get("texture_size", 1024)
        selected = target.get("material_slots", list(range(count)))
        if not selected or any(type(i) is not int or i < 0 or i >= count for i in selected):
            raise ValueError(f"Invalid material_slots: {name}")
        for field, socket in (("position", "Position"), ("normal", "True Normal")):
            mat, nt, shader = emission("MAP_"+field)
            geo = nt.nodes.new("ShaderNodeNewGeometry")
            nt.links.new(geo.outputs[socket], shader.inputs["Color"])
            array = bake(obj, [mat]*count, size, field, args.samples)
            np.save(args.out/f"{name}_{field}.npy", array)
        mats = [emission("MAP_slot_"+str(i), (i+1,)*3)[0] for i in range(count)]
        indices = np.rint(bake(obj, mats, size, "material", args.samples)[..., 0]).astype(np.int32)-1
        normals = np.load(args.out/f"{name}_normal.npy")
        valid = (np.linalg.norm(normals, axis=2) > 0.5) & np.isin(indices, selected)
        if not valid.any():
            raise ValueError(f"No selected UV texels: {name}")
        np.save(args.out/f"{name}_material.npy", indices)
        np.save(args.out/f"{name}_valid.npy", valid)
        if target.get("appearance") == "estimated_albedo":
            white, nt, output = material("MAP_white_diffuse")
            diffuse = nt.nodes.new("ShaderNodeBsdfDiffuse")
            diffuse.inputs["Color"].default_value = (1, 1, 1, 1)
            nt.links.new(diffuse.outputs[0], output.inputs["Surface"])
            np.save(args.out/f"{name}_irradiance.npy", bake(obj, [white]*count, size, "irradiance", args.samples))
        report["targets"][name] = dict(object=obj.name, source_object=source.name,
            materials=[m.name for m in obj.data.materials], selected_slots=selected,
            mapping_uv=mapping_uv, fallback_uv=fallback_uv,
            polygons=len(obj.data.polygons), surface_texels=int(valid.sum()))
        obj.hide_render = True; source.hide_render = False
    bpy.data.libraries.write(str(args.out/"targets.blend"), set(copies), fake_user=True, path_remap="ABSOLUTE")
    visibility(cfg, args.out)
    report["files"] = {str(p.relative_to(args.out)): sha256(p) for p in sorted(args.out.rglob("*")) if p.is_file()}
    (args.out/"prepared.json").write_text(json.dumps(report, indent=2)+"\n")


def assemble(args, cfg):
    prep = json.loads((args.prepared/"prepared.json").read_text())
    mapped = json.loads((args.textures/"projection.json").read_text())
    if args.out.exists() or args.out.resolve() == Path(bpy.data.filepath).resolve():
        raise ValueError("Output must be a new .blend path; preserve the source")
    if prep["source_blend_sha256"] != sha256(bpy.data.filepath):
        raise ValueError("Source blend changed since preparation; rebake the new geometry")
    if sha256(args.config) != prep["config_sha256"] or mapped["prepared_sha256"] != sha256(args.prepared/"prepared.json"):
        raise ValueError("Config/prepared/mapped checkpoint mismatch")
    for directory, manifest in ((args.prepared, prep), (args.textures, mapped)):
        for name, digest in manifest["files"].items():
            if sha256(directory/name) != digest:
                raise ValueError(f"Artifact changed: {name}")
    if mapped["config_sha256"] != prep["config_sha256"]:
        raise ValueError("Projection config mismatch")
    wanted = [prep["targets"][t["name"]]["object"] for t in cfg["targets"]]
    if any(name in bpy.data.objects for name in wanted):
        raise ValueError("Source already contains mapped targets; use the original frozen source")
    with bpy.data.libraries.load(str(args.prepared/"targets.blend")) as (src, dst):
        dst.objects = wanted
    disable_reference(cfg)
    collection = bpy.data.collections.new("MAPPED_SURFACES")
    bpy.context.scene.collection.children.link(collection)
    for target, obj in zip(cfg["targets"], dst.objects):
        name = target["name"]
        collection.objects.link(obj); obj.hide_render = False; obj.hide_viewport = False
        source = bpy.data.objects[target["object"]]
        source.hide_render = True; source.hide_viewport = True
        original_uv = prep["targets"][name]["fallback_uv"]
        if original_uv:
            obj.data.uv_layers[original_uv].active_render = True
        rgb = bpy.data.images.load(str(args.textures/f"{name}_appearance.png"), check_existing=False)
        rgb.colorspace_settings.name = "sRGB"; rgb.pack()
        mix = bpy.data.images.load(str(args.textures/f"{name}_mix.png"), check_existing=False)
        mix.colorspace_settings.name = "Non-Color"; mix.pack()
        for slot in prep["targets"][name]["selected_slots"]:
            mat = obj.data.materials[slot].copy(); mat.name += " [mapped]"
            obj.data.materials[slot] = mat; nt = mat.node_tree
            output = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output)
            if not output.inputs["Surface"].is_linked:
                raise ValueError(f"No fallback surface shader: {name}/{slot}")
            fallback = output.inputs["Surface"].links[0].from_socket
            tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = rgb; tex.extension = "EXTEND"
            mask = nt.nodes.new("ShaderNodeTexImage"); mask.image = mix; mask.extension = "EXTEND"
            uv = nt.nodes.new("ShaderNodeUVMap"); uv.uv_map = prep["targets"][name]["mapping_uv"]
            nt.links.new(uv.outputs[0], tex.inputs["Vector"]); nt.links.new(uv.outputs[0], mask.inputs["Vector"])
            settings = target.get("material_overrides", {}).get(str(slot), {})
            scale = nt.nodes.new("ShaderNodeVectorMath"); scale.operation = "SCALE"
            scale.inputs["Scale"].default_value = settings.get("color_scale", 1.0)
            nt.links.new(tex.outputs["Color"], scale.inputs[0])
            if target.get("appearance", "captured_radiance") == "captured_radiance":
                shader = nt.nodes.new("ShaderNodeEmission")
                nt.links.new(scale.outputs[0], shader.inputs["Color"])
            else:
                shader = nt.nodes.new("ShaderNodeBsdfPrincipled")
                nt.links.new(scale.outputs[0], shader.inputs["Base Color"])
                shader.inputs["Roughness"].default_value = settings.get("roughness", 0.5)
                shader.inputs["Specular IOR Level"].default_value = settings.get("specular", 0.5)
            blend = nt.nodes.new("ShaderNodeMixShader")
            nt.links.new(mask.outputs["Color"], blend.inputs[0])
            nt.links.new(fallback, blend.inputs[1]); nt.links.new(shader.outputs[0], blend.inputs[2])
            nt.links.new(blend.outputs[0], output.inputs["Surface"])
        obj["mapping_source_object"] = source.name
        obj["mapping_editability"] = "Baked evaluated mesh; edits to source GN require rebaking"
    bpy.context.scene["mapping_manifest_sha256"] = sha256(args.textures/"projection.json")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.out.resolve()), compress=True)
    print("SAVED_HYBRID", args.out, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "assemble"))
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--prepared", type=Path)
    parser.add_argument("--textures", type=Path)
    parser.add_argument("--device", choices=("CPU", "GPU"), default="CPU")
    parser.add_argument("--samples", type=int, default=32)
    args = parser.parse_args(sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else [])
    if not bpy.data.filepath or not Path(bpy.data.filepath).is_file():
        parser.error("Open a saved reconstructed scene first")
    if args.samples < 1:
        parser.error("samples must be positive")
    cfg, _ = load_config(args.config)
    if args.action == "prepare":
        prepare(args, cfg)
    elif args.prepared and args.textures:
        assemble(args, cfg)
    else:
        parser.error("assemble requires --prepared and --textures")


if __name__ == "__main__":
    main()
