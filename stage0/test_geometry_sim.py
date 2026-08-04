from __future__ import annotations

import json
import unittest
from pathlib import Path

import numpy as np

from stage0.geometry_sim import (
    evaluate,
    projection_matrix,
    project_point,
    reflect_point,
    triangulate,
    world_to_camera_rotation,
)


class GeometrySimulationTests(unittest.TestCase):
    def test_reflection_across_yz_plane(self) -> None:
        reflected = reflect_point(
            point=[1.0, 2.0, 3.0],
            plane_point=[0.0, 0.0, 0.0],
            plane_normal=[1.0, 0.0, 0.0],
        )
        np.testing.assert_allclose(reflected, [-1.0, 2.0, 3.0], atol=1e-12)

    def test_noise_free_triangulation_recovers_point(self) -> None:
        intrinsics = (1000.0, 1000.0, 640.0, 360.0)
        target = np.asarray([0.0, 2.0, 0.5])
        point = np.asarray([0.1, 1.3, 0.35])
        centres = [
            np.asarray([-0.5, 0.0, 0.5]),
            np.asarray([0.5, 0.0, 0.5]),
        ]
        rotations = [
            world_to_camera_rotation(centre, target)
            for centre in centres
        ]
        matrices = [
            projection_matrix(centre, rotation, intrinsics)
            for centre, rotation in zip(centres, rotations)
        ]
        observations = [
            project_point(point, centre, rotation, intrinsics)
            for centre, rotation in zip(centres, rotations)
        ]

        reconstructed = triangulate(observations, matrices)
        np.testing.assert_allclose(reconstructed, point, atol=1e-9)

    def test_all_reflections_improve_nominal_p95(self) -> None:
        config_path = Path(__file__).with_name("layouts.json")
        config = json.loads(config_path.read_text(encoding="utf-8"))
        report = evaluate(config)

        for layout in report["layouts"].values():
            subsets = layout["subsets"]
            combined = subsets["direct+all_reflections"][
                "radial_standard_deviation_mm"
            ]["p95"]
            single_view_pairs = [
                metrics["radial_standard_deviation_mm"]["p95"]
                for name, metrics in subsets.items()
                if name != "direct+all_reflections"
            ]
            self.assertLess(combined, min(single_view_pairs))


if __name__ == "__main__":
    unittest.main()
