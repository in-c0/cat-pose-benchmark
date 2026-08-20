from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from audio.acoustic_features import extract_features


class AcousticFeatureTests(unittest.TestCase):
    def test_extracts_pitch_and_mfcc_from_sine_wave(self) -> None:
        sample_rate = 22050
        duration = 1.0
        t = np.arange(int(sample_rate * duration)) / sample_rate
        signal = 0.25 * np.sin(2.0 * np.pi * 440.0 * t)
        pcm = np.int16(np.clip(signal, -1.0, 1.0) * 32767)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tone.wav"
            wavfile.write(path, sample_rate, pcm)
            features = extract_features(path)

        self.assertAlmostEqual(features["duration_s"], duration, places=2)
        self.assertGreater(features["voiced_fraction"], 0.5)
        self.assertAlmostEqual(features["f0_median_hz"], 440.0, delta=15.0)
        self.assertIn("mfcc_01_mean", features)
        self.assertIn("mfcc_delta_20_std", features)
        self.assertTrue(np.isfinite(features["spectral_centroid_hz_mean"]))


if __name__ == "__main__":
    unittest.main()
