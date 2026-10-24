#!/usr/bin/env python3
"""Fingerprint a local asset and inspect common splat container metadata.

This is a header/record-layout inspector, NOT a semantic decoder or a mesh converter.
PLY body values and KSPLAT bucket/payload integrity are not validated.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()


def inspect(path):
    path = Path(path)
    size = path.stat().st_size
    result = dict(filename=path.name, bytes=size, sha256=sha256(path))
    suffix = path.suffix.lower()
    if suffix == ".ply":
        with path.open("rb") as f:
            header = bytearray()
            while len(header) < 1024*1024:
                line = f.readline(4096)
                if not line:
                    raise ValueError("PLY header has no end_header")
                header.extend(line)
                if line.strip() == b"end_header":
                    break
            else:
                raise ValueError("PLY header exceeds 1 MiB")
        lines = header.decode("ascii").splitlines()
        if lines[0] != "ply":
            raise ValueError("Invalid PLY magic")
        elements, current, fmt = [], None, None
        for line in lines[1:]:
            p = line.split()
            if not p:
                continue
            if p[0] == "format":
                if len(p) != 3 or p[1] not in ("ascii", "binary_little_endian", "binary_big_endian") or p[2] != "1.0":
                    raise ValueError("Unsupported PLY format")
                fmt = p[1]
            elif p[0] == "element":
                if len(p) != 3 or int(p[2]) < 0:
                    raise ValueError("Invalid PLY element count")
                current = dict(name=p[1], count=int(p[2]), properties=[])
                elements.append(current)
            elif p[0] == "property":
                if current is None:
                    raise ValueError("PLY property without element")
                current["properties"].append(" ".join(p[1:]))
        if fmt is None or not elements:
            raise ValueError("Incomplete PLY header")
        props = {p.split()[-1] for e in elements if e["name"] == "vertex" for p in e["properties"]}
        result.update(format="ply", encoding=fmt, header_bytes=len(header), elements=elements,
                      gaussian_fields_present={k: k in props for k in ("opacity", "scale_0", "rot_0", "f_dc_0")},
                      validation="Header only; field conventions and body require the producer's decoder")
    elif suffix == ".splat":
        if size == 0 or size % 32:
            raise ValueError("Expected nonempty 32-byte records for the common .splat layout")
        result.update(format="splat", records=size//32, record_bytes=32,
                      validation="Size only; .splat has no magic/version marker. Confirm producer/layout")
    elif suffix == ".ksplat":
        with path.open("rb") as f:
            h = f.read(4096)
        if len(h) < 4096 or h[:2] != b"\x00\x01":
            raise ValueError("Only GaussianSplats3D KSPLAT v0.1 headers are supported")
        max_sections, sections, max_splats, splats = struct.unpack_from("<IIII", h, 4)
        level = struct.unpack_from("<H", h, 20)[0]
        if not 0 < sections <= max_sections or splats > max_splats or level not in (0, 1, 2):
            raise ValueError("Inconsistent KSPLAT header")
        if size < 4096 + 1024*max_sections:
            raise ValueError("Truncated KSPLAT section headers")
        result.update(format="ksplat", version="0.1", sections=sections, splats=splats,
                      compression_level=level, validation="Main header only; section records and payload not decoded")
    else:
        result.update(format="unknown", validation="Fingerprint only; use the producer's decoder")
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("asset", type=Path)
    p.add_argument("--out", type=Path)
    a = p.parse_args()
    output = json.dumps(inspect(a.asset), indent=2) + "\n"
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(output)
    print(output, end="")


if __name__ == "__main__":
    main()
