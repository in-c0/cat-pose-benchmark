from detail.tail_audit import anchors
from detail.tail_track import runs


def _statuses(s: str) -> list[str]:
    m = {"C": "no_cat", "N": "temporal_none", "B": "no_tail_box", "O": "ok", "P": "all_look_like_paw"}
    return [m[c] for c in s]


def test_runs_classify_by_bounding_seeds():
    got = [(g["first"], g["last"], g["kind"]) for g in runs(_statuses("CCNNBNNOOOOOOBNBOOBBOOOO"))]
    assert got == [(0, 6, "one_sided"), (13, 15, "two_sided"), (18, 19, "two_sided")]


def test_runs_paw_bounded_is_unseeded_or_one_sided():
    got = [(g["first"], g["last"], g["kind"]) for g in runs(_statuses("NNNNNOOOOPNPPNPNNNNOOPPP"))]
    assert got == [(0, 4, "one_sided"), (10, 10, "unseeded"), (13, 13, "unseeded"), (15, 18, "one_sided")]


def test_anchors_within_horizon():
    ok = [1, 2, 5, 9, 10]
    assert anchors(ok, 5, 3) == (2, None)
    assert anchors(ok, 2, 3) == (1, 5)
    assert anchors(ok, 9, 3) == (None, 10)
    assert anchors(ok, 1, 3) == (None, 2)
