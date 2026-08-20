from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "scripts" / "start-h0-capture.ps1"
GITIGNORE = ROOT / ".gitignore"
CORE_STATION = ROOT / "audio" / "a1_capture_station.py"


class H0LauncherContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.launcher = LAUNCHER.read_text(encoding="utf-8")
        cls.gitignore = GITIGNORE.read_text(encoding="utf-8")
        cls.core_station = CORE_STATION.read_text(encoding="utf-8")

    def test_private_local_data_is_git_ignored(self) -> None:
        lines = {
            line.strip()
            for line in self.gitignore.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
        self.assertIn("local-data/", lines)

    def test_launcher_delegates_to_canonical_secure_station(self) -> None:
        self.assertIn("audio.a1_capture_station_secure", self.launcher)
        self.assertIn("'--open-browser'", self.launcher)
        self.assertIn("local-data", self.launcher)
        self.assertIn("ct1-h0", self.launcher)

        # The launcher may import the secure station for preflight and execute that
        # module. It must not start a second capture server or any evaluation path.
        forbidden_execution_tokens = (
            "audio.acoustic_baselines",
            "audio.personalisation",
            "latent.l1_discovery",
            "context.ct1_baseline",
            "sklearn",
            "predict_proba",
        )
        for token in forbidden_execution_tokens:
            self.assertNotIn(token, self.launcher)

    def test_local_defaults_persist_only_pseudonymous_subject_and_household(self) -> None:
        match = re.search(
            r"\$localDefaults\s*=\s*\[ordered\]@\{(?P<body>.*?)\n\s*\}",
            self.launcher,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(match)
        body = match.group("body")
        keys = re.findall(r"^\s*([A-Za-z0-9_]+)\s*=", body, flags=re.MULTILINE)
        self.assertEqual(["subject_id", "household_id"], keys)

        for forbidden in (
            "event_id =",
            "outcome =",
            "audio =",
            "hypothesis =",
            "model =",
            "score =",
            "performance =",
        ):
            self.assertNotIn(forbidden, body.lower())

    def test_launcher_fails_closed_on_git_ignore_preflight(self) -> None:
        self.assertIn("check-ignore -q", self.launcher)
        self.assertIn("Privacy preflight failed", self.launcher)
        self.assertIn("h0-launcher-config.json", self.launcher)

    def test_launcher_repeats_frozen_h0_restrictions(self) -> None:
        self.assertIn("Natural episodes only", self.launcher)
        self.assertIn("first 10 eligible strict-valid episodes", self.launcher)
        self.assertIn("Do NOT inspect predictor coefficients", self.launcher)
        self.assertIn("prevalence, missingness, episode rate, temporal dependence", self.launcher)

    def test_launcher_id_charset_matches_capture_store(self) -> None:
        # Both layers should accept the same pseudonymous ID alphabet/length rather
        # than creating a wrapper-specific identifier policy.
        self.assertIn("^[A-Za-z0-9._+\\-]{1,128}$", self.launcher)
        self.assertIn('r"^[A-Za-z0-9._+-]{1,128}$"', self.core_station)


if __name__ == "__main__":
    unittest.main()
