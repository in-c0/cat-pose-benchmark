from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

DEFAULT_UNLABELLED_BUDGETS = [1, 2, 4, 8, 16]
DEFAULT_LABELLED_BUDGETS = [1, 2, 4, 8]


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError("manifest is empty")
    required = {"path", "cat_id", "session", "context"}
    missing = required - set(rows[0])
    if missing:
        raise ValueError(f"manifest missing required fields: {sorted(missing)}")
    return rows


def _budget_support(max_budget: int, budgets: list[int]) -> dict[str, bool]:
    return {str(budget): max_budget >= budget for budget in budgets}


def audit(
    manifest_csv: Path,
    unlabelled_budgets: list[int] | None = None,
    labelled_budgets: list[int] | None = None,
) -> dict[str, object]:
    rows = _read_rows(manifest_csv)
    unlabelled_budgets = sorted(set(unlabelled_budgets or DEFAULT_UNLABELLED_BUDGETS))
    labelled_budgets = sorted(set(labelled_budgets or DEFAULT_LABELLED_BUDGETS))

    by_cat: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_cat[row["cat_id"]].append(row)

    cats: dict[str, object] = {}
    all_folds: list[dict[str, object]] = []

    for cat_id in sorted(by_cat):
        cat_rows = by_cat[cat_id]
        sessions = sorted({int(row["session"]) for row in cat_rows})
        contexts = sorted({row["context"] for row in cat_rows})
        session_context_counts: dict[str, dict[str, int]] = {}

        for session in sessions:
            session_rows = [row for row in cat_rows if int(row["session"]) == session]
            counts = Counter(row["context"] for row in session_rows)
            session_context_counts[str(session)] = dict(sorted(counts.items()))

        folds: list[dict[str, object]] = []
        if len(sessions) >= 2:
            for test_session in sessions:
                test_rows = [row for row in cat_rows if int(row["session"]) == test_session]
                adaptation_rows = [row for row in cat_rows if int(row["session"]) != test_session]
                test_contexts = sorted({row["context"] for row in test_rows})
                adaptation_context_counts = Counter(row["context"] for row in adaptation_rows)
                adaptation_contexts = sorted(adaptation_context_counts)
                shared_contexts = sorted(set(test_contexts) & set(adaptation_contexts))
                all_test_contexts_supported = set(test_contexts).issubset(adaptation_context_counts)
                test_has_at_least_two_contexts = len(test_contexts) >= 2
                if all_test_contexts_supported and test_contexts:
                    max_labelled_budget = min(adaptation_context_counts[context] for context in test_contexts)
                else:
                    max_labelled_budget = 0

                fold = {
                    "cat_id": cat_id,
                    "test_session": test_session,
                    "adaptation_sessions": [session for session in sessions if session != test_session],
                    "n_test": len(test_rows),
                    "n_adaptation": len(adaptation_rows),
                    "test_contexts": test_contexts,
                    "adaptation_contexts": adaptation_contexts,
                    "shared_contexts": shared_contexts,
                    "test_has_at_least_two_contexts": test_has_at_least_two_contexts,
                    "all_test_contexts_supported": all_test_contexts_supported,
                    "primary_feasible": test_has_at_least_two_contexts and all_test_contexts_supported,
                    "max_labelled_budget_per_test_context": max_labelled_budget,
                    "unlabelled_budget_support": _budget_support(len(adaptation_rows), unlabelled_budgets),
                    "labelled_budget_support": _budget_support(max_labelled_budget, labelled_budgets),
                }
                folds.append(fold)
                all_folds.append(fold)

        cats[cat_id] = {
            "n_clips": len(cat_rows),
            "contexts": contexts,
            "sessions": sessions,
            "session_context_counts": session_context_counts,
            "n_session_disjoint_folds": len(folds),
            "folds": folds,
            "infeasible_reason": None if folds else "fewer_than_two_recording_sessions",
        }

    primary_folds = [fold for fold in all_folds if fold["primary_feasible"]]
    summary = {
        "n_rows": len(rows),
        "n_cats": len(by_cat),
        "n_cats_with_at_least_two_sessions": sum(
            1 for cat in cats.values() if len(cat["sessions"]) >= 2
        ),
        "n_session_disjoint_folds": len(all_folds),
        "n_folds_test_has_at_least_two_contexts": sum(
            bool(fold["test_has_at_least_two_contexts"]) for fold in all_folds
        ),
        "n_folds_all_test_contexts_supported": sum(
            bool(fold["all_test_contexts_supported"]) for fold in all_folds
        ),
        "n_primary_feasible_folds": len(primary_folds),
        "n_primary_feasible_cats": len({fold["cat_id"] for fold in primary_folds}),
        "unlabelled_budget_primary_fold_counts": {
            str(budget): sum(
                bool(fold["unlabelled_budget_support"][str(budget)]) for fold in primary_folds
            )
            for budget in unlabelled_budgets
        },
        "labelled_budget_primary_fold_counts": {
            str(budget): sum(
                bool(fold["labelled_budget_support"][str(budget)]) for fold in primary_folds
            )
            for budget in labelled_budgets
        },
    }

    return {
        "protocol": "A1.0b-personalisation-feasibility-v0.1",
        "primary_fold_rule": (
            "held-out cat session has >=2 contexts and every test context appears in other sessions; "
            "adaptation and evaluation sessions are disjoint"
        ),
        "unlabelled_budgets": unlabelled_budgets,
        "labelled_budgets_per_test_context": labelled_budgets,
        "summary": summary,
        "cats": cats,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit session-disjoint CatMeows personalisation feasibility")
    parser.add_argument("manifest_csv", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report = audit(args.manifest_csv)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    print(f"wrote personalisation feasibility audit to {args.output}")


if __name__ == "__main__":
    main()
