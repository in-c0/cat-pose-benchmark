from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from stage0.capture_host_probe import sequential_write_probe


class CaptureHostProbeTests(unittest.TestCase):
    def test_probe_writes_and_removes_temporary_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = sequential_write_probe(root, size_mb=1, chunk_mb=1)
            self.assertEqual(result["size_bytes"], 1024 * 1024)
            self.assertGreater(result["write_mb_per_s"], 0.0)
            self.assertTrue(result["probe_file_deleted"])
            self.assertEqual(list(root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
