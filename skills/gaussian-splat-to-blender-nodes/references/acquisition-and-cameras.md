# Acquisition and camera registration

Record scene/author, asset and viewer URLs, retrieval date, bytes, SHA-256, producer/version,
usage terms and conversions. Keep scans, decoded per-splat arrays and private session data
local. Do not infer dataset rights from an MIT viewer.

## Formats

Use the producer's decoder and confirm field semantics. Common 3DGS training PLY files
contain log-scales, opacity logits, quaternions and spherical harmonics; PLY is only a
container and other exporters differ. Do not exponentiate or sigmoid already-linear data.
A common 32-byte `.splat` layout contains position, scale, RGBA and quantized rotation
without higher-order SH. KSPLAT uses versioned compressed sections; SPZ is different.

The inspector enumerates PLY headers, checks common `.splat` record size, and reads
KSPLAT v0.1 main-header metadata. It does not validate PLY bodies/KSPLAT payloads, decode
positions or infer semantic labels. Unknown formats receive a fingerprint only.

Primary implementations: [GaussianSplats3D](https://github.com/mkkellogg/GaussianSplats3D)
and [3D Gaussian Splatting](https://github.com/graphdeco-inria/gaussian-splatting).

## One frame, two renderers

With column vectors, proper rotation R, scan origin o and positive metric scale s:

```text
world_point = s * R * (scan_point - o)
scan_point = transpose(R) * world_point / s + o
world_direction = R * scan_direction
```

Directions/up receive no translation or metric scale. Check orthonormal rows and determinant
+1. A reflection is not a rotation. Example `frame.json`:

```json
{
  "scale_m_per_unit": 1.0,
  "origin_scan": [0, 0, 0],
  "R_scan_to_world": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
  "assumption": "Scale measured from a known physical dimension"
}
```

World is right-handed, metres and Z-up. Blender cameras look along local -Z with +Y up.
For position p, target t and up u, use z=normalize(p-t), x=normalize(cross(u,z)),
y=cross(z,x) as matrix columns. Reject collinear up/view vectors.

Record **vertical** FOV, dimensions and square pixel aspect. Account for browser viewport
bounds: a cropped screenshot is not necessarily the whole render viewport. Register three
dispersed landmarks, then verify another landmark and an opposite view. Check projected
pixels before changing geometry. Lock the camera while correcting a part.

Scale may be an assumption: Garden uses a table height of 0.74 m. Label estimates and
inferred hidden surfaces. Splat floaters, transparent backsides and unseen regions can be
capture artifacts. A camera manifest proves repeatability, not ground-truth calibration.
