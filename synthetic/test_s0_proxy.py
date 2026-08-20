from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from fusion.v1_pose_package import validate_pose_package
from synthetic.s0_proxy import (
    DT_SECONDS,
    BUNDLE_VERSION,
    FRAME_COUNT,
    build_bundle,
    build_synthetic_m1_candidate,
    camera_to_image,
    image_to_camera,
    root_acceleration_world,
    root_velocity_world,
    validate_bundle,
    visibility_for_landmark,
    world_to_camera,
    world_to_image,
)

FIXTURE_MANIFEST = Path(__file__).with_name("fixtures") / "s0_proxy_v0.json"
EXPECTED_SHA256 = "e428bbe52403608737321772a5b6d3c8c23a404db5a7286be8cfd93a1c47ad3e"


def _load_fixture_manifest() -> dict:
    return json.loads(FIXTURE_MANIFEST.read_text(encoding="utf-8"))


def _obs(frame: dict, semantic_name: str, coordinate_space: str | None = None) -> dict:
    matches = [
        item
        for item in frame["observations"]
        if item["semantic_name"] == semantic_name
        and (coordinate_space is None or item["coordinate_space"] == coordinate_space)
    ]
    if len(matches) != 1:
        raise AssertionError((semantic_name, coordinate_space, len(matches)))
    return matches[0]


def _regression_manifest(bundle: dict) -> dict:
    return {
        "fixture_kind": "S0A-canonical-regression-manifest-v0",
        "bundle_version": bundle["bundle_version"],
        "payload_sha256": bundle["payload_sha256"],
        "frame_count": bundle["frame_count"],
        "observation_count_total": sum(
            len(frame["observations"]) for frame in bundle["frames"]
        ),
        "left_ear_visibility": [
            _obs(frame, "left_ear_tip", "world")["visibility"][0]
            for frame in bundle["frames"]
        ],
        "left_hind_contact": [
            _obs(frame, "left_hind_paw_center_floor_contact")["mean"]
            for frame in bundle["frames"]
        ],
        "root_x_m": [
            frame["subject_root_world_m"][0] for frame in bundle["frames"]
        ],
        "nose_image_frame0_px": _obs(
            bundle["frames"][0], "nose_tip", "image"
        )["mean"],
        "nose_image_frame4_px": _obs(
            bundle["frames"][4], "nose_tip", "image"
        )["mean"],
    }


class S0AProxyHandshakeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bundle = build_bundle()

    def test_fixture_manifest_pins_exact_current_generator_output(self) -> None:
        expected = _load_fixture_manifest()
        actual = _regression_manifest(self.bundle)
        self.assertEqual(expected, actual)
        self.assertEqual(EXPECTED_SHA256, actual["payload_sha256"])
        self.assertEqual(BUNDLE_VERSION, actual["bundle_version"])
        self.assertEqual(FRAME_COUNT, actual["frame_count"])

    def test_two_generation_runs_are_byte_deterministic(self) -> None:
        a = json.dumps(
            build_bundle(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        b = json.dumps(
            build_bundle(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        self.assertEqual(a, b)

    def test_generated_observations_are_schema_valid_x1_and_provenance_bearing(self) -> None:
        self.assertEqual([], validate_bundle(self.bundle))

    def test_world_camera_image_projection_round_trip(self) -> None:
        for frame in self.bundle["frames"]:
            for semantic in (
                "nose_tip",
                "left_ear_tip",
                "right_ear_tip",
                "withers_visible",
            ):
                world = _obs(frame, semantic, "world")["mean"]
                image = _obs(frame, semantic, "image")["mean"]
                camera = world_to_camera(world)
                self.assertEqual(image, world_to_image(world))
                reconstructed = image_to_camera(image, camera[2])
                for actual, expected in zip(reconstructed, camera):
                    self.assertAlmostEqual(expected, actual, places=12)
                self.assertEqual(image, camera_to_image(camera))

    def test_analytic_derivatives_match_fixed_step_finite_differences(self) -> None:
        roots = [frame["subject_root_world_m"] for frame in self.bundle["frames"]]
        for index in range(1, len(roots) - 1):
            t = index * DT_SECONDS
            central_velocity = [
                (roots[index + 1][axis] - roots[index - 1][axis])
                / (2.0 * DT_SECONDS)
                for axis in range(3)
            ]
            central_acceleration = [
                (
                    roots[index + 1][axis]
                    - 2.0 * roots[index][axis]
                    + roots[index - 1][axis]
                )
                / (DT_SECONDS * DT_SECONDS)
                for axis in range(3)
            ]
            for actual, expected in zip(
                central_velocity, root_velocity_world(t)
            ):
                self.assertAlmostEqual(expected, actual, places=12)
            for actual, expected in zip(
                central_acceleration, root_acceleration_world(t)
            ):
                self.assertAlmostEqual(expected, actual, places=12)

    def test_contact_has_positive_and_negative_cases(self) -> None:
        values = [
            _obs(frame, "left_hind_paw_center_floor_contact")["mean"]
            for frame in self.bundle["frames"]
        ]
        self.assertEqual([True, True, False, False, True], values)
        for frame in self.bundle["frames"]:
            self.assertTrue(
                _obs(frame, "right_front_paw_center_floor_contact")["mean"]
            )

    def test_occlusion_is_geometry_driven_and_has_positive_negative_cases(self) -> None:
        left = [
            _obs(frame, "left_ear_tip", "world")["visibility"]
            for frame in self.bundle["frames"]
        ]
        right = [
            _obs(frame, "right_ear_tip", "world")["visibility"]
            for frame in self.bundle["frames"]
        ]
        self.assertEqual(
            [
                ["visible"],
                ["visible"],
                ["fully_occluded"],
                ["fully_occluded"],
                ["visible"],
            ],
            left,
        )
        self.assertEqual([["visible"]] * FRAME_COUNT, right)
        for index in range(FRAME_COUNT):
            self.assertEqual(
                left[index], visibility_for_landmark("left_ear_tip", index)
            )

    def test_payload_hash_and_x1_rule_detect_tampering(self) -> None:
        tampered = copy.deepcopy(self.bundle)
        _obs(tampered["frames"][0], "nose_tip", "world")["mean"][0] += 1.0
        self.assertIn("payload_sha256 mismatch", validate_bundle(tampered))

        tier_tampered = copy.deepcopy(self.bundle)
        changed = _obs(
            tier_tampered["frames"][0], "nose_tip", "world"
        )
        changed["evidence_tier"] = "S2"
        errors = validate_bundle(tier_tampered)
        self.assertTrue(
            any(
                "synthetic observation must use X1" in item
                for item in errors
            ),
            errors,
        )

    def test_x1_synthetic_bundle_cannot_satisfy_prospective_real_m1_contract(self) -> None:
        candidate = build_synthetic_m1_candidate(self.bundle)
        errors = validate_pose_package(candidate)
        self.assertTrue(
            any(
                "evidence_tier" in error
                and "cannot count as prospective real V1 evidence" in error
                for error in errors
            ),
            errors,
        )


if __name__ == "__main__":
    unittest.main()
