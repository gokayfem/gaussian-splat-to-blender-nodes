"""Small builder for native Blender node trees (Geometry Nodes and Shader Nodes).

Every node group in the project is written against this module so that graphs are built, linked, laid out and
inspected the same way. It runs inside Blender (``bpy``); nothing here is evaluated outside it.

    from nodekit.graph import Graph
    g = Graph("SS Example", kind="GEOMETRY")
    geo = g.input("Geometry", "GEOMETRY")
    width = g.input("Width", "FLOAT", 4.0, min=0.5, max=20, subtype="DISTANCE", panel="Street",
                    desc="Curb-to-curb width of the cobbled road")
    grid = g.node("GeometryNodeMeshGrid", **{"Size X": width, "Vertices X": 32})
    g.output("Geometry", "GEOMETRY", grid["Mesh"])
    g.finish()            # auto-layout + frames

Values passed for inputs may be: a constant, a socket, a ``Node`` (its first enabled output), or ``None`` (leave).
Sockets are found by name among *enabled* sockets; use ``"Name#k"`` for the k-th enabled socket with that name
(Math nodes have three inputs named "Value"), or an integer index into the enabled list.
"""
import bpy

SOCKET_TYPES = {
    "FLOAT": "NodeSocketFloat", "INT": "NodeSocketInt", "BOOL": "NodeSocketBool", "VECTOR": "NodeSocketVector",
    "COLOR": "NodeSocketColor", "GEOMETRY": "NodeSocketGeometry", "MATERIAL": "NodeSocketMaterial",
    "OBJECT": "NodeSocketObject", "COLLECTION": "NodeSocketCollection", "STRING": "NodeSocketString",
    "ROTATION": "NodeSocketRotation", "SHADER": "NodeSocketShader", "MENU": "NodeSocketMenu",
    "MATRIX": "NodeSocketMatrix",
}
TREE_TYPES = {"GEOMETRY": "GeometryNodeTree", "SHADER": "ShaderNodeTree", "COMPOSITOR": "CompositorNodeTree"}


def _enabled(sockets):
    return [s for s in sockets if s.enabled]


def find_socket(sockets, key):
    """Resolve ``key`` (name, "name#k" or index) against the enabled sockets of a node."""
    live = _enabled(sockets)
    if isinstance(key, int):
        return live[key]
    name, _, k = key.partition("#")
    hits = [s for s in live if s.name == name] or [s for s in live if s.identifier == name]
    if not hits:
        raise KeyError(f"no enabled socket {key!r}; have {[s.name for s in live]}")
    return hits[int(k) if k else 0]


_ONCE = {}


def once(build):
    """Decorator for builders of SHARED groups (used by several modules). Rebuilding a group clears its
    interface, which silently unlinks every group node already using it, so a shared group is built once per
    Blender session and the same tree is returned afterwards."""
    def wrapper(*a, **k):
        tree = _ONCE.get(build)
        if tree is not None:
            try:
                tree.name                      # still alive (not freed by a factory reset)
                return tree
            except ReferenceError:
                pass
        tree = _ONCE[build] = build(*a, **k)
        return tree
    wrapper.__doc__, wrapper.__name__ = build.__doc__, build.__name__
    return wrapper


class Node:
    """Thin wrapper: ``n["Out"]`` is an output socket, ``n.i("In")`` an input socket."""

    def __init__(self, graph, bnode):
        self.g, self.b = graph, bnode

    def __getitem__(self, key):
        return find_socket(self.b.outputs, key)

    def i(self, key):
        return find_socket(self.b.inputs, key)

    @property
    def out(self):
        return _enabled(self.b.outputs)[0]

    def set(self, **inputs):
        for k, v in inputs.items():
            self.g.connect(v, self.i(k))
        return self


class Graph:
    def __init__(self, name, kind="GEOMETRY", description="", modifier=False):
        """Create (or clear and rebuild) the node group ``name``. ``kind`` is GEOMETRY or SHADER."""
        tree_type = TREE_TYPES[kind]
        ng = bpy.data.node_groups.get(name)
        if ng is None or ng.bl_idname != tree_type:
            ng = bpy.data.node_groups.new(name, tree_type)
        ng.nodes.clear()
        ng.interface.clear()
        ng.description = description
        if kind == "GEOMETRY" and modifier and hasattr(ng, "is_modifier"):
            ng.is_modifier = True
        self.kind, self.nt = kind, ng
        self._panels = {}
        self._gin = ng.nodes.new("NodeGroupInput")
        self._gout = ng.nodes.new("NodeGroupOutput")
        self._frames = []          # (label, [nodes], color)
        self._current_frame = None

    # ---- interface -------------------------------------------------------------------------------------------
    def _panel(self, name):
        if name is None:
            return None
        if name not in self._panels:
            self._panels[name] = self.nt.interface.new_panel(name)
        return self._panels[name]

    def input(self, name, stype, default=None, min=None, max=None, desc="", panel=None, subtype=None,
              hide_value=False, menu=None):
        """Declare a group input and return its socket on the Group Input node."""
        s = self.nt.interface.new_socket(name, in_out="INPUT", socket_type=SOCKET_TYPES[stype],
                                         parent=self._panel(panel))
        s.description = desc
        if subtype and hasattr(s, "subtype"):
            s.subtype = subtype
        if default is not None and hasattr(s, "default_value"):
            s.default_value = default
        if min is not None and hasattr(s, "min_value"):
            s.min_value = min
        if max is not None and hasattr(s, "max_value"):
            s.max_value = max
        if hide_value:
            s.hide_value = True
        return self._gin.outputs[s.identifier]

    def output(self, name, stype, value=None, desc=""):
        s = self.nt.interface.new_socket(name, in_out="OUTPUT", socket_type=SOCKET_TYPES[stype])
        s.description = desc
        sock = self._gout.inputs[s.identifier]
        if value is not None:
            self.connect(value, sock)
        return sock

    # ---- nodes -----------------------------------------------------------------------------------------------
    def node(self, bl_idname, label=None, props=None, **inputs):
        """Add a node. ``props`` sets node properties (operation, data_type, domain...) BEFORE inputs are
        resolved, because properties change which sockets are enabled. Keyword inputs use socket names; names
        with spaces go through ``**{"Size X": ...}``."""
        b = self.nt.nodes.new(bl_idname)
        for k, v in (props or {}).items():
            setattr(b, k, v)
        if label:
            b.label = label
        n = Node(self, b)
        for k, v in inputs.items():
            self.connect(v, n.i(k))
        if self._current_frame is not None:
            self._current_frame[1].append(b)
        return n

    def group(self, tree, label=None, **inputs):
        """Instance another node group (a ``Graph`` or a bpy node group)."""
        tree = tree.nt if isinstance(tree, Graph) else tree
        idname = {"GEOMETRY": "GeometryNodeGroup", "SHADER": "ShaderNodeGroup",
                  "COMPOSITOR": "CompositorNodeGroup"}[self.kind]
        b = self.nt.nodes.new(idname)
        b.node_tree = tree
        b.label = label or ""
        n = Node(self, b)
        for k, v in inputs.items():
            self.connect(v, n.i(k))
        if self._current_frame is not None:
            self._current_frame[1].append(b)
        return n

    # ---- zones -----------------------------------------------------------------------------------------------
    ZONES = {"SIMULATION": ("GeometryNodeSimulationInput", "GeometryNodeSimulationOutput", "state_items"),
             "REPEAT": ("GeometryNodeRepeatInput", "GeometryNodeRepeatOutput", "repeat_items"),
             "FOREACH": ("GeometryNodeForeachGeometryElementInput", "GeometryNodeForeachGeometryElementOutput",
                         "main_items")}

    def zone(self, kind, items=(), label=None):
        """A paired zone. ``items`` are (socket_type, name) state/repeat/main items added after the default
        Geometry item; e.g. ``zin, zout = g.zone("SIMULATION", [("FLOAT", "Age")])``. Inside the zone, read state
        from ``zin[name]`` and write it to ``zout.i(name)``; after the zone, read ``zout[name]``. Simulation zones
        expose ``zin["Delta Time"]``; repeat zones take ``zin.i("Iterations")``."""
        in_id, out_id, coll = self.ZONES[kind]
        zin = self.node(in_id, label and f"{label} (in)")
        zout = self.node(out_id, label and f"{label} (out)")
        zin.b.pair_with_output(zout.b)
        store = getattr(zout.b, coll)
        for stype, name in items:
            store.new(stype, name)
        return zin, zout

    def connect(self, value, to_socket):
        if value is None:
            return
        if isinstance(value, Node):
            value = value.out
        if isinstance(value, bpy.types.NodeSocket):
            self.nt.links.new(value, to_socket)
            return
        if isinstance(value, bpy.types.ID) or value is None:
            to_socket.default_value = value
            return
        if isinstance(value, (list, tuple)):
            dv = to_socket.default_value
            n = len(dv)
            v = list(value) + [1.0] * (n - len(value))
            to_socket.default_value = v[:n]
            return
        to_socket.default_value = value

    # ---- math shorthands (the commonest nodes, kept terse so graphs read like formulas) -----------------------
    def math(self, op, a=None, b=None, c=None, label=None, clamp=False):
        mid = "ShaderNodeMath"
        n = self.node(mid, label, props={"operation": op, "use_clamp": clamp})
        for k, v in ((0, a), (1, b), (2, c)):
            if v is not None and k < len(_enabled(n.b.inputs)):
                self.connect(v, _enabled(n.b.inputs)[k])
        return n

    def vmath(self, op, a=None, b=None, c=None, label=None, scale=None):
        n = self.node("ShaderNodeVectorMath", label, props={"operation": op})
        ins = [s for s in _enabled(n.b.inputs) if s.name != "Scale"]
        for k, v in enumerate((a, b, c)):
            if v is not None and k < len(ins):
                self.connect(v, ins[k])
        if scale is not None:
            self.connect(scale, n.i("Scale"))
        return n

    def combine(self, x=0.0, y=0.0, z=0.0, label=None):
        return self.node("ShaderNodeCombineXYZ", label, X=x, Y=y, Z=z)

    def separate(self, v, label=None):
        return self.node("ShaderNodeSeparateXYZ", label, Vector=v)

    def mix(self, fac, a, b, data_type="FLOAT", label=None, clamp=True):
        n = self.node("ShaderNodeMix", label, props={"data_type": data_type, "clamp_factor": clamp})
        n.set(Factor=fac, A=a, B=b)
        return n

    def map_range(self, v, a0, a1, b0, b1, clamp=True, interp="LINEAR", label=None):
        n = self.node("ShaderNodeMapRange", label, props={"interpolation_type": interp, "clamp": clamp})
        return n.set(Value=v, **{"From Min": a0, "From Max": a1, "To Min": b0, "To Max": b1})

    def value(self, v, label=None):
        n = self.node("ShaderNodeValue", label)
        n.b.outputs[0].default_value = v
        return n

    # ---- organisation ----------------------------------------------------------------------------------------
    def frame(self, label, color=None):
        """Context manager: nodes created inside are wrapped in a labelled frame.

            with g.frame("Parcels: split each side into houses"):
                ...
        """
        graph = self

        class _F:
            def __enter__(self_):
                graph._current_frame = (label, [], color)
                return self_

            def __exit__(self_, *a):
                graph._frames.append(graph._current_frame)
                graph._current_frame = None

        return _F()

    def split_inputs(self):
        """Give every frame its own Group Input node with only the sockets that frame uses (the rest hidden),
        so a graph with many inputs reads frame by frame instead of as one fan of long links."""
        gin = self._gin
        for label, nodes, color in self._frames:
            members = set(nodes)
            links = [l for l in self.nt.links if l.from_node == gin and l.to_node in members]
            if not links:
                continue
            local = self.nt.nodes.new("NodeGroupInput")
            local.label = "Inputs"
            nodes.insert(0, local)
            for l in links:
                src, dst = local.outputs[l.from_socket.identifier], l.to_socket
                self.nt.links.remove(l)
                self.nt.links.new(src, dst)
            for s in local.outputs:
                s.hide = not s.is_linked
        if not any(s.is_linked for s in gin.outputs):
            self.nt.nodes.remove(gin)
            self._gin = None
            return
        for s in gin.outputs:
            s.hide = not s.is_linked

    def finish(self, split_inputs=True):
        if split_inputs:
            self.split_inputs()
        groups = [nodes for _, nodes, _ in self._frames if nodes]
        layout(self.nt, self._gin, self._gout, groups)
        for label, nodes, color in self._frames:
            if not nodes:
                continue
            f = self.nt.nodes.new("NodeFrame")
            f.label = label
            f.label_size = 18
            f.shrink = True
            if color:
                f.use_custom_color, f.color = True, color
            for b in nodes:
                b.parent = f
        return self.nt


def _node_h(n):
    """Estimated drawn height: header, one row per socket, extra rows for vector defaults and option widgets."""
    rows = len([s for s in _enabled(n.outputs) if not s.hide]) + len([s for s in _enabled(n.inputs) if not s.hide])
    rows += sum(2 for s in _enabled(n.inputs) if not s.is_linked and s.type in {"VECTOR", "ROTATION"})
    props = [p for p in n.bl_rna.properties if p.type == "ENUM" and not p.is_readonly
             and p.identifier not in {"warning_propagation", "color_tag"}]
    return 50 + 22 * rows + 26 * len(props)


def _depths(nodes, preds):
    depth = {}

    def d(n, stack=()):
        if n in depth:
            return depth[n]
        if n in stack:
            return 0
        ps = [p for p in preds[n] if p in preds]
        depth[n] = 0 if not ps else 1 + max(d(p, stack + (n,)) for p in ps)
        return depth[n]

    for n in nodes:
        d(n)
    return depth


def layout(nt, gin=None, gout=None, groups=(), dx=60, dy=40, gap=120):
    """Block layout: each frame is laid out internally by longest path (columns), then frames and loose nodes
    are placed as blocks in columns by their own longest path, so frames never overlap and data flows left to
    right. Group Input sits first, Group Output last."""
    nodes = [n for n in nt.nodes if n.bl_idname != "NodeFrame"]
    preds = {n: set() for n in nodes}
    for l in nt.links:
        if l.from_node in preds and l.to_node in preds:
            preds[l.to_node].add(l.from_node)
    unit_of, units = {}, []
    for grp in groups:
        u = [n for n in grp if n in preds]
        if u:
            units.append(u)
            for n in u:
                unit_of[n] = len(units) - 1
    for n in nodes:
        if n not in unit_of:
            units.append([n])
            unit_of[n] = len(units) - 1
    # unit graph
    upreds = {i: set() for i in range(len(units))}
    for n in nodes:
        for p in preds[n]:
            if unit_of[p] != unit_of[n]:
                upreds[unit_of[n]].add(unit_of[p])
    udepth = _depths(list(upreds), upreds)
    if gin is not None:
        udepth[unit_of[gin]] = 0
    if gout is not None:
        udepth[unit_of[gout]] = max(udepth.values(), default=0) + 1
    # internal layout of each unit, relative coordinates; returns (w, h)
    size, rel = {}, {}
    for i, u in enumerate(units):
        local = {n: {p for p in preds[n] if p in u} for n in u}
        ld = _depths(u, local)
        cols = {}
        for n in u:
            cols.setdefault(ld[n], []).append(n)
        x, w_tot, h_max = 0, 0, 0
        for c in sorted(cols):
            y, w = 0, 0
            for n in cols[c]:
                rel[n] = (x, y)
                y -= _node_h(n) + dy
                w = max(w, n.width)
            h_max = max(h_max, -y)
            x += w + dx
        size[i] = (x - dx, h_max)
    ucols = {}
    for i in range(len(units)):
        ucols.setdefault(udepth[i], []).append(i)
    X = 0
    placed_y = {}
    for c in sorted(ucols):
        us = ucols[c]
        # order blocks by the mean height of the blocks feeding them, so links cross less
        us.sort(key=lambda i: -(sum(placed_y.get(p, 0) for p in upreds[i]) / len(upreds[i])) if upreds[i] else 0)
        Y = 0
        for i in us:
            placed_y[i] = Y
            for n in units[i]:
                rx, ry = rel[n]
                n.location = (X + rx, Y + ry)
            Y -= size[i][1] + gap
        X += max(size[i][0] for i in us) + gap * 1.5
