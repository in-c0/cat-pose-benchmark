from __future__ import annotations

import unittest

import detail.grounded_tail_v1 as v1
from detail.grounded_tail_v1 import looks_like_paw, map_box_from_crop, pad_box, tail_candidates, viterbi

CAT = [100.0, 100.0, 500.0, 400.0]


def cand(x: float, y: float, score: float, size: float = 40.0) -> dict:
    return {"label": "tail", "score": score, "box": [x, y, x + size, y + size]}


class BoxHelperTests(unittest.TestCase):
    def test_pad_box_clamps_to_image(self) -> None:
        self.assertEqual(pad_box([10.0, 10.0, 50.0, 50.0], 0.5, 60, 60), [0.0, 0.0, 60.0, 60.0])

    def test_map_box_from_crop_offsets(self) -> None:
        self.assertEqual(map_box_from_crop([1.0, 2.0, 3.0, 4.0], [10.0, 20.0, 99.0, 99.0]), [11.0, 22.0, 13.0, 24.0])

    def test_candidates_are_ranked_deduplicated_and_limited(self) -> None:
        dets = [cand(120, 120, 0.3), cand(122, 121, 0.28), cand(300, 300, 0.5), cand(400, 150, 0.25), {"label": "cat", "score": 0.9, "box": CAT}]
        out = tail_candidates(dets, CAT, limit=2)
        self.assertEqual([c["score"] for c in out], [0.5, 0.3])  # the 0.28 duplicate of 0.3 is dropped

    def test_paw_rule(self) -> None:
        self.assertTrue(looks_like_paw({"tail": 0.02, "paw": 0.4}))
        self.assertFalse(looks_like_paw({"tail": 0.5, "paw": 0.4}))
        self.assertFalse(looks_like_paw({"tail": 0.0, "paw": 0.05}))  # below the floor: no evidence either way


class ViterbiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.saved = (v1.NONE_EMISSION, v1.MOVE_WEIGHT, v1.NONE_SWITCH_COST)
        v1.NONE_EMISSION, v1.MOVE_WEIGHT, v1.NONE_SWITCH_COST = 0.2, 0.5, 0.2

    def tearDown(self) -> None:
        v1.NONE_EMISSION, v1.MOVE_WEIGHT, v1.NONE_SWITCH_COST = self.saved

    def test_smooth_track_is_followed(self) -> None:
        frames = [[cand(100 + 10 * t, 100, 0.35)] for t in range(6)]
        self.assertEqual(viterbi(frames, [500.0] * 6), [0] * 6)

    def test_jumping_low_score_candidates_become_none(self) -> None:
        frames = [[cand(100, 100, 0.26)], [cand(400, 350, 0.27)], [cand(120, 380, 0.25)], [cand(450, 120, 0.26)]]
        self.assertEqual(viterbi(frames, [500.0] * 4), [None] * 4)

    def test_smooth_candidate_beats_stronger_jumper(self) -> None:
        frames = []
        for t in range(5):
            steady = cand(200 + 8 * t, 200, 0.30)
            jumper = cand(100 if t % 2 else 450, 100 if t % 2 else 380, 0.36)
            frames.append([jumper, steady])
        self.assertEqual(viterbi(frames, [500.0] * 5), [1] * 5)

    def test_empty_frames_and_none_state(self) -> None:
        frames = [[cand(100, 100, 0.5)], [], [cand(105, 102, 0.5)]]
        self.assertEqual(viterbi(frames, [500.0] * 3), [0, None, 0])
        self.assertEqual(viterbi([], []), [])


if __name__ == "__main__":
    unittest.main()
