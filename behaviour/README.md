# BH1: behaviour-recognition feasibility study

BH1 tests whether five observable behaviours (walk, sit/lie, self-groom, jump, play/other) can be recognised from video on cats a method has never seen. It sits outside benchmark v0, which makes no behaviour claims (`docs/OPEN-DECISIONS.md`), and it labels nothing about emotion, intention or pain.

**Status, 2026-10-17: prepared, not run.** The protocol is frozen, the clip pool is drawn, and the builder, baselines and scorer exist and are tested on synthetic data. Nothing has been selected, labelled or scored. Three owner rulings are pending (exception `2026-10-11-cat-pose-behaviour-feasibility-df26`): whether BH1 runs, who the two labellers are, and which clips may be used.

| file | what it is |
|---|---|
| [PROTOCOL.md](PROTOCOL.md) | class definitions, labelling unit, selection, blinding, analysis plan and decision rules, frozen before any label |
| [LABELLER-GUIDE.md](LABELLER-GUIDE.md) | what a labeller reads |
| `protocol_freeze.json` | SHA-256 of the frozen protocol text; the tests fail if it changes |
| `pool/pool.json`, `pool/draw.json` | the Commons pool (498 files, 38 categories, depth 2), seed 20261017, frozen order, and the clip counts under each candidate ruling |
| `sample_pool.py` | draws the pool; after the ruling, `select` writes `pool/selection.json` |
| `build.py` | identity template, fetch, and the blind package (opaque ids from a private salt) |
| `withholding.py` | checks the public tree hides the key until every labeller has locked |
| `baselines.py` | `majority` and `motion_lr` (motion energy + logistic regression), clip-disjoint and cat-disjoint folds |
| `score.py` | agreement, unanimous truth, balanced accuracy against chance, gain over majority, per-class P/R/F1, cat-level bootstrap intervals, decision rules R0–R6 |
| `synthetic.py`, `test_bh1.py` | synthetic segments and the tests, including two negative controls |

## What the pool draw found

Without CC BY-SA, 248 clips from 35 uploaders are eligible, and 189 of them come from one uploader. Reaching 100 clips without BY-SA means letting that uploader supply at least 41. With BY-SA allowed, a cap of 4 clips per uploader gives 105 clips from 62 uploaders. The full table is in PROTOCOL.md section 4. How many distinct cats any of these contain is unknown until a person does the identity pass.

## Running it, once the rulings exist

```bash
python -m behaviour.sample_pool select --cap <n> [--include-by-sa] --ruling <exception or issue>
python -m behaviour.build identity-template      # a person fills work/identity.csv by watching each clip
python -m behaviour.build fetch                  # downloads clips, extracts frames (needs imageio-ffmpeg)
python -m behaviour.build package                # template, media digests, commitment; sheets and videos to work/package/
python -m behaviour.withholding                  # then commit package/ and submissions/labellers.json
```

Send `work/package/` and the template to the registered labellers. Record each posted digest in `submissions/locks.json`. When every registered labeller has locked and sent their file:

```bash
# copy work/key.json and work/manifest.json to behaviour/, then
python -m behaviour.withholding --verify-release
python -m behaviour.baselines
python -m behaviour.score --output-md behaviour/results.md --output-json behaviour/results.json
```

Apply the decision rules as PROTOCOL.md section 8 states them. Keep a private backup of `work/`; without the salt the commitment cannot be checked.

## Tests

```bash
python -m pytest -q behaviour
```

The tests use synthetic data only. Three synthetic worlds check the decision rules: one where labels follow the motion, one where labels are random, and one where each cat has its own habit and its own way of moving. Two drafts of the decision rule failed these tests before the protocol was frozen. Macro-F1 gain over the majority baseline passed on random labels, and balanced-accuracy gain over the majority baseline passed in the identity world, because a cross-validated majority baseline scores below chance. The rule now compares balanced accuracy on unseen cats with the chance level (PROTOCOL.md section 7.5).
