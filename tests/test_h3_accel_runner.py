"""Offline failure-retention checks; never create or delete real Pods."""

import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import h3_accel_runner as runner


class RetentionTests(unittest.TestCase):
    def run_failure(self, keep):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lease = root / "private/runpod-h100x4accel-p01-002"
            lease.mkdir(parents=True)
            state = {"status": "created", "hardware": "h100x4accel",
                     "generation_submissions": 0, "pod_id": "offline-pod",
                     "name": "offline-trial", "deadline": time.time() + 1200}
            (lease / "state.json").write_text(json.dumps(state))
            argv = ["runner", "--env-file", "unused", "--attempt", "2"]
            if keep:
                argv.append("--keep-on-error")
            with patch.object(runner, "ROOT", root), patch.object(runner, "LEASE", lease), \
                    patch.object(sys, "argv", argv), \
                    patch.object(runner, "load_keys", return_value={"runpod": "offline"}), \
                    patch.object(runner, "api", return_value=(200, {
                        "name": "offline-trial", "cost": 99})), \
                    patch.object(runner, "terminate", return_value=True) as terminate:
                with self.assertRaisesRegex(RuntimeError, "hourly rate exceeds"):
                    runner.main()
                result = json.loads((lease / "state.json").read_text())
                if keep:
                    terminate.assert_not_called()
                    self.assertTrue(result["retained_for_debugging"])
                    self.assertEqual(result["status"], "created")
                    self.assertEqual(result["deadline"], state["deadline"])
                else:
                    terminate.assert_called_once_with("offline-pod", "offline-trial", "offline")
                    self.assertEqual(result["status"], "terminated")
                    self.assertFalse(result["both_adapters_downloaded"])

    def test_keep_on_error_preserves_exception_and_original_deadline(self):
        self.run_failure(True)

    def test_default_cleanup_preserves_exception(self):
        self.run_failure(False)
