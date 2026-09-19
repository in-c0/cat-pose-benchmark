"""Prospective holdout sampling — metadata only, precommitted (ChatGPT pass 11).

Pool: every file directly in one fixed Wikimedia Commons category, listed through the API
with continuation (no thumbnails, no video opened). Eligibility from metadata alone:
video MIME, licence CC0 / CC BY / public domain, duration >= 4 s, height >= 360, not one of
the four development clips, title/description free of a fixed "not ordinary footage"
keyword list (animation, adverts, broadcast productions), one clip per uploader. Selection: sort canonical titles,
shuffle with the recorded seed, take the first N eligible with distinct uploaders. A clip
that later proves unusable (corrupt, not a cat video) is replaced by the next in the frozen
order; never for being hard, boring, tail-less or bad for the method.

    python -m review.holdout.sample_pool --category "Videos of cats" --seed 20260920 --n 4
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import random
import re
from pathlib import Path

import requests

API = "https://commons.wikimedia.org/w/api.php"
UA = "cat-pose-benchmark/0.1 (holdout sampling; https://github.com/in-c0/cat-pose-benchmark)"
HERE = Path(__file__).resolve().parent
DEV_CLIPS = {"cat jumping backwards.webm", "cat plays.webm", "black cat walking.webm", "cat licking tail.ogv"}
# Metadata-only proxy for "real ordinary footage": a fixed keyword list applied to the title
# and description, frozen before the pool was drawn. Nothing else excludes a clip.
NOT_ORDINARY = re.compile(r"animat|cartoon|commercial|advert|trailer|documentary|music video|TV|ZDF|Samsung|montage|compilation", re.I)
OK_LICENCE = re.compile(r"^(CC0|CC BY( \d\.\d)?( [a-z]{2})?|Public domain)$", re.I)


def category_members(category: str) -> list[str]:
    titles, cont = [], {}
    while True:
        r = requests.get(API, params={"action": "query", "list": "categorymembers", "cmtitle": f"Category:{category}", "cmtype": "file", "cmlimit": 500, "format": "json", **cont}, headers={"User-Agent": UA}, timeout=60).json()
        titles += [m["title"] for m in r["query"]["categorymembers"]]
        if "continue" not in r:
            return titles
        cont = r["continue"]


def file_info(titles: list[str]) -> list[dict]:
    out = []
    for i in range(0, len(titles), 50):
        batch = titles[i : i + 50]
        r = requests.get(API, params={"action": "query", "prop": "imageinfo", "titles": "|".join(batch), "iiprop": "url|size|mime|extmetadata|user", "iiextmetadatafilter": "LicenseShortName|Artist|Credit|ImageDescription", "format": "json"}, headers={"User-Agent": UA}, timeout=60).json()
        for page in r["query"]["pages"].values():
            ii = (page.get("imageinfo") or [{}])[0]
            em = ii.get("extmetadata", {})
            out.append({
                "title": page["title"], "url": ii.get("url"), "mime": ii.get("mime"), "width": ii.get("width"), "height": ii.get("height"),
                "duration_s": ii.get("duration"), "uploader": ii.get("user"), "licence": em.get("LicenseShortName", {}).get("value"),
                "artist": re.sub(r"<[^>]+>", "", em.get("Artist", {}).get("value", ""))[:80], "description": re.sub(r"<[^>]+>", "", em.get("ImageDescription", {}).get("value", ""))[:200],
            })
    return out


def eligible(f: dict, min_s: float, min_h: int) -> tuple[bool, str]:
    if not (f["mime"] or "").startswith("video/"):
        return False, "not_video"
    if f["title"].removeprefix("File:").lower() in DEV_CLIPS:
        return False, "development_clip"
    if NOT_ORDINARY.search(" ".join((f["title"], f["description"], f["uploader"] or "", f["artist"]))):
        return False, "not_ordinary_footage"
    if not f["licence"] or not OK_LICENCE.match(f["licence"].strip()):
        return False, f"licence:{f['licence']}"
    if not f["duration_s"] or f["duration_s"] < min_s:
        return False, f"duration:{f['duration_s']}"
    if not f["height"] or f["height"] < min_h:
        return False, f"height:{f['height']}"
    return True, "ok"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--category", default="Videos of cats")
    p.add_argument("--seed", type=int, default=20260920)
    p.add_argument("--n", type=int, default=4)
    p.add_argument("--min-seconds", type=float, default=4.0)
    p.add_argument("--min-height", type=int, default=360)
    a = p.parse_args()
    titles = sorted(set(category_members(a.category)))
    files = file_info(titles)
    for f in files:
        f["eligible"], f["reason"] = eligible(f, a.min_seconds, a.min_height)
    order = sorted(f["title"] for f in files)
    random.Random(a.seed).shuffle(order)
    by_title = {f["title"]: f for f in files}
    selected, seen_uploaders, rank = [], set(), []
    for k, t in enumerate(order):
        f = by_title[t]
        if not f["eligible"]:
            continue
        rank.append(t)
        if f["uploader"] in seen_uploaders:
            continue
        seen_uploaders.add(f["uploader"])
        selected.append({"rank": len(rank), "shuffle_position": k, **f})
        if len(selected) == a.n:
            break
    payload = {
        "protocol": "metadata-only random selection; see module docstring", "category": a.category, "seed": a.seed, "n": a.n,
        "min_seconds": a.min_seconds, "min_height": a.min_height, "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "pool_size": len(files), "eligible": sum(f["eligible"] for f in files), "reasons": {r: sum(1 for f in files if f["reason"] == r) for r in sorted({f["reason"] for f in files})},
        "shuffled_eligible_order": rank + [t for t in order if t not in rank and by_title[t]["eligible"]],
        "selected": selected,
    }
    (HERE / "pool.json").write_text(json.dumps({"files": files}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (HERE / "selection.json").write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in payload.items() if k not in ("shuffled_eligible_order", "selected")}, indent=1))
    for s in selected:
        print(s["rank"], s["title"], s["licence"], s["duration_s"], f"{s['width']}x{s['height']}", s["uploader"])


if __name__ == "__main__":
    main()
