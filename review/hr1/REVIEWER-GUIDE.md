# Reviewer guide: is there a cat's tail in this frame?

Thank you for helping. This review checks whether a tail-finding method works on cat videos it has never seen. So far every label in this project was written by an AI model, so your answers would be the first human check of those numbers. It takes about an hour and a half in two sittings, and you need nothing beyond a browser, a spreadsheet program and some familiarity with cats.

There are two stages. Please finish Stage A before you look at anything in Stage B, and please do not compare answers with anyone else until everyone has submitted. The value of having two reviewers comes from your answers being independent.

## Before you start

Please do **not** open these, because they show what the model or the AI annotator thought about the same frames:

- `review/truth/` (the AI-written labels)
- `review/hr1/outputs/` and `review/hr1/key.json`, once they appear (the method's output and the Stage B answer key)
- `review/results/` and the technical notes under `paper/` (pictures with model output drawn on them)

If you have already seen some of them, that is fine. Just say so when you submit (see the end of this guide), and we will record it next to your answers.

The easiest way to get everything is to download the repository as a ZIP: the green **Code** button on the [repository page](https://github.com/in-c0/cat-pose-benchmark), then **Download ZIP**. The files you need are under `review/hr1/package/`.

## Stage A: tail or no tail (about 45 minutes)

You will look at **456 frames from 12 short videos**, laid out as contact sheets in `review/hr1/package/stage_a/sheets/`. Each sheet holds up to 20 frames, in order, with the video name, frame number and time printed above each frame. No model output is drawn on them.

1. Copy `review/hr1/package/stage_a/stage-a-TEMPLATE.csv` and name it `stage-a-<your-handle>.csv`.
2. Open the sheets one at a time. The `sheet` column in the CSV tells you which sheet each row belongs to.
3. For each frame, fill the `tail` column with exactly one of these words:

| answer | use it when |
|---|---|
| `visible` | you can see a cat's tail, or a clear stretch of it |
| `partial` | you can see only a small piece, such as the tip above the back or the base under the body, and you are sure it is tail |
| `not_visible` | no tail can be seen: it is hidden behind the body, out of the frame, or there is no cat in the frame at all |
| `cannot_tell` | the frame is too blurred, dark or small to judge, or you can see something long and thin but cannot decide whether it is a tail |

Some practical points:

- If there are two cats, answer `visible` or `partial` if you can see **either** cat's tail.
- A tail grows from the base of the spine, above the hind legs, and has no paw at the end. A leg ends in a paw. On a curled-up cat the tail is often wrapped along the body or under the chin, and it can be hard to separate from the body.
- `cannot_tell` is a real answer, not a failure. Please use it rather than guessing. Every row needs one of the four words; a blank row is treated as a mistake in the file.
- Some videos are old black-and-white films, and two contain no cat. These go quickly: `not_visible` for frames with no cat.
- Some cats are small in the frame. Zoom in with your image viewer; the sheets are full resolution at about 2000 pixels wide.
- The frames are 0.25 seconds apart, so neighbouring frames are a useful check. If a frame is ambiguous on its own, it is fine to use the frames on either side to decide.
- The `note` column is optional. Use it for anything you want to flag, such as "tail behind the person's arm".

When you finish, save the file and **lock** it as described under "Submitting". Do not change it after locking.

## Stage B: is the line on the tail? (about 30 minutes)

Stage B is released after every reviewer has locked Stage A. It contains 175 images, one per item, named `B001.jpg`, `B002.jpg` and so on, in a shuffled order that mixes the videos. Each image has three panels: the full frame with a **magenta line** drawn on it, a zoomed view with the same line, and the same zoomed view without the line so you can see what is underneath.

The line is the method's claim that "this is the tail". Fill the `on_tail` column of `stage-b-<your-handle>.csv` with one of:

| answer | use it when |
|---|---|
| `on_tail` | the line lies on a cat's tail for most of its length. Running a little past the tip or into the body at the base is fine |
| `not_on_tail` | the line lies mostly on something else: a leg, a paw, the back or rump, the face or ear, a person, furniture, the ground. Also use it for a line that runs along the body and only happens to touch the tail |
| `cannot_tell` | you cannot decide |

Judge each image on its own; ignore any memory of what you answered in Stage A for the same frame. A few items appear twice on purpose so we can see how consistent the task is. Please answer them as if you had not seen them before.

## Submitting

We use a two-step submission so that nobody's answers can influence anyone else's.

1. **Lock** your file by computing its SHA-256 fingerprint and posting only that fingerprint as a comment on [issue #79](https://github.com/in-c0/cat-pose-benchmark/issues/79), with the stage, your handle, and one line saying which of the files listed under "Before you start" you had seen, if any.

   - Windows: `certutil -hashfile stage-a-yourhandle.csv SHA256`
   - macOS: `shasum -a 256 stage-a-yourhandle.csv`
   - Linux: `sha256sum stage-a-yourhandle.csv`

2. **Upload** the file itself only when we ask, after every reviewer has locked that stage. You can attach it to the issue or open a pull request adding it to `review/hr1/submissions/stage_a/` (or `stage_b/`). The scorer checks the file against the fingerprint you posted, so please do not edit it in between, not even to fix a typo. If you notice a mistake after locking, leave it and mention it in the issue; a corrected file can be added as a separate, clearly labelled resubmission.

If the fingerprint step does not work for you, say so on the issue and we will find another way to lock your file.

## If something is unclear

Ask on [issue #79](https://github.com/in-c0/cat-pose-benchmark/issues/79), but please describe the problem in general terms ("what should I answer when the tail is behind a person's arm?") rather than naming a frame and your answer, because the other reviewer may read it.

Your answers are contributed under CC0 (see [CONTRIBUTING.md](../../CONTRIBUTING.md)). Each reviewer's file is kept separately and credited by handle. Where reviewers disagree, the frame is recorded as uncertain. Your answers are never averaged together, and they are never overruled by the model.
