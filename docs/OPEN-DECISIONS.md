# Open decisions — the hold list

**The repo is held here pending research direction.** This is the list of what that pass
needs to settle. Nothing below is decided; nothing is being built until it is.

Ordered by how expensive they are to get wrong.

---

## Tier 1 — irreversible after data collection starts

| # | Decision | Why it locks | Draft position |
|---|---|---|---|
| 1 | **Keypoint topology** | Changing it after collection means recollecting everything | 34-point strict AP-10K superset — [KEYPOINT-TOPOLOGY-DRAFT.md](KEYPOINT-TOPOLOGY-DRAFT.md) |
| 2 | **Benchmark sourcing + CLA** | Contributor rights cannot be retrofitted after footage is collected | Undecided — 4 options in [BENCHMARK-PROTOCOL-DRAFT.md](BENCHMARK-PROTOCOL-DRAFT.md) |
| 3 | **Outbound licences** (code / synthetic / benchmark / weights) | The CLA depends on this; collection cannot start before it | Undecided — [LICENSING-POLICY.md](LICENSING-POLICY.md) §3 |
| 4 | **Stratification design** | Coverage gaps must be declared up front, not discovered later | Fractional factorial vs tiered — undecided |

## Tier 2 — expensive to change, not fatal

| # | Decision | Note |
|---|---|---|
| 5 | **Occlusion flags** — does synthetic emit them, does real annotation match? | Must be answered before *either* pipeline starts |
| 6 | **Metrics** — PCK only, or OKS with estimated sigmas? | Affects what the benchmark can claim |
| 7 | **Rigged asset selection** | Licence-gated; see policy §2. Ear/tail rig quality is the binding constraint, not visual realism |
| 8 | **Sim-to-real validation gate** | What accuracy on real data counts as "it worked"? Set the number *before* seeing results |

## Tier 3 — deferred, listed so they aren't forgotten

| # | Decision |
|---|---|
| 9 | Brand name (separate from this repo's name) |
| 10 | Whether the consumer app is a separate repo (recommended: yes) |
| 11 | Paper venue and timing — dataset public first, paper later |
| 12 | Whether to approach Tech4Animals / FGS group before or after first release |

---

## Unresolved external dependencies

- **AP-10K licence conflict.** Repo states CC-BY-4.0; MMPose dataset zoo lists it as
  non-commercial. **Blocks any use of AP-10K.** Resolve in writing with the authors;
  commit the reply. Cost: one email. Not yet sent.
- **Rigged cat asset terms.** No vendor identified yet. The specific question most
  asset licences fail to answer: *may rendered derivative imagery be redistributed as a
  public dataset, and are weights trained on it unencumbered?*

---

## Standing constraints (not decisions — these hold regardless)

- No CC BY-NC or research-only data, weights, or pseudo-labels. Ever. No laundering
  path exists. See [LICENSING-POLICY.md](LICENSING-POLICY.md) §1.
- No medical, veterinary, welfare, or diagnostic claims from anything built on this.
- No semantic "translation" claims — unsupported by the literature.
- Benchmark data is **evaluation only** and is never trained on. Violating this destroys
  the only thing that makes the result meaningful.
- Coverage gaps are declared in the datasheet. Silent truncation reads as full coverage.

---
