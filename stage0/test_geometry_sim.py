from __future__ import annotations

import json
import unittest
from pathlib import Path

import numpy as np

from stage0.geometry_sim import (
    direct_projection_matrix,
    evaluate,
    mirror_projection_matrix,
    project_with_matrix,
    reflect_point,
    triangulate,
)


class GeometrySimulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        config_path = Path(__file__).with_name("layouts.json")
        cls.config = json.loads(config_path.read_text(encoding="utf-8"))

    def test_reflection_across_yz_plane(self) -> None:
        reflected = reflect_point(
            point=[1.0, 2.0, 3.0],
            plane_point=[0.0, 0.0, 0.0],
            plane_normal=[1.0, 0.0, 0.0],
        )
        np.testing.assert_allclose(reflected, [-1.0, 2.0, 3.0], atol=1e-12)

    def test_mirror_projection_matches_reflected_world_point(self) -> None:
        camera = self.config["camera"]
        mirror = self.config["layouts"]["A_symmetric_lateral"]["mirrors"][0]
        point = np.asarray([0.05, 0.3, 0.35])

        reflected = reflect_point(
            point,
            mirror["plane_point_m"],
            mirror["plane_normal"],
        )
        expected, expected_depth = project_with_matrix(
            reflected,
            direct_projection_matrix(camera),
        )
        actual, actual_depth = project_with_matrix(
            point,
            mirror_projection_matrix(camera, mirror),
        )

        np.testing.assert_allclose(actual, expected, atol=1e-9)
        self.assertAlmostEqual(actual_depth, expected_depth, places=9)

    def test_noise_free_direct_and_mirror_triangulation_recovers_point(self) -> None:
        camera = self.config["camera"]
        mirror = self.config["layouts"]["A_symmetric_lateral"]["mirrors"][0]
        point = np.asarray([0.05, 0.3, 0.35])
        matrices = [
            direct_projection_matrix(camera),
            mirror_projection_matrix(camera, mirror),
        ]
        observations = [
            project_with_matrix(point, matrix)[0]
            for matrix in matrices
        ]

        reconstructed = triangulate(observations, matrices)
        np.testing.assert_allclose(reconstructed, point, atol=1e-9)

    def test_candidate_layouts_have_useful_finite_aperture_coverage(self) -> None:
        report = evaluate(self.config)

        for layout_name, layout in report["layouts"].items():
            for view_name, view in layout["views"].items():
                self.assertIsNotNone(
                    view["roi_bounds_px"],
                    msg=f"{layout_name}/{view_name} has no sensor ROI",
                )
                self.assertGreaterEqual(
                    view["coverage_fraction"],
                    0.95,
                    msg=f"{layout_name}/{view_name} has insufficient coverage",
                )

            combined = layout["subsets"]["direct+all_reflections"]
            self.assertGreaterEqual(
                combined["coverage_fraction"],
                0.90,
                msg=f"{layout_name} common coverage is insufficient",
            )

    def test_all_reflections_improve_nominal_p95(self) -> None:
        report = evaluate(self.config)

        for layout in report["layouts"].values():
            subsets = layout["subsets"]
            combined = subsets["direct+all_reflections"][
                "radial_standard_deviation_mm"
            ]["p95"]
            single_reflection_pairs = [
                metrics["radial_standard_deviation_mm"]["p95"]
                for name, metrics in subsets.items()
                if name != "direct+all_reflections"
            ]
            self.assertLess(combined, min(single_reflection_pairs))


if __name__ == "__main__":
    unittest.main()
