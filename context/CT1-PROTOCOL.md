# CT1.1 — context + routine baseline protocol

CT1.1 is the zero-burden instrumentation slice of issue #34. It asks whether ordinary, observable context and routine history can predict an observable next outcome before adding visual/audio fusion.

## Primary target

The first executable target is `signalling_terminated` from the shared `#18` event outcome record.

This is not an intent label. It records whether the signalling episode terminates inside the declared outcome window.

## Prediction cutoff

For CT1.1, prediction time is `event.time.start_time`.

The extractor may use:

- the current event's top-level `context` as a prediction-time snapshot;
- the current event's timestamp;
- earlier events whose `time.start_time` precedes the cutoff;
- actions/outcomes from earlier events only when their absolute timestamps are at or before the cutoff.

The extractor must not use the current event's:

- observations;
- hypotheses;
- human actions;
- interventions;
- outcomes;
- free-form `context.routine`.

The current outcome is label-only.

This conservative rule intentionally throws away potentially useful information until capture-time provenance is strong enough to prove that it existed before the prediction.

## Feature groups

### Object/location

- coarse location;
- object count;
- human / other-cat presence;
- nearest-human distance when recorded;
- door/access presence and open/closed state;
- toy presence;
- food-area / feeder / bowl presence.

The keyword mapping is fixed in `ct1_feature_spec.json` before any naturalistic result.

### Routine/history

- cyclic local clock from the recorded timestamp offset;
- time since previous episode;
- episode count in the previous hour / 24 hours;
- previous episode location;
- previous observed signalling-termination state, if already known before the current cutoff;
- time since prior ordinary food/play/access/social actions.

No history statistic may be computed using a future event.

## CT1.1 evaluation

The first evaluator is intentionally limited to a **single-household chronological blocked sensitivity**.

Rows are sorted by prediction time. The earlier contiguous block trains; the later contiguous block evaluates. There is no random event split headline.

Model ladder:

1. Laplace-smoothed prevalence;
2. routine/history only;
3. object/location only;
4. context + routine.

All non-prevalence models are regularised logistic classifiers and are scored on the same held-out rows.

Metrics:

- balanced accuracy;
- macro F1;
- log loss;
- Brier score;
- ECE.

A single-household result is instrumentation evidence only. Population claims require later cross-cat and preferably cross-household outer splits.

## Synthetic fixture

`fixtures/ct1_synthetic_events.py` generates deterministic software-test data. It is explicitly not an animal-behaviour dataset and must never be cited as feline evidence.

Its purpose is to verify that:

- #18-shaped events can be converted into CT1 rows;
- current actions/outcomes cannot leak into predictors;
- future episodes cannot enter history;
- overlapping previous episodes cannot leak actions/outcomes that occur after the current cutoff;
- chronological evaluation can recover a deliberately planted context signal.

## Advancement

CT1.1 is complete when the feature contract, leakage tests, synthetic fixture, baseline evaluator and CI are green.

The next empirical step is CT1.2/A1.2/I1-compatible prospective naturalistic recording. That step must timestamp context at capture time and preserve ordinary-care/welfare constraints from issues #19 and #20.
