"""BH1 clip pool: a metadata-only, seeded draw from Wikimedia Commons (PROTOCOL.md section 4).

Extends ``review/holdout/sample_pool.py`` in three ways:

* the pool is every file in ``Category:Videos of cats`` **and its subcategories down to
  depth 2**, walked breadth-first so a category reached by two routes is recorded at its
  shallowest depth whatever order the API lists it in;
* every clip carries a ``cat_id`` field, ``null`` until a human fills it in the identity
  pass (PROTOCOL.md section 5). Different uploaders are not assumed to mean different cats;
* licences are classified, not only filtered. CC0, CC BY and public domain are
  ``licence_ok``. CC BY-SA is recorded as ``by_sa`` and carries its own eligibility verdict,
  but the selection rule cannot take it unless the owner allows it (exception
  2026-10-11-cat-pose-behaviour-feasibility-df26). Everything else is ``other``.

The other eligibility checks are the holdout's, imported unchanged: video MIME, duration
>= 4 s, height >= 360, not a development clip, title/description free of the frozen
"not ordinary footage" keyword list.

The draw fixes one order over the whole pool: sort canonical titles, shuffle with the
recorded seed. Selection walks that order and takes each eligible clip unless its uploader
already has ``cap`` clips. The cap and the BY-SA switch are the owner's rulings, so this file
commits the pool, the seed and the order, plus the clip and uploader counts every candidate
ruling would give, and selects nothing until the ruling exists:

    python -m behaviour.sample_pool draw                        # fetch, classify, freeze order (done 2026-10-17)
    python -m behaviour.sample_pool select --cap 10             # after the ruling; writes pool/selection.json
    python -m behaviour.sample_pool select --cap 10 --include-by-sa
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import random
import re
from collections import Counter, deque
from pathlib import Path
from typing import Any

from review.holdout.sample_pool import API, OK_LICENCE, UA, eligible

HERE = Path(__file__).resolve().parent
POOL_DIR = HERE / "pool"
ROOT_CATEGORY = "Videos of cats"
MAX_DEPTH = 2
SEED = 20261017
BY_SA = re.compile(r"^CC BY-SA( \d\.\d)?( [a-z]{2})?$", re.I)
# caps and BY-SA settings whose counts are recorded for the owner; any other value is still allowed
SCENARIO_CAPS = (1, 3, 5, 10, 20, None)


def _get(params: dict[str, Any]) -> dict[str, Any]:
    import requests

    return requests.get(API, params={**params, "format": "json"}, headers={"User-Agent": UA}, timeout=60).json()


def _members(category: str, kind: str) -> list[str]:
    out, cont = [], {}
    while True:
        r = _get({"action": "query", "list": "categorymembers", "cmtitle": category, "cmtype": kind, "cmlimit": 500, **cont})
        out += [m["title"] for m in r["query"]["categorymembers"]]
        if "continue" not in r:
            return out
        cont = r["continue"]


def walk_categories(root: str, max_depth: int, members=_members) -> tuple[dict[str, int], dict[str, list[str]]]:
    """Breadth-first walk. Returns {category: shallowest depth} and {file: [categories it is in]}.

    ``members(category, kind)`` is injectable for tests."""
    depth = {root: 0}
    found: dict[str, list[str]] = {}
    queue = deque([root])
    while queue:
        cat = queue.popleft()
        for f in members(cat, "file"):
            found.setdefault(f, []).append(cat)
        if depth[cat] == max_depth:
            continue
        for sub in sorted(members(cat, "subcat")):
            if sub not in depth:
                depth[sub] = depth[cat] + 1
                queue.append(sub)
    return depth, {f: sorted(cs) for f, cs in found.items()}


def file_info(titles: list[str]) -> list[dict[str, Any]]:
    out = []
    for i in range(0, len(titles), 50):
        r = _get({"action": "query", "prop": "imageinfo", "titles": "|".join(titles[i:i + 50]), "iiprop": "url|size|mime|extmetadata|user",
                  "iiextmetadatafilter": "LicenseShortName|Artist|ImageDescription"})
        for page in r["query"]["pages"].values():
            ii = (page.get("imageinfo") or [{}])[0]
            em = ii.get("extmetadata", {})
            out.append({
                "title": page["title"], "url": ii.get("url"), "mime": ii.get("mime"), "width": ii.get("width"), "height": ii.get("height"),
                "duration_s": ii.get("duration"), "uploader": ii.get("user"), "licence": em.get("LicenseShortName", {}).get("value"),
                "artist": re.sub(r"<[^>]+>", "", em.get("Artist", {}).get("value", ""))[:80],
                "description": re.sub(r"<[^>]+>", "", em.get("ImageDescription", {}).get("value", ""))[:200],
            })
    return out


def licence_class(licence: str | None) -> str:
    lic = (licence or "").strip()
    if OK_LICENCE.match(lic):
        return "licence_ok"
    if BY_SA.match(lic):
        return "by_sa"
    return "other"


def classify(f: dict[str, Any], min_s: float = 4.0, min_h: int = 360) -> dict[str, Any]:
    """Holdout eligibility, with BY-SA judged on every other criterion as if its licence were allowed."""
    lc = licence_class(f["licence"])
    probe = dict(f, licence="CC BY 4.0") if lc == "by_sa" else f
    ok, reason = eligible(probe, min_s, min_h)
    if lc == "by_sa" and ok:
        reason = "ok_if_by_sa_allowed"
    elif lc == "by_sa":
        reason = f"by_sa_and_{reason}"
    return {**f, "licence_class": lc, "eligible": ok and lc == "licence_ok", "eligible_if_by_sa": ok, "reason": reason, "cat_id": None}


def frozen_order(titles: list[str], seed: int) -> list[str]:
    order = sorted(titles)
    random.Random(seed).shuffle(order)
    return order


def select(files: dict[str, dict[str, Any]], order: list[str], cap: int | None, include_by_sa: bool, n: int | None = None) -> list[dict[str, Any]]:
    """Walk the frozen order; take each eligible clip unless its uploader already has ``cap`` clips."""
    per_uploader: Counter = Counter()
    out = []
    for pos, t in enumerate(order):
        f = files[t]
        if not (f["eligible_if_by_sa"] if include_by_sa else f["eligible"]):
            continue
        if cap is not None and per_uploader[f["uploader"]] >= cap:
            continue
        per_uploader[f["uploader"]] += 1
        out.append({"shuffle_position": pos, "title": t, "uploader": f["uploader"], "licence": f["licence"], "duration_s": f["duration_s"]})
        if n is not None and len(out) == n:
            break
    return out


def scenarios(files: dict[str, dict[str, Any]], order: list[str]) -> list[dict[str, Any]]:
    rows = []
    for by_sa in (False, True):
        for cap in SCENARIO_CAPS:
            sel = select(files, order, cap, by_sa)
            up = Counter(s["uploader"] for s in sel)
            top = up.most_common(1)[0] if up else (None, 0)
            rows.append({"include_by_sa": by_sa, "cap_per_uploader": cap, "clips": len(sel), "uploaders": len(up),
                         "largest_uploader": top[0], "largest_uploader_clips": top[1],
                         "seconds_total": round(sum(min(s["duration_s"] or 0, 20.0) for s in sel), 1)})
    return rows


def draw(seed: int = SEED) -> dict[str, Any]:
    depth, found = walk_categories(f"Category:{ROOT_CATEGORY}", MAX_DEPTH)
    titles = sorted(found)
    files = [classify(f) for f in file_info(titles)]
    for f in files:
        f["categories"] = found.get(f["title"], [])
        f["min_depth"] = min(depth[c] for c in f["categories"]) if f["categories"] else None
    by_title = {f["title"]: f for f in files}
    order = frozen_order(list(by_title), seed)
    uploaders_ok = Counter(f["uploader"] for f in files if f["eligible"])
    payload = {
        "protocol": "behaviour/PROTOCOL.md section 4; behaviour/sample_pool.py",
        "root_category": f"Category:{ROOT_CATEGORY}", "max_depth": MAX_DEPTH, "seed": seed,
        "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "categories": {c: d for c, d in sorted(depth.items())},
        "counts": {
            "files": len(files),
            "videos": sum(1 for f in files if (f["mime"] or "").startswith("video/")),
            "eligible": sum(f["eligible"] for f in files),
            "eligible_if_by_sa": sum(f["eligible_if_by_sa"] for f in files),
            "uploaders_eligible": len(uploaders_ok),
            "largest_uploader_eligible": list(uploaders_ok.most_common(1)[0]) if uploaders_ok else None,
            "licence_class": dict(Counter(f["licence_class"] for f in files)),
            "reasons": dict(sorted(Counter(f["reason"] for f in files).items())),
        },
        "scenarios": scenarios(by_title, order),
        "shuffled_order": order,
    }
    POOL_DIR.mkdir(parents=True, exist_ok=True)
    (POOL_DIR / "pool.json").write_text(json.dumps({"files": sorted(files, key=lambda f: f["title"])}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (POOL_DIR / "draw.json").write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def load_pool() -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    files = {f["title"]: f for f in json.loads((POOL_DIR / "pool.json").read_text(encoding="utf-8"))["files"]}
    return files, json.loads((POOL_DIR / "draw.json").read_text(encoding="utf-8"))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("draw", help="fetch the pool from Commons and freeze the order (overwrites pool/)")
    d.add_argument("--seed", type=int, default=SEED)
    s = sub.add_parser("select", help="apply the owner's ruling to the frozen order; no refetch")
    s.add_argument("--cap", type=int, required=True, help="max clips per uploader (0 = no cap)")
    s.add_argument("--include-by-sa", action="store_true")
    s.add_argument("--ruling", required=True, help="where the ruling is recorded (exception id or issue link)")
    a = p.parse_args()
    if a.cmd == "draw":
        payload = draw(a.seed)
        print(json.dumps(payload["counts"], indent=1, ensure_ascii=False))
        for row in payload["scenarios"]:
            print(row)
        return
    files, drawn = load_pool()
    cap = a.cap or None
    sel = select(files, drawn["shuffled_order"], cap, a.include_by_sa)
    out = {"protocol": "behaviour/PROTOCOL.md section 4", "seed": drawn["seed"], "retrieved_at": drawn["retrieved_at"],
           "cap_per_uploader": cap, "include_by_sa": a.include_by_sa, "ruling": a.ruling,
           "selected_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "selected": sel}
    (POOL_DIR / "selection.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(sel)} clips from {len({s['uploader'] for s in sel})} uploaders")


if __name__ == "__main__":
    main()
