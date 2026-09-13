# Contributing

Thanks for looking. This is a small research repository, and the most useful thing an outside
person can do right now is also the simplest: review model output on real cat frames.

## 1. Review frames

Start at [Help review frames](README.md#help-review-frames-no-setup-needed) in the README. In
short: look at the four contact sheets, fill the `verdict` column of the CSV template, and send
the file back as a pull request or as an attachment on the review call issue.

A few things that make a review more useful:

- Judge only solid points. Hollow points are below the confidence threshold and the model is not
  claiming them.
- `not_visible` is a real answer. If the part is hidden, blurred or out of frame, say so instead
  of guessing which way the model went.
- Use `wrong` when the model drew nothing but the part is clearly there. A red `NO OUTPUT`
  banner with a visible cat is a miss, and a miss counts.
- Add a `condition` (`blur`, `occlusion`, `multi_cat`, ...) when you mark something `wrong`.
  Grouping failures by condition is most of the point.
- Do not look at anyone else's CSV before doing yours. Independent verdicts are worth more than
  matching ones; the scorer reports disagreement on purpose.

Name the file after your GitHub handle, for example `review/results/<set>/reviews/octocat.csv`.
The file stem becomes the reviewer id in the score report.

## 2. Add a clip

Body pose needs nothing but video. If you have phone footage of your own cat and are happy for
it to be redistributed under a Creative Commons licence, open an issue with a link and the
licence you are offering. Clips are only added through a manifest in `bakeoff/clips/` with a
verified licence, so please do not open a pull request that adds media directly.

Good clips for this stage: a single cat, ordinary indoor light, the whole animal in frame for
several seconds, some movement. Motion blur, clutter and dark fur are welcome; that is where the
models fail and where the review is informative.

## 3. Run the models yourself

```bash
python -m review.sample_frames
python -m review.run_body
python -m review.run_tail --device cuda   # or cpu
python -m review.sheets --output-dir review/work/sheets
python -m review.template --output review/results/<set>/reviews/TEMPLATE.csv
```

Dependencies and notes are in [review/README.md](review/README.md). If a run produces a
different sheet from the committed one, that is worth an issue.

## 4. Code

Pull requests are welcome for the review tooling, the bake-off adapters, the detail head
experiments and the identity work. Keep the existing pattern: each experiment directory has a
README saying what question it answers, a `reports/` or `results/` folder with what was
actually run, and tests that pass with `python -m pytest -q`. CI runs the relevant suite on
Python 3.11, 3.12 and 3.13.

Please do not add model weights, datasets or large media to the repository. Reports may cite
them; manifests may point at them.

## Licensing of contributions

The repository does not have an outbound licence yet; see
[docs/OPEN-DECISIONS.md](docs/OPEN-DECISIONS.md). Until it does:

- **Review verdicts** (CSV files under `review/results/`) are contributed under
  [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/). They are lists of `ok` /
  `wrong` / `not_visible` and carry no personal data, so this lets them be reused freely once
  the repository licence is chosen.
- **Code and documentation** contributions are accepted on the understanding that they will be
  released under whatever open licence the repository adopts, which will be an OSI-approved
  licence. If that is a problem for you, say so in the pull request and we will sort it out
  before merging.

## Conduct

Be decent. Disagree about frames, not about people. Cats in the clips were filmed by their
owners going about their day; nothing here involves handling or provoking an animal, and
contributions that do will not be accepted.
