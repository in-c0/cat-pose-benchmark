from __future__ import annotations

import unittest

import numpy as np
from sklearn.metrics import balanced_accuracy_score

from audio.identity_invariance import (
    _between_group_variance_ratio,
    _fit_logistic,
    _group_residualise,
    _predict,
    _pseudo_labels,
)


class IdentityInvarianceTests(unittest.TestCase):
    def test_pseudo_labels_are_deterministic_and_preserve_group_sizes(self) -> None:
        labels = np.asarray(["A", "A", "A", "B", "B", "C"], dtype=object)
        first = _pseudo_labels(labels, seed=17, held_out_cat="TEST", repeat=3)
        second = _pseudo_labels(labels, seed=17, held_out_cat="TEST", repeat=3)
        self.assertEqual(first.tolist(), second.tolist())
        self.assertEqual(sorted(labels.tolist()), sorted(first.tolist()))

    def test_true_centering_removes_between_cat_mean_structure(self) -> None:
        x = np.asarray([
            [-1.0, -5.0], [1.0, -5.0],
            [-1.0, 0.0], [1.0, 0.0],
            [-1.0, 5.0], [1.0, 5.0],
        ])
        labels = np.asarray(["A", "A", "B", "B", "C", "C"], dtype=object)
        population_mean = x.mean(axis=0)
        before = _between_group_variance_ratio(x, labels)
        centered = _group_residualise(x, labels, population_mean, tau=None)
        after = _between_group_variance_ratio(centered, labels)
        self.assertGreater(before, 0.4)
        self.assertLess(after, 1e-12)

    def test_true_identity_grouping_can_outperform_pseudo_grouping(self) -> None:
        rng = np.random.default_rng(1)
        x_train: list[list[float]] = []
        y_train: list[str] = []
        labels: list[str] = []

        # Identity offset is spuriously correlated with class prevalence in training.
        # The signal feature remains predictive within cats. Correct cat-centering
        # removes the nuisance offset; arbitrary same-size groups generally do not.
        for cat, offset, n_a, n_b in [
            ("C1", -6.0, 10, 2),
            ("C2", -2.0, 8, 4),
            ("C3", 2.0, 4, 8),
            ("C4", 6.0, 2, 10),
        ]:
            for label, count, signal_mean in [("A", n_a, -0.4), ("B", n_b, 0.4)]:
                for _ in range(count):
                    x_train.append([float(signal_mean + rng.normal(0.0, 0.5)), offset])
                    y_train.append(label)
                    labels.append(cat)

        x_train_array = np.asarray(x_train, dtype=float)
        y_train_array = np.asarray(y_train, dtype=object)
        cat_labels = np.asarray(labels, dtype=object)
        population_mean = x_train_array.mean(axis=0)

        x_test: list[list[float]] = []
        y_test: list[str] = []
        for label, signal_mean in [("A", -0.4), ("B", 0.4)]:
            for _ in range(100):
                x_test.append([float(signal_mean + rng.normal(0.0, 0.5)), -6.0])
                y_test.append(label)
        x_test_array = np.asarray(x_test, dtype=float)
        y_test_array = np.asarray(y_test, dtype=object)
        classes = np.asarray(["A", "B"], dtype=object)
        zero_shot_test = x_test_array - population_mean

        true_train = _group_residualise(
            x_train_array, cat_labels, population_mean, tau=None
        )
        true_scaler, true_model = _fit_logistic(true_train, y_train_array)
        true_probability = _predict(true_scaler, true_model, zero_shot_test, classes)
        true_prediction = classes[np.argmax(true_probability, axis=1)]
        true_score = balanced_accuracy_score(y_test_array, true_prediction)

        pseudo_scores = []
        for repeat in range(20):
            pseudo = _pseudo_labels(
                cat_labels, seed=23, held_out_cat="TEST", repeat=repeat
            )
            pseudo_train = _group_residualise(
                x_train_array, pseudo, population_mean, tau=None
            )
            scaler, model = _fit_logistic(pseudo_train, y_train_array)
            probability = _predict(scaler, model, zero_shot_test, classes)
            prediction = classes[np.argmax(probability, axis=1)]
            pseudo_scores.append(balanced_accuracy_score(y_test_array, prediction))

        self.assertGreater(true_score, float(np.mean(pseudo_scores)) + 0.03)


if __name__ == "__main__":
    unittest.main()
