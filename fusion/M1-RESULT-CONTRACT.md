# M1 machine-enforced result contract

Status: synthetic integration guard for M1 #21 / M1.1 #41. No animal data or multimodal performance result is produced here.

## Purpose

M1 is vulnerable to a common multimodal failure mode: train a flexible fusion model, notice which combinations look good, then report only those combinations. The result guard makes the frozen ablation doctrine mechanically enforceable before compatible real V1/A1/CT1 episodes exist.

The first compatible target is the CT1.3 observable endpoint:

- target: `signalling_terminated`
- horizon: 60 seconds
- label meaning: directly observed termination outcome only; not a human `true_intent` label.

## Frozen initial matrix

The machine-readable source of truth is `fusion/m1_ablation_spec.json`.

| ID | Available inputs | Role |
| --- | --- | --- |
| B0 | context/routine | strongest non-sensor comparator |
| V | V1 | visual only |
| A | A1 | vocal audio only |
| BV | context/routine + V1 | incremental visual information |
| BA | context/routine + A1 | incremental audio information |
| VA | V1 + A1 | sensor-only fusion |
| BVA | context/routine + V1 + A1 | full initial fusion |
| BVA-V | context/routine + A1 | visual-drop stress of BVA |
| BVA-A | context/routine + V1 | audio-drop stress of BVA |

Every row is required. A poor row cannot be omitted.

## Comparable held-out cohort

`B0`, `V`, `A`, `BV`, `BA`, `VA`, and `BVA` must carry the exact same held-out episode IDs and outer-split manifest hash. The dropout stress rows must use the BVA evaluation cohort too.

This deliberately prevents an apparent fusion gain created by scoring BVA only on easier complete-modality episodes while scoring unimodal comparators on a different cohort.

## Required report content

Every ablation row reports:

- log loss;
- Brier score;
- ECE;
- balanced accuracy;
- macro F1;
- exact held-out episode IDs plus SHA-256 digest;
- target/horizon and outer-split manifest digest.

The report also carries subject, household/owner, time/routine, location, device/source, and modality-missingness leakage probes; complete/naturally-missing/dropout diagnostics; abstention status; and uncertainty support.

Unsupported diagnostics must be explicitly marked unsupported with a reason. They may not silently disappear.

## Contract validity versus advancement

A report can be **contract-valid** even when fusion fails. That is intentional: null and negative ablations are valid scientific results.

If `advancement.requested=true`, the guard additionally computes the strongest constituent comparator among B0/V/A/BV/BA/VA and requires:

1. BVA log loss is strictly lower than that strongest comparator;
2. the declared delta log loss equals the metrics actually reported;
3. group-aware uncertainty is supported using subject, household, day, or session resampling;
4. the uncertainty result supports the improvement;
5. material ECE degradation above the frozen 0.02 threshold is explicitly disclosed.

The guard does not infer necessity/sufficiency from feature importance.

## Usage

Generate the software-only fixture:

```bash
python -m fusion.fixtures.m1_synthetic_report --output /tmp/m1-report.json
```

Validate it:

```bash
python -m fusion.m1_result_guard /tmp/m1-report.json --summary /tmp/m1-summary.json
```

A non-conforming report exits non-zero and lists the failed contract clauses.

## Boundaries

- Synthetic fixture numbers are planted software-test values, not feline evidence.
- Large-scale M1 training still waits for compatible real measurement threads.
- CT1.3 remains owner-operated and empirically gated; M1.1 does not fabricate those episodes.
- A future target other than 60-second signalling termination requires a separately versioned M1 experiment contract rather than silently editing this one after seeing data.
