"""Shared material helpers. Owner-specific materials live in street/materials/<owner>.py."""
import bpy


def material(name):
    """Get-or-create a node material named ``name`` with an emptied tree (rebuilt on every build)."""
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    if m.node_tree is None:                  # Blender 5.x materials always use nodes; use_nodes is deprecated
        m.use_nodes = True
    m.node_tree.nodes.clear()
    return m


def flat(name, rgb, roughness=0.8):
    m = material(name)
    nt = m.node_tree
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = roughness
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    o.location = (300, 0)
    nt.links.new(b.outputs[0], o.inputs[0])
    return m
