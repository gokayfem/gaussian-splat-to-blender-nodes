"""Portable projection tests: no downloaded scan and no scene-specific object names."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image

SCRIPTS = Path(__file__).resolve().parents[1]/"skills/gaussian-splat-to-blender-nodes/scripts"
sys.path.insert(0, str(SCRIPTS))
from projection_config import load_config, options, sha256, validate_rule
from projection_core import (bilinear, blend_samples, finish_texture, linear_to_srgb,
                             prepare_view, project, project_surface, reject_samples,
                             sample_view, srgb_to_linear)


def fixture():
    camera = dict(position=[0, 0, 3], look_at=[0, 0, 0], up=[0, 1, 0],
                  fov_y_deg=50, width=16, height=16)
    view = dict(camera=camera, rgb=np.full((16, 16, 3), [200, 100, 50], np.uint8),
                depth=np.full((16, 16), 3.0), ids=np.full((16, 16), 7))
    target = dict(name="panel", object="Arbitrary Panel", object_id=7, texture_size=8,
                  projection=dict(border=1, mix_feather=0, padding=0))
    return view, target


class ProjectionTests(unittest.TestCase):
    def test_camera_rigid_transform_invariance(self):
        view, _ = fixture()
        points = np.array([[0.0, 0, 0], [0.2, -0.3, 0.1]])
        expected = project(view["camera"], points)
        # A different project's translated/rotated coordinate system must give identical pixels.
        rotation = np.array([[0, -1, 0], [0, 0, 1], [-1, 0, 0]])
        offset = np.array([13.5, -20, 4.25])
        camera = copy.deepcopy(view["camera"])
        for key in ("position", "look_at"):
            camera[key] = rotation @ camera[key] + offset
        camera["up"] = rotation @ camera["up"]
        actual = project(camera, points @ rotation.T + offset)
        for i in (1, 2, 4, 5):
            np.testing.assert_allclose(actual[i], expected[i], atol=1e-10)
        self.assertEqual(expected[4][0], 8)
        self.assertEqual(expected[5][0], 8)

    def test_linear_light_interpolation(self):
        rgb = np.array([[[0, 0, 0], [1, 1, 1]], [[0, 0, 0], [1, 1, 1]]], float)
        np.testing.assert_allclose(bilinear(srgb_to_linear(rgb), np.array([1.]), np.array([1.])), .5)
        levels = np.linspace(0, 1, 100)
        np.testing.assert_allclose(linear_to_srgb(srgb_to_linear(levels)), levels, atol=1e-7)
        view, target = fixture()
        view["rgb"][:, 8:] = 255; view["rgb"][:, :8] = 0
        _, colors, _ = sample_view(np.array([[0, 0, 0]]), np.array([[0, 0, 1]]),
                                   prepare_view(view, target, options(target)), target, options(target))
        np.testing.assert_allclose(colors, .5)

    def test_occlusion_and_source_rejection(self):
        view, target = fixture()
        pos = np.zeros((1, 1, 3)); normals = np.array([[[0, 0, 1.]]])
        valid, slots = np.ones((1, 1), bool), np.zeros((1, 1), int)
        def state(v):
            return project_surface(pos, normals, valid, slots, [v], target)[1].item()
        self.assertEqual(state(view), 1)
        hidden = dict(view, depth=np.ones((16, 16)))
        self.assertEqual(state(hidden), 3)
        foreign = dict(view, ids=np.full((16, 16), 11))
        self.assertEqual(state(foreign), 3)
        masked = dict(view, allowed=np.zeros((16, 16), bool))
        self.assertEqual(state(masked), 2)
        # Reject a neighboring pixel too: bilinear interpolation must not bleed across it.
        allowed = np.ones((16, 16), bool); allowed[7, 7] = False
        self.assertEqual(state(dict(view, allowed=allowed)), 2)

    def test_scoped_rejection_has_no_scene_constants(self):
        points = np.array([[31, 10, -4], [0, 0, 0], [31, 10, -4]])
        colors = np.array([[.1, .8, .3], [.1, .8, .3], [.8, .1, .1]])
        rule = dict(bounds_min=[30, 9, -5], bounds_max=[32, 11, -3], channel_ratios=[["g", "r", 1.5]])
        np.testing.assert_array_equal(reject_samples(points, colors, [rule]), [True, False, False])
        np.testing.assert_array_equal(reject_samples(points, colors, []), False)

    def test_robust_consensus_suppresses_highlight(self):
        weights = np.ones((4, 1))
        colors = np.array([[[.2]*3]]*3 + [[[1.]*3]])
        weighted, _ = blend_samples(weights, colors, "weighted", np.array([.3]))
        robust, covered = blend_samples(weights, colors, "robust", np.array([.3]))
        self.assertTrue(covered.item())
        self.assertLess(abs(robust[0, 0]-.2), abs(weighted[0, 0]-.2))
        empty, covered = blend_samples(weights*0, colors, "robust", np.array([.3]))
        self.assertFalse(covered.item()); self.assertTrue(np.isfinite(empty).all())

    def test_unseen_never_gets_capture_and_materials_do_not_cross_feather(self):
        _, target = fixture()
        target["projection"].update(mix_feather=2, padding=3)
        state = np.array([[1, 1, 3, 3], [1, 1, 3, 0]], np.uint8)
        slots = np.array([[2, 2, 9, 9], [2, 2, 9, -1]])
        rgb, mix, padded = finish_texture(np.full((2, 4, 3), .2), state, slots, target)
        np.testing.assert_allclose(mix[state == 1], 1)  # Other material's fallback does not dilute this one.
        np.testing.assert_array_equal(mix[state == 3], 0)
        self.assertEqual(padded[-1, -1], 4)
        self.assertTrue(np.isfinite(rgb).all())
        _, empty_mix, _ = finish_texture(np.zeros((2, 4, 3)), np.full((2, 4), 3), slots, target)
        self.assertFalse(empty_mix.any())

    def test_albedo_requires_irradiance(self):
        _, target = fixture(); target["appearance"] = "estimated_albedo"
        color = np.full((2, 2, 3), .2); state = np.ones((2, 2), np.uint8); slots = np.zeros((2, 2), int)
        with self.assertRaises(ValueError):
            finish_texture(color, state, slots, target)
        rgb, _, _ = finish_texture(color, state, slots, target, np.full_like(color, .5))
        np.testing.assert_allclose(srgb_to_linear(rgb), .4, atol=1e-7)

    def test_rule_validation_before_baking(self):
        validate_rule(dict(bounds_min=[-1, -1, -1], bounds_max=[1, 1, 1]))
        for rule in (dict(bounds_min=[0, 0, 2], bounds_max=[1, 1, 1]),
                     dict(bounds_min=[0, 0, 0], bounds_max=[1, 1, 1], rgb_min=[0, 2, 0]),
                     dict(bounds_min=[0, 0, 0], bounds_max=[1, 1, 1], channel_ratios=[["x", "r", 2]])):
            with self.assertRaises(ValueError):
                validate_rule(rule)

    def test_config_and_cli_fingerprints(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); prep = root/"prepared"; (prep/"depth").mkdir(parents=True)
            view, target = fixture()
            cfg = dict(schema_version=1, targets=[target], views={"front": dict(camera=view["camera"], image="capture.png")})
            config = root/"mapping.json"; config.write_text(json.dumps(cfg))
            self.assertEqual(load_config(config)[0]["targets"][0]["object"], "Arbitrary Panel")
            Image.fromarray(view["rgb"]).save(root/"capture.png")
            np.save(prep/"depth/front.npy", view["depth"]); np.save(prep/"depth/front_id.npy", view["ids"])
            arrays = dict(position=np.zeros((8, 8, 3)), normal=np.broadcast_to([0., 0, 1], (8, 8, 3)),
                          valid=np.ones((8, 8), bool), material=np.zeros((8, 8), int))
            for key, value in arrays.items():
                np.save(prep/f"panel_{key}.npy", value)
            manifest = dict(config_sha256=sha256(config), source_blend_sha256="synthetic-fixture",
                            files={str(p.relative_to(prep)): sha256(p) for p in prep.rglob("*.npy")})
            (prep/"prepared.json").write_text(json.dumps(manifest))
            cmd = [sys.executable, str(SCRIPTS/"project_textures.py"), "--config", str(config), "--prepared", str(prep), "--out", str(root/"mapped")]
            result = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads((root/"mapped/projection.json").read_text())
            self.assertEqual(report["targets"]["panel"]["direct"], 1)
            self.assertEqual(report["captures"]["front"]["image_sha256"], sha256(root/"capture.png"))
            cfg["targets"][0]["object"] = "Another Project Object"
            config.write_text(json.dumps(cfg))
            result = subprocess.run(cmd[:-1] + [str(root/"changed")], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Config changed", result.stderr)
            cfg["targets"][0]["projection"]["typo"] = 1; config.write_text(json.dumps(cfg))
            with self.assertRaisesRegex(ValueError, "Unknown projection"):
                load_config(config)


if __name__ == "__main__":
    unittest.main()
