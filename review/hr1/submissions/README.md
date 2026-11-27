# HR1 submissions

One CSV per reviewer per stage. The file stem is the reviewer id.

```text
stage_a/stage-a-<handle>.csv
stage_b/stage-b-<handle>.csv
locks.json
```

`locks.json` maps `<stage folder>/<file name>` to the SHA-256 the reviewer posted on issue #79 **before** uploading, for example:

```json
{"stage_a/stage-a-octocat.csv": "3f2a…"}
```

`python -m review.hr1.score` refuses any file whose digest is missing from `locks.json` or does not match it. Do not edit a submitted file. A correction goes in as a new file named `stage-a-<handle>-r2.csv`, with its own posted digest, and both files are reported.

Empty until the first reviewer submits.
