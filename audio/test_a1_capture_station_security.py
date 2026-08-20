from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from audio.a1_capture_station_secure import (
    validate_host_header,
    validate_mutation_timing,
    validate_post_request,
)


class A1CaptureStationSecurityTests(unittest.TestCase):
    def test_loopback_host_with_matching_port_is_accepted(self) -> None:
        self.assertEqual(("127.0.0.1", 8765), validate_host_header("127.0.0.1:8765", 8765))
        self.assertEqual(("localhost", 8765), validate_host_header("localhost:8765", 8765))
        self.assertEqual(("::1", 8765), validate_host_header("[::1]:8765", 8765))

    def test_non_loopback_or_wrong_port_host_is_rejected(self) -> None:
        for host in ("attacker.example:8765", "127.0.0.1:9999", None):
            with self.subTest(host=host):
                with self.assertRaises(ValueError):
                    validate_host_header(host, 8765)

    def test_same_origin_json_request_is_accepted(self) -> None:
        validate_post_request(
            path="/api/start",
            host_header="127.0.0.1:8765",
            origin_header="http://127.0.0.1:8765",
            sec_fetch_site="same-origin",
            content_type="application/json; charset=utf-8",
            server_port=8765,
        )

    def test_cross_origin_request_is_rejected_even_with_loopback_host(self) -> None:
        with self.assertRaises(ValueError):
            validate_post_request(
                path="/api/start",
                host_header="127.0.0.1:8765",
                origin_header="https://attacker.example",
                sec_fetch_site="cross-site",
                content_type="text/plain",
                server_port=8765,
            )

    def test_dns_rebinding_style_host_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            validate_post_request(
                path="/api/start",
                host_header="rebind.attacker.example:8765",
                origin_header="http://rebind.attacker.example:8765",
                sec_fetch_site="same-origin",
                content_type="application/json",
                server_port=8765,
            )

    def test_origin_is_required_for_state_changing_requests(self) -> None:
        with self.assertRaisesRegex(ValueError, "Origin header is required"):
            validate_post_request(
                path="/api/start",
                host_header="127.0.0.1:8765",
                origin_header=None,
                sec_fetch_site=None,
                content_type="application/json",
                server_port=8765,
            )

    def test_simple_csrf_content_types_cannot_reach_json_api(self) -> None:
        for content_type in ("text/plain", "application/x-www-form-urlencoded", "multipart/form-data"):
            with self.subTest(content_type=content_type):
                with self.assertRaisesRegex(ValueError, "application/json"):
                    validate_post_request(
                        path="/api/start",
                        host_header="localhost:8765",
                        origin_header="http://localhost:8765",
                        sec_fetch_site="same-origin",
                        content_type=content_type,
                        server_port=8765,
                    )

    def test_audio_upload_requires_wav_content_type(self) -> None:
        validate_post_request(
            path="/api/audio/a1-safe-id",
            host_header="localhost:8765",
            origin_header="http://localhost:8765",
            sec_fetch_site="same-origin",
            content_type="audio/wav",
            server_port=8765,
        )
        for content_type in ("text/plain", "application/octet-stream", "application/json"):
            with self.subTest(content_type=content_type):
                with self.assertRaisesRegex(ValueError, "audio/wav"):
                    validate_post_request(
                        path="/api/audio/a1-safe-id",
                        host_header="localhost:8765",
                        origin_header="http://localhost:8765",
                        sec_fetch_site="same-origin",
                        content_type=content_type,
                        server_port=8765,
                    )

    def test_fetch_metadata_cannot_claim_cross_site(self) -> None:
        for site in ("cross-site", "same-site"):
            with self.subTest(site=site):
                with self.assertRaisesRegex(ValueError, "cross-site"):
                    validate_post_request(
                        path="/api/finalize/a1-safe-id",
                        host_header="localhost:8765",
                        origin_header="http://localhost:8765",
                        sec_fetch_site=site,
                        content_type="application/json",
                        server_port=8765,
                    )

    def test_audio_reservation_must_arrive_inside_frozen_evidence_window(self) -> None:
        t0 = datetime(2026, 8, 21, 0, 0, 0, tzinfo=timezone.utc)
        validate_mutation_timing(
            path="/api/reserve-audio/a1-safe-id",
            event_start_time=t0.isoformat(),
            now=t0 + timedelta(milliseconds=4999),
        )
        with self.assertRaisesRegex(ValueError, "5000 ms evidence cutoff"):
            validate_mutation_timing(
                path="/api/reserve-audio/a1-safe-id",
                event_start_time=t0.isoformat(),
                now=t0 + timedelta(milliseconds=5001),
            )

    def test_outcome_finalization_is_server_blocked_before_60_seconds(self) -> None:
        t0 = datetime(2026, 8, 21, 0, 0, 0, tzinfo=timezone.utc)
        with self.assertRaisesRegex(ValueError, "60000 ms horizon"):
            validate_mutation_timing(
                path="/api/finalize/a1-safe-id",
                event_start_time=t0.isoformat(),
                now=t0 + timedelta(milliseconds=59999),
            )
        validate_mutation_timing(
            path="/api/finalize/a1-safe-id",
            event_start_time=t0.isoformat(),
            now=t0 + timedelta(milliseconds=60000),
        )


if __name__ == "__main__":
    unittest.main()
