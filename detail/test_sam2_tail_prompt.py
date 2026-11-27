from __future__ import annotations

import unittest

import numpy as np

from detail.sam2_tail_prompt import _candidate_diagnostics, _candidate_rank


PROMPT = {
    "positive_points": [
        {"x_px": 2.0, "y_px": 2.0},
        {"x_px": 7.0, "y_px": 2.0},
    ],
    "negative_points": [
        {"x_px": 4.0, "y_px": 7.0},
        {"x_px": 7.0, "y_px": 7.0},
    ],
}


class PromptCandidateTests(unittest.TestCase):
    def test_prompt_consistency_outranks_raw_sam_score(self) -> None:
        whole_subject = np.ones((10, 10), dtype=bool)
        tail_only = np.zeros((10, 10), dtype=bool)
        tail_only[1:4, 1:9] = True

        whole = _candidate_diagnostics(whole_subject, 0.99, PROMPT, 0)
        tail = _candidate_diagnostics(tail_only, 0.75, PROMPT, 1)

        self.assertEqual(whole["positive_prompt_inside_fraction"], 1.0)
        self.assertEqual(whole["negative_prompt_outside_fraction"], 0.0)
        self.assertEqual(tail["positive_prompt_inside_fraction"], 1.0)
        self.assertEqual(tail["negative_prompt_outside_fraction"], 1.0)
        self.assertGreater(_candidate_rank(tail), _candidate_rank(whole))

    def test_smaller_mask_breaks_tie_after_prompt_and_score(self) -> None:
        large = np.zeros((10, 10), dtype=bool)
        small = np.zeros((10, 10), dtype=bool)
        large[0:5, :] = True
        small[1:4, 1:9] = True

        large_diagnostic = _candidate_diagnostics(large, 0.8, PROMPT, 0)
        small_diagnostic = _candidate_diagnostics(small, 0.8, PROMPT, 1)
        self.assertGreater(
            _candidate_rank(small_diagnostic), _candidate_rank(large_diagnostic)
        )


if __name__ == "__main__":
    unittest.main()
