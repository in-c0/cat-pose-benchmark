# BH1 submissions

Empty until labelling starts. Nothing here is a measurement until every registered labeller (at least two) has locked.

```text
labellers.json                 {"labellers": ["<handle>", ...]}, written before the package is sent
locks.json                     {"labels/labels-<handle>.csv": "<sha256 the labeller posted>"}
labels/labels-<handle>.csv     sent only after every registered labeller has posted a digest
```

`python -m behaviour.score` refuses any file whose digest is missing from `locks.json` or differs from it, and refuses to run until every handle in `labellers.json` has a lock. Do not edit a submitted file. A correction goes in as `labels-<handle>-r2.csv` with its own posted digest; the newest revision is scored and both are kept.
