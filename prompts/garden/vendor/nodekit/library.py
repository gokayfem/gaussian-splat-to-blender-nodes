"""The node-group library registry.

Every reusable group in `library/` is a builder function decorated with `@nodegroup`. The decorator records its
metadata (for `nodes_tools.py search` / `index`, which read it statically with `ast`, without Blender) and makes
the builder build-once-per-session (rebuilding a group that other groups already instance would unlink them).

    from nodekit.graph import Graph
    from nodekit.library import nodegroup

    @nodegroup("NK Curve Frame", kind="GEOMETRY", tags=["curve", "placement"],
               use="streets, fences, rails, anything placed along a path")
    def curve_frame():
        '''(s, d, h) along a curve to world position and orientation.'''
        g = Graph("NK Curve Frame", description=curve_frame.__doc__.strip().splitlines()[0])
        ...
        return g.finish()

Rules (checked by `nodes_tools.py check`):
- the group name passed to the decorator equals the Graph name, and starts with "NK ";
- the docstring's first line is a one-sentence summary; `use` names concrete subjects;
- a builder may call builders only from modules listed before its own in library/__init__.py MODULE_ORDER.
"""
from nodekit.graph import once

REGISTRY = {}          # name -> metadata dict (filled when a library module is imported)


def nodegroup(name, kind="GEOMETRY", tags=(), use=""):
    def deco(fn):
        built = once(fn)
        built.nodegroup = {"name": name, "kind": kind, "tags": list(tags), "use": use,
                           "summary": (fn.__doc__ or "").strip().splitlines()[0] if fn.__doc__ else "",
                           "module": fn.__module__, "builder": fn.__name__}
        REGISTRY[name] = dict(built.nodegroup, build=built)
        return built
    return deco


def build_all(modules=None):
    """Import every library module (in MODULE_ORDER) and build every registered group. Returns {name: tree}."""
    import importlib, importlib.util
    from library import MODULE_ORDER
    for m in modules or MODULE_ORDER:
        if importlib.util.find_spec(f"library.{m}") is not None:     # modules not written yet are skipped
            importlib.import_module(f"library.{m}")
    return {name: meta["build"]() for name, meta in REGISTRY.items()}
