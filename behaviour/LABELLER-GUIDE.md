# BH1 labeller guide

Thank you for helping. You will watch short pieces of ordinary cat video and say what one cat is doing in each piece. There are no trick questions, and "cannot tell" is always an acceptable answer.

Plan on about 30–60 seconds per segment. A batch of 100 clips is roughly 600 segments, which is several sessions of work, so take breaks. You can stop and come back at any time.

## Before you start

Please check that none of these apply to you:

- you own this repository, or you filled in the cat identity file for BH1;
- you have opened anything under `behaviour/work/`, or a file called `key.json`;
- you are an AI system, or you are using one to choose labels.

Please also do **not** search for the clips on Wikimedia Commons or anywhere else. Their titles often name the behaviour, which would tell you the answer. If you recognise a clip anyway, label what you see and mention it in the note.

When you send your file, you will be asked which project files and Commons pages you had seen beforehand. Having seen something does not disqualify you. It is reported next to your numbers.

## What you receive

- One **sheet** per clip (`BH1-C001.jpg`, ...). Each row is one 2-second segment: eight frames left to right in time order. The header describes the **target cat**, for example "the grey tabby on the left". Only the target cat counts.
- One **silent video** per segment (`BH1-C001-S00.mp4`, ...), so you can see the movement.
- `label-TEMPLATE.csv`, with one row per segment.
- `media.json`, which lists the SHA-256 of every file. Use it to check that your files arrived intact.

## What to do

1. Read section 2 of [PROTOCOL.md](PROTOCOL.md) ("Behaviour classes") once, including the boundary-case table. It is the only definition of the labels. Keep it open while you work; you are not expected to memorise it.
2. For each segment, watch the video (as many times as you like) and look at its row on the sheet.
3. In the `behaviour` column, write exactly one of:

   `walk` · `sit_lie` · `groom` · `jump` · `play_other` · `cannot_tell`

4. Use `note` for anything you want to say: a clip you recognised, editing in the footage, a second cat that confused you. Notes are read but never scored.

Rules of thumb, all from the protocol:

- If a jump takes off or lands inside the segment, it is `jump`.
- Otherwise, choose the activity that fills more than half of the 2 seconds. If nothing does, write `cannot_tell`.
- Describe what the body does, not what the cat might feel or want. There is no label for mood, and you should not try to fit one in.
- If you are stuck between two labels after looking carefully, `cannot_tell` is better than a guess.

Every row needs an answer. A blank row sends the whole file back to you.

## Sending your labels

1. Save the file as `labels-<your handle>.csv`, in UTF-8, with the same columns.
2. Compute its SHA-256 (for example `certutil -hashfile labels-you.csv SHA256` on Windows or `shasum -a 256 labels-you.csv` on macOS and Linux).
3. Post **only the digest** on the project's review issue. This locks your answers before anyone else's are seen.
4. When every labeller has posted a digest, you will be asked to send the file itself.

If you need to correct something after posting, do not edit the sent file. Make a new file, `labels-<your handle>-r2.csv`, and post its digest the same way. The newest file is scored, and both are kept.
