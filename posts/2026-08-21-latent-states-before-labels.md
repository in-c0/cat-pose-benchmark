# Latent states before labels: when the confound detector catches us

**Date:** 2026-08-21  
**Status:** software-only methodology note; no real-cat result

There is an easy way for unsupervised animal-behaviour work to fool itself.

You collect a complicated set of signals. You run a clustering algorithm. The clusters are stable. They look different. They even line up with things you recognise. Then someone gives them names.

`hungry`. `playful`. `wants attention`.

The problem is that the clusters may instead be telling you which cat was recorded, which house the microphone was in, which session used a different camera, or what time the owner usually gets home.

A stable cluster is not automatically a meaningful behavioural state.

We built L1.0 to make that mistake harder.

## The rule: discover first, interpret later

The latent-state thread deliberately separates two information planes.

The clustering algorithm receives only numeric predictor evidence that existed before the outcome being studied. It cannot receive:

- cat, household or session identity;
- human intent labels;
- translations;
- outcome labels;
- intervention responses;
- post-horizon observations.

Those variables are kept outside the fitting function. Only after an opaque partition exists do we ask whether it is associated with identity, context or observable outcomes.

The first method is intentionally ordinary:

- median imputation;
- standardisation;
- KMeans with `k = 2..8`;
- twenty deterministic 80% subsample refits;
- all-episode assignment stability measured with adjusted Rand index;
- post-fit adjusted mutual-information audits against cat, household, session, context and observable outcome.

Clusters get identifiers such as `L1-Z03-c1`. They do not get English names.

The point of this stage is not to discover a sophisticated representation. It is to discover whether we can trust ourselves not to narrate one into existence.

## Then the detector caught our own test

We created two synthetic fixtures before any real household episode enters L1.

One fixture was supposed to contain a clean three-state latent structure independent of identity. The other was deliberately identity-dominated: four synthetic cats occupied four very distinct regions of feature space, while the context and outcome labels varied within each cat.

The second fixture was meant to test whether the system would say, in effect:

> Yes, this is very clusterable. No, that does not make it a candidate intent state.

That test worked.

More interestingly, the supposedly clean fixture failed too.

Its planted latent state was generated from the episode index modulo three. Cat identity was generated from the same index modulo six. Without intending to, we had made cat identity predictive of the latent state.

The clustering itself looked excellent. The planted regimes were recoverable and stable. But the nuisance audit saw that the partition was also strongly associated with subject identity and rejected our expectation that this was a clean non-identity example.

That was not a false alarm. The fixture was wrong.

## What we changed — and what we did not

We changed the fixture so every synthetic cat receives all three planted regimes, and every synthetic session is balanced across them.

We did **not** change:

- the clustering method;
- the number of clusters tested;
- the twenty-repeat stability procedure;
- the identity-confound threshold;
- the post-fit audit logic.

The corrected clean fixture passes. The deliberately identity-dominated fixture remains highly stable and is still flagged as nuisance structure.

That distinction matters. If a diagnostic is relaxed whenever it rejects a result we expected to like, it is no longer much of a diagnostic.

## Why this matters for real cats

Real household data will be much less polite than our synthetic fixtures.

Individual cats have distinctive voices, movement styles and routines. Different households have different rooms, microphones, surfaces, schedules and people. Sessions differ in lighting, device placement and background noise. Some of those variables may genuinely interact with behaviour; others may simply provide an easy shortcut for a model.

We already saw a version of this problem in the CatMeows acoustic work: stable acoustic structure was substantially more associated with cat, owner and breed identity than with the supplied behavioural context. That is useful information, but it is not a licence to rename the clusters as feline communicative states.

L1 therefore treats identity-confounded structure as a result in its own right. It can tell us what nuisance variation future representations need to control. It just cannot be promoted into semantics.

## Stability is only the beginning

Even a stable, non-identity-dominated latent partition will not be called an intent state at L1.0.

A later stage would still have to show that the representation adds something useful under held-out evaluation—for example:

- better prediction of what happens next;
- better probability calibration;
- better discrimination between competing prospective hypotheses;
- useful intervention-conditioned changes;
- information beyond the strong context/routine baseline.

And only after those observable consequences are established does semantic interpretation become an interesting question.

The programme's direction is therefore deliberately backwards from a conventional “cat translator” demo:

`signals -> reproducible latent structure -> confound audit -> predictive/outcome validation -> possible interpretation`

not

`signals -> plausible English sentence`.

## Current evidence boundary

Everything described in the L1.0 regression fixtures is synthetic software test data. It proves that the methodology can recover a planted structure, reject an identity shortcut, and catch one accidental confound in our own test construction.

It does **not** prove that cats possess three latent communicative states, that KMeans is the right model for feline behaviour, or that any opaque cluster corresponds to hunger, play, affection, access-seeking, stress, pain, or anything else.

That uncertainty is not something to hide at this stage. It is the thing the research machinery is being built to preserve.

## Reproducibility

The implementation is in:

- [`latent/L1-PROTOCOL.md`](../latent/L1-PROTOCOL.md)
- [`latent/l1_discovery.py`](../latent/l1_discovery.py)
- [`latent/test_l1_discovery.py`](../latent/test_l1_discovery.py)

The programme roadmap is tracked in [issue #22](https://github.com/in-c0/cat-pose-benchmark/issues/22), and L1.0 was introduced in [issue #59](https://github.com/in-c0/cat-pose-benchmark/issues/59).
