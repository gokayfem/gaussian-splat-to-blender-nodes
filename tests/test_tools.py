import copy
import json
import math
from pathlib import Path
import struct
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/gaussian-splat-to-blender-nodes/scripts"))
import cameras
import inspect_asset
import compare
from PIL import Image


class CameraTests(unittest.TestCase):
    def setUp(self):
        self.frame = dict(scale_m_per_unit=0.54, origin_scan=[1.3, -5, 2.6],
                          R_scan_to_world=[[0, -1, 0], [1, 0, 0], [0, 0, 1]])

    def assertVector(self, a, b):
        for x, y in zip(a, b):
            self.assertAlmostEqual(x, y, places=10)

    def test_point_roundtrip(self):
        for p in ([0, 0, 0], [14.3, -2, 8], self.frame["origin_scan"]):
            self.assertVector(p, cameras.transform(cameras.transform(p, self.frame), self.frame, True))

    def test_origin_maps_to_zero(self):
        self.assertVector(cameras.transform(self.frame["origin_scan"], self.frame), [0, 0, 0])

    def test_direction_has_no_origin_or_scale(self):
        self.assertVector(cameras.transform([1, 0, 0], self.frame, direction=True), [0, 1, 0])
        self.assertVector(cameras.transform([0, 1, 0], self.frame, True, True), [1, 0, 0])

    def test_reflection_rejected(self):
        self.frame["R_scan_to_world"] = [[1, 0, 0], [0, 1, 0], [0, 0, -1]]
        with self.assertRaises(ValueError):
            cameras.validate_frame(self.frame)

    def test_shear_rejected(self):
        self.frame["R_scan_to_world"][0][0] = 0.1
        with self.assertRaises(ValueError):
            cameras.validate_frame(self.frame)

    def test_invalid_scale_rejected(self):
        for scale in (0, -1, float("nan"), float("inf")):
            self.frame["scale_m_per_unit"] = scale
            with self.assertRaises(ValueError):
                cameras.validate_frame(self.frame)

    def test_orbit_distance_and_seam(self):
        poses = list(cameras.orbit([0.1, 0.3, 0.7], 3, 30, 24, 640, 480, 50).values())
        self.assertNotEqual(poses[0]["position"], poses[-1]["position"])
        distances = []
        for i, c in enumerate(poses):
            self.assertAlmostEqual(math.dist(c["position"], c["look_at"]), 3)
            distances.append(math.dist(c["position"], poses[(i+1) % 24]["position"]))
        self.assertAlmostEqual(min(distances), max(distances))

    def test_scan_camera_projection_invariance(self):
        c = cameras.orbit([0, 0, .7], 3, 30, 4, 640, 480, 50)["000000"]
        scan = cameras.camera_to_scan(c, self.frame)
        def project(camera, point):
            z = cameras.unit([camera["position"][i]-camera["look_at"][i] for i in range(3)])
            x = cameras.unit(cameras.cross(camera["up"], z))
            y = cameras.cross(z, x)
            v = [point[i]-camera["position"][i] for i in range(3)]
            depth = -cameras.dot(v, z)
            return [cameras.dot(v, x)/depth, cameras.dot(v, y)/depth]
        for point in ([0, 0, 0], [.5, -.2, 1], [-.5, .4, .3]):
            self.assertVector(project(c, point), project(scan, cameras.transform(point, self.frame, True)))

    def test_degenerate_camera_rejected(self):
        c = cameras.orbit([0, 0, 0], 3, 30, 4, 640, 480, 50)["000000"]
        c["up"] = c["position"]
        with self.assertRaises(ValueError):
            cameras.validate_camera(c)

    def test_invalid_orbit_rejected(self):
        for r, e, n in ((0, 30, 4), (3, 90, 4), (3, 30, 1)):
            with self.assertRaises(ValueError):
                cameras.orbit([0, 0, 0], r, e, n, 640, 480, 50)

    def test_garden_frame(self):
        f = json.loads((ROOT / "prompts/garden/data/frame.json").read_text())
        cameras.validate_frame(f)
        data = json.loads((ROOT / "prompts/garden/data/cameras_world.json").read_text())
        for c in data["world"].values():
            cameras.validate_camera(c)


class FileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def write(self, name, data):
        p = self.root / name
        p.write_bytes(data)
        return p

    def test_ply_header_fields(self):
        p = self.write("tiny.ply", b"ply\nformat ascii 1.0\nelement vertex 1\nproperty float x\nproperty float opacity\nend_header\n0 0.5\n")
        r = inspect_asset.inspect(p)
        self.assertEqual(r["elements"][0]["count"], 1)
        self.assertTrue(r["gaussian_fields_present"]["opacity"])
        self.assertFalse(r["gaussian_fields_present"]["scale_0"])

    def test_truncated_ply_rejected(self):
        with self.assertRaises(ValueError):
            inspect_asset.inspect(self.write("bad.ply", b"ply\nformat ascii 1.0\n"))

    def test_negative_ply_count_rejected(self):
        with self.assertRaises(ValueError):
            inspect_asset.inspect(self.write("bad.ply", b"ply\nformat ascii 1.0\nelement vertex -1\nend_header\n"))

    def test_splat_record_count(self):
        self.assertEqual(inspect_asset.inspect(self.write("tiny.splat", bytes(96)))["records"], 3)

    def test_splat_bad_sizes_rejected(self):
        for size in (0, 31, 33):
            with self.assertRaises(ValueError):
                inspect_asset.inspect(self.write("bad.splat", bytes(size)))

    def test_ksplat_main_header(self):
        data = bytearray(5120)
        data[:2] = b"\x00\x01"
        struct.pack_into("<IIIIH", data, 4, 1, 1, 4, 4, 2)
        r = inspect_asset.inspect(self.write("tiny.ksplat", data))
        self.assertEqual((r["splats"], r["compression_level"]), (4, 2))
        self.assertIn("not decoded", r["validation"])

    def test_ksplat_truncated_section_headers_rejected(self):
        data = bytearray(4096)
        data[:2] = b"\x00\x01"
        struct.pack_into("<IIIIH", data, 4, 2, 1, 4, 4, 2)
        with self.assertRaises(ValueError):
            inspect_asset.inspect(self.write("bad.ksplat", data))

    def test_unknown_format_fingerprinted(self):
        p = self.write("file.custom", b"abc")
        r = inspect_asset.inspect(p)
        self.assertEqual(r["format"], "unknown")
        self.assertEqual(r["sha256"], "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")

    def test_compare_pixels_preserved(self):
        a, b = self.root/"a.png", self.root/"b.png"
        Image.new("RGB", (64, 48), "red").save(a)
        Image.new("RGB", (64, 48), "blue").save(b)
        result = compare.compose(a, b)
        self.assertEqual(result.size, (128, 80))
        self.assertEqual(result.getpixel((0, 32)), (255, 0, 0))
        self.assertEqual(result.getpixel((64, 32)), (0, 0, 255))

    def test_compare_size_mismatch_rejected(self):
        a, b = self.root/"a.png", self.root/"b.png"
        Image.new("RGB", (64, 48)).save(a)
        Image.new("RGB", (63, 48)).save(b)
        with self.assertRaises(ValueError):
            compare.compose(a, b)

    def test_compare_filename_mismatch_rejected(self):
        a, b = self.root/"a", self.root/"b"
        a.mkdir(); b.mkdir()
        (a/"000000.png").touch(); (b/"000001.png").touch()
        with self.assertRaises(ValueError):
            compare.pairs(a, b)

    def test_compare_sorted_pairing(self):
        a, b = self.root/"a", self.root/"b"
        a.mkdir(); b.mkdir()
        for name in ("000002.png", "000000.png", "000001.png"):
            (a/name).touch(); (b/name).touch()
        self.assertEqual([x.name for x, _ in compare.pairs(a, b)], ["000000.png", "000001.png", "000002.png"])


if __name__ == "__main__":
    unittest.main()
