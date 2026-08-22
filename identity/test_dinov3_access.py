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
        # The repo id and revision cannot be confirmed without reaching Hugging Face,
        # so the pin must not assert them as verified until a preflight says so.
        if not pin["repo_id_verified"]:
            self.assertIsNone(pin["revision"])
            self.assertFalse(pin["revision_verified"])

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
