# Clip-level annotation instructions (protocol v1)

Rules that decide the frame-truth labels. They live here so a decision can be re-derived
rather than remembered.

## commons-cat-plays (tuxedo cat, 4 fps, 33 frames)

- The tail is **all black**. A black limb that ends in a white paw is a leg, not the tail.
  This rule alone settles f000–f003 (raised hind legs), f009–f012 (side-lying, hind legs
  toward the camera) and f018 (paws), which earlier readings had called tail.
- The tail is out at f004–f005 (extends up-left, no white tip), f007–f008 (only the tip
  shows: `partial`), and f019–f020 (curled, upper right).
- Everywhere else the tail is under the body: `not_visible`, confidence `medium` because
  the body hides it rather than the frame edge.

## commons-cat-jumping-backwards (3 fps, 24 frames; two cats)

- `target_cat` is the cat the body run boxed on that frame (the largest detection). A
  method that draws the other cat's tail is `wrong_cat`, which is still a wrong assertion.
- f000, f001, f018 are motion-blurred: `uncertain`, excluded.
- f019: the tuxedo cat is on the scratcher with its tail behind the body: `not_visible`.

## commons-black-cat-walking (2 fps, 38 frames)

- f000: the cat faces the camera and the tail is behind the body: `not_visible`.
- f001, f020, f030–f033: the tail shows only as a raised tip or base above the back:
  `partial`.
- f036–f037: extreme close-up, the tail fills most of the frame; the body run found no
  cat but the tail is visible: `visible`.

## commons-cat-licking-tail (2 fps, 52 frames)

- f000–f026: the tail lies along the sofa edge below the cat: `visible`.
- f027–f035: the cat has curled around; a dark strip under the chin is the tucked tail,
  mostly hidden: `partial`, confidence `low`, condition `occlusion`.
- f036–f051: curled tight, tail under the body: `not_visible`, confidence `medium`.
