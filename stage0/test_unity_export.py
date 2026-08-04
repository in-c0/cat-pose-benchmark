from __future__ import annotations

import json
import unittest
from pathlib import Path

import numpy as np

from stage0.compare_reports import compare_values
from stage0.export_unity_scene_v2 import export_scene


class UnityExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).parents[1]
        cls.config = json.loads(
            (Path(__file__).with_name("layouts.json")).read_text(encoding="utf-8")
        )

    def test_committed_unity_scene_matches_exporter(self) -> None:
        expected = json.loads(
            (
                self.root
                / "unity-viewer"
                / "Assets"
                / "StreamingAssets"
                / "stage0-scene-v2.json"
            ).read_text(encoding="utf-8")
        )
        actual = export_scene(self.config, "A_symmetric_lateral")
        self.assertEqual(compare_values(expected, actual), [])

    def test_reflected_waypoints_lie_on_mirror_planes(self) -> None:
        scene = export_scene(self.config, "A_symmetric_lateral")
        mirrors = {mirror["name"]: mirror for mirror in scene["mirrors"]}

        for ray in scene["rays"]:
            if ray["kind"] != "reflected":
                continue
            mirror_name = ray["name"].removeprefix("reflected-centre-ray-")
            mirror = mirrors[mirror_name]
            waypoint = ray["points_m"][1]
            point = np.asarray([waypoint["x"], waypoint["y"], waypoint["z"]])
            plane_point = np.asarray(
                [
                    mirror["plane_point_m"]["x"],
                    mirror["plane_point_m"]["y"],
                    mirror["plane_point_m"]["z"],
                ]
            )
            normal = np.asarray(
                [
                    mirror["plane_normal"]["x"],
                    mirror["plane_normal"]["y"],
                    mirror["plane_normal"]["z"],
                ]
            )
            normal /= np.linalg.norm(normal)
            self.assertAlmostEqual(float(np.dot(normal, point - plane_point)), 0.0, places=8)

    def test_scene_uses_explicit_vector_objects(self) -> None:
        scene = export_scene(self.config, "A_symmetric_lateral")
        self.assertEqual(
            set(scene["representative_point_m"]),
            {"x", "y", "z"},
        )
        self.assertEqual(set(scene["mirrors"][0]["size_m"]), {"x", "y"})
        self.assertIsInstance(scene["rays"][0]["points_m"][0], dict)


if __name__ == "__main__":
    unittest.main()
