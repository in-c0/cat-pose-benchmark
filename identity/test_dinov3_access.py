from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from identity.dinov3_access import (
    STATUS_GATE_NOT_ACCEPTED,
    STATUS_MODEL_NOT_FOUND,
    STATUS_NETWORK_UNREACHABLE,
    STATUS_OK,
    STATUS_TOKEN_INVALID,
    STATUS_TOKEN_MISSING,
    STATUS_UNEXPECTED,
    DINOv3AccessError,
    HttpResponse,
    check_access,
    followup_note,
    load_pin,
    resolve_token,
)

WHOAMI = "api/whoami-v2"
MODEL_INFO = "api/models/"
RESOLVE = "/resolve/"


def fake_transport(*, whoami=200, info=200, entitlement=200, sha="deadbeef", raise_on=None):
    """Build a transport that answers each probe with a scripted status."""

    def send(method: str, url: str, token: "str | None") -> HttpResponse:
        if raise_on and raise_on in url:
            raise DINOv3AccessError("network failure reaching https://huggingface.co: blocked")
        if WHOAMI in url:
            return HttpResponse(whoami, json.dumps({"name": "test-account"}))
        if RESOLVE in url:
            return HttpResponse(entitlement, "")
        if MODEL_INFO in url:
            return HttpResponse(info, json.dumps({"sha": sha, "gated": "manual"}))
        raise AssertionError(f"unexpected probe url: {url}")

    return send


class LoadPinTests(unittest.TestCase):
    def test_repository_pin_is_wellformed(self) -> None:
        pin = load_pin()
        self.assertEqual(pin["pin_version"], "DINOV3-S-PIN-v0")
        self.assertTrue(pin["repo_id"])
        self.assertTrue(pin["gated"])
        self.assertEqual(pin["access"]["requires_token_secret"], "HF_TOKEN")

    def test_pin_does_not_claim_unverified_facts(self) -> None:
        pin = load_pin()
        # An unverified repo id cannot carry a claimed revision; a verified one must
        # carry a real commit SHA rather than a floating branch name.
        if pin["repo_id_verified"]:
            self.assertTrue(pin["revision_verified"])
            self.assertRegex(pin["revision"], r"^[0-9a-f]{40}$")
        else:
            self.assertIsNone(pin["revision"])
            self.assertFalse(pin["revision_verified"])

    def test_repository_pin_is_frozen_to_a_commit(self) -> None:
        # The backbone is part of the ID1.0 provenance surface: a floating revision
        # would let identity descriptors change under an unchanged spec.
        pin = load_pin()
        self.assertTrue(pin["repo_id_verified"])
        self.assertRegex(pin["revision"], r"^[0-9a-f]{40}$")
        self.assertIn("workflow_run", pin["verified_by"])

    def test_rejects_verified_pin_with_a_branch_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pin.json"
            path.write_text(
                json.dumps(
                    {
                        "pin_version": "DINOV3-S-PIN-v0",
                        "repo_id": "x/y",
                        "revision": "main",
                        "revision_verified": True,
                    }
                ),
                "utf-8",
            )
            with self.assertRaises(DINOv3AccessError):
                load_pin(path)

    def test_rejects_foreign_pin_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pin.json"
            path.write_text(json.dumps({"pin_version": "other", "repo_id": "x/y"}), "utf-8")
            with self.assertRaises(DINOv3AccessError):
                load_pin(path)

    def test_rejects_pin_without_repo_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pin.json"
            path.write_text(json.dumps({"pin_version": "DINOV3-S-PIN-v0"}), "utf-8")
            with self.assertRaises(DINOv3AccessError):
                load_pin(path)


class ResolveTokenTests(unittest.TestCase):
    def test_prefers_hf_token(self) -> None:
        self.assertEqual(resolve_token({"HF_TOKEN": "a", "HUGGING_FACE_HUB_TOKEN": "b"}), "a")

    def test_falls_back_to_hub_variables(self) -> None:
        self.assertEqual(resolve_token({"HUGGINGFACE_HUB_TOKEN": "c"}), "c")

    def test_blank_and_whitespace_are_absent(self) -> None:
        self.assertIsNone(resolve_token({}))
        self.assertIsNone(resolve_token({"HF_TOKEN": "   "}))

    def test_strips_padding(self) -> None:
        self.assertEqual(resolve_token({"HF_TOKEN": "  hf_x  "}), "hf_x")


class CheckAccessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pin = load_pin()

    def _check(self, **kwargs):
        token = kwargs.pop("token", "hf_fake")
        return check_access(pin=self.pin, token=token, transport=fake_transport(**kwargs))

    def test_granted_access_reports_ok_and_resolved_sha(self) -> None:
        report = self._check()
        self.assertEqual(report["status"], STATUS_OK)
        self.assertTrue(report["ok"])
        self.assertEqual(report["resolved_sha"], "deadbeef")
        self.assertEqual(report["account"], "test-account")
        self.assertNotIn("remedy", report)

    def test_redirect_to_cdn_counts_as_entitlement(self) -> None:
        # The transport deliberately does not follow the redirect, so 302 is terminal
        # and already proves the account may fetch the weights.
        report = self._check(entitlement=302)
        self.assertEqual(report["status"], STATUS_OK)

    def test_upstream_head_drift_is_surfaced_without_failing(self) -> None:
        # A frozen revision that no longer matches the branch head is still
        # reproducible, but the divergence is provenance-relevant.
        report = self._check(sha="0" * 40)
        self.assertEqual(report["status"], STATUS_OK)
        self.assertTrue(report["upstream_head_moved"])

    def test_no_drift_flag_when_head_matches_the_pin(self) -> None:
        report = self._check(sha=self.pin["revision"])
        self.assertEqual(report["status"], STATUS_OK)
        self.assertNotIn("upstream_head_moved", report)

    def test_missing_token_is_named_as_such(self) -> None:
        report = check_access(pin=self.pin, token=None, transport=fake_transport())
        self.assertEqual(report["status"], STATUS_TOKEN_MISSING)
        self.assertIn("HF_TOKEN", report["remedy"])

    def test_invalid_token_is_distinguished_from_the_gate(self) -> None:
        report = self._check(whoami=401)
        self.assertEqual(report["status"], STATUS_TOKEN_INVALID)

    def test_valid_token_without_granted_gate(self) -> None:
        report = self._check(info=403, entitlement=403)
        self.assertEqual(report["status"], STATUS_GATE_NOT_ACCEPTED)
        self.assertIn("accept the access conditions", report["remedy"])

    def test_gated_401_on_entitlement_is_the_gate_not_the_credential(self) -> None:
        # whoami already accepted the token, so a 401 further down is an entitlement problem.
        report = self._check(entitlement=401)
        self.assertEqual(report["status"], STATUS_GATE_NOT_ACCEPTED)

    def test_wrong_repo_id_is_reported_as_not_found(self) -> None:
        report = self._check(info=404)
        self.assertEqual(report["status"], STATUS_MODEL_NOT_FOUND)
        self.assertIn("dinov3_backbone_pin.json", report["remedy"])

    def test_blocked_network_is_not_reported_as_a_credential_failure(self) -> None:
        report = self._check(raise_on="whoami")
        self.assertEqual(report["status"], STATUS_NETWORK_UNREACHABLE)
        self.assertIn("network policy", report["remedy"])

    def test_unexpected_status_fails_closed(self) -> None:
        report = self._check(entitlement=500)
        self.assertEqual(report["status"], STATUS_UNEXPECTED)
        self.assertFalse(report["ok"])

    def test_report_never_contains_the_token(self) -> None:
        secret = "hf_supersecrettokenvalue"
        for kwargs in ({}, {"whoami": 401}, {"entitlement": 403}, {"info": 404}):
            report = check_access(
                pin=self.pin, token=secret, transport=fake_transport(**kwargs)
            )
            self.assertNotIn(secret, json.dumps(report))

    def test_every_failure_carries_an_actionable_remedy(self) -> None:
        for kwargs in (
            {"token": None},
            {"whoami": 401},
            {"entitlement": 403},
            {"info": 404},
            {"raise_on": "whoami"},
            {"entitlement": 500},
        ):
            report = self._check(**kwargs)
            self.assertFalse(report["ok"])
            self.assertTrue(report["remedy"].strip())


if __name__ == "__main__":
    unittest.main()


class FollowupNoteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pin = load_pin()

    def test_frozen_pin_at_head_says_nothing(self) -> None:
        # The freeze instruction must not keep printing once the pin is already frozen.
        report = {"ok": True, "resolved_sha": self.pin["revision"]}
        self.assertIsNone(followup_note(report, self.pin))

    def test_unfrozen_pin_is_told_how_to_freeze(self) -> None:
        unfrozen = dict(self.pin, revision_verified=False)
        note = followup_note({"ok": True, "resolved_sha": "a" * 40}, unfrozen)
        self.assertIn("a" * 40, note)
        self.assertIn("revision_verified", note)

    def test_drift_is_reported_as_a_rebaselining_decision(self) -> None:
        report = {"ok": True, "resolved_sha": "b" * 40, "upstream_head_moved": True}
        note = followup_note(report, self.pin)
        self.assertIn("b" * 40, note)
        self.assertIn("re-baselining", note)

    def test_no_note_without_a_resolved_sha(self) -> None:
        self.assertIsNone(followup_note({"ok": True}, self.pin))
