# A1 — vocalisation acoustics

This directory contains the **zero-new-collection** engineering slice for issue #19.

## Scope

The first A1 experiment uses existing external research data only to establish whether feline vocal audio carries reproducible information about **observable emission context** under leakage-safe evaluation. It does not train a literal translator and does not create veterinary claims.

## CatMeows baseline

The initial manifest tooling targets CatMeows v1.0.2 (Zenodo record 4008297), whose filenames encode:

`C_NNNNN_BB_SS_OOOOO_RXX`

- `C`: context (`B` brushing, `F` waiting for food, `I` isolation)
- `NNNNN`: cat ID
- `BB`: breed (`MC`, `EU`)
- `SS`: sex/neuter code (`FI`, `FN`, `MI`, `MN`)
- `OOOOO`: owner ID
- `R`: recording session (`1`–`3`)
- `XX`: vocalisation counter

The upstream dataset states that it is available for scientific research and non-commercial purposes. **Do not copy CatMeows audio into this repository or reuse it for commercial training without a separate licence review.** The manifest stores paths/metadata only.

## Build a manifest

```bash
python -m audio.catmeows_manifest /path/to/CatMeows --output /tmp/catmeows.csv
```

The parser rejects filenames that do not follow the declared dataset convention instead of silently guessing metadata.

## Generate leakage-safe folds

Primary A1.0 evaluation is leave-one-cat-out:

```bash
python -m audio.group_splits /tmp/catmeows.csv --group-key cat_id --output /tmp/cat-folds.json
```

Owner-group sensitivity analysis:

```bash
python -m audio.group_splits /tmp/catmeows.csv --group-key owner_id --output /tmp/owner-folds.json
```

See `SPLIT-PROTOCOL.md` for the frozen evaluation rules.

## Non-goals for this slice

- downloading or redistributing external audio;
- feature extraction/model training;
- random clip-level train/test splits;
- interpreting the three CatMeows elicitation contexts as universal feline intent labels;
- recreating isolation or delayed-feeding treatments for new data collection.
