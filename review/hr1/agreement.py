"""Chance-corrected agreement for categorical labels from two or more reviewers.

Kept dependency-free so the scorer runs anywhere the review CSVs can be opened.
"""

from __future__ import annotations

from collections import Counter
from itertools import combinations
from typing import Hashable, Mapping

Labels = Mapping[Hashable, str]  # item -> label, for one reviewer; missing items are absent


def percent_agreement(a: Labels, b: Labels) -> tuple[int, int]:
    shared = set(a) & set(b)
    return sum(1 for k in shared if a[k] == b[k]), len(shared)


def cohen_kappa(a: Labels, b: Labels) -> float | None:
    """Cohen's kappa on the items both reviewers labelled. None if undefined."""
    shared = sorted(set(a) & set(b), key=str)
    n = len(shared)
    if n == 0:
        return None
    po = sum(1 for k in shared if a[k] == b[k]) / n
    ca, cb = Counter(a[k] for k in shared), Counter(b[k] for k in shared)
    pe = sum(ca[c] * cb[c] for c in set(ca) | set(cb)) / (n * n)
    if pe == 1.0:
        return None  # both reviewers used one identical category throughout
    return (po - pe) / (1 - pe)


def krippendorff_alpha_nominal(reviewers: Mapping[str, Labels]) -> float | None:
    """Krippendorff's alpha, nominal metric, any number of reviewers, missing data allowed.

    Items labelled by fewer than two reviewers are not pairable and are dropped, as in the
    standard coincidence-matrix formulation.
    """
    items: dict[Hashable, list[str]] = {}
    for labels in reviewers.values():
        for k, v in labels.items():
            items.setdefault(k, []).append(v)
    coincidence: Counter = Counter()
    for values in items.values():
        m = len(values)
        if m < 2:
            continue
        for i, j in ((i, j) for i in range(m) for j in range(m) if i != j):
            coincidence[(values[i], values[j])] += 1.0 / (m - 1)
    n = sum(coincidence.values())
    if n <= 1:
        return None
    marg: Counter = Counter()
    for (c, _k), w in coincidence.items():
        marg[c] += w
    do = sum(w for (c, k), w in coincidence.items() if c != k)
    de = sum(marg[c] * marg[k] for c in marg for k in marg if c != k) / (n - 1)
    if de == 0:
        return None
    return 1 - do / de


def pairwise(reviewers: Mapping[str, Labels]) -> list[dict]:
    out = []
    for x, y in combinations(sorted(reviewers), 2):
        agree, shared = percent_agreement(reviewers[x], reviewers[y])
        k = cohen_kappa(reviewers[x], reviewers[y])
        out.append({"a": x, "b": y, "n_shared": shared, "n_agree": agree,
                    "pct_agree": round(100.0 * agree / shared, 1) if shared else None,
                    "cohen_kappa": None if k is None else round(k, 3)})
    return out
