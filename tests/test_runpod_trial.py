"""Offline journal-isolation tests; no cloud resources or requests."""

from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import runpod_trial


class AttemptTests(unittest.TestCase):
    def tearDown(self):
        runpod_trial.configure_attempt(1)

    def test_original_paths_are_preserved(self):
        runpod_trial.configure_attempt(1)
        self.assertEqual(runpod_trial.PRIVATE.name, "runpod-p01")
        self.assertEqual(runpod_trial.RUN_ID, "P01_RUNPOD_B300_5S_001")

    def test_retry_uses_distinct_journal_and_budget_id(self):
        runpod_trial.configure_attempt(2)
        self.assertEqual(runpod_trial.PRIVATE.name, "runpod-p01-002")
        self.assertEqual(runpod_trial.STATE, runpod_trial.PRIVATE / "state.json")
        self.assertEqual(runpod_trial.RUN_ID, "P01_RUNPOD_B300_5S_002")
        self.assertEqual(runpod_trial.ATTEMPT, 2)

    def test_invalid_attempt_does_not_change_selection(self):
        for value in (0, -1, 1000, True, "2", "../old"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                runpod_trial.configure_attempt(value)
        self.assertEqual(runpod_trial.ATTEMPT, 1)

    def test_h100_has_its_own_identity_and_smaller_rental_bound(self):
        runpod_trial.configure_attempt(1, "h100x4", "AP-IN-1")
        self.assertEqual(runpod_trial.PRIVATE.name, "runpod-h100x4-p01-001")
        self.assertEqual(runpod_trial.RUN_ID, "P01_RUNPOD_H100X4_5S_001")
        profile = runpod_trial.PROFILES[runpod_trial.HARDWARE]
        self.assertEqual(profile["count"] * profile["ram_per_gpu"], 384)
        self.assertEqual(profile["seconds"], 3600)
        self.assertEqual(profile["reservation"], "16.00")
        self.assertEqual(runpod_trial.REGION, "AP-IN-1")

    def test_unreviewed_profile_or_region_rejected(self):
        for hardware, region in (("h100x4", "US-WA-2"), ("b300", "AP-IN-1"), ("unknown", "EUR-IS-1")):
            with self.subTest(hardware=hardware, region=region), self.assertRaises(ValueError):
                runpod_trial.configure_attempt(1, hardware, region)

    def test_acceleration_trial_has_new_journal_and_24_minute_bound(self):
        runpod_trial.configure_attempt(1, "h100x4accel", "AP-IN-1")
        self.assertEqual(runpod_trial.PRIVATE.name, "runpod-h100x4accel-p01-001")
        self.assertEqual(runpod_trial.RUN_ID, "P01_RUNPOD_H100X4ACCEL_5S_001")
        profile = runpod_trial.PROFILES[runpod_trial.HARDWARE]
        self.assertEqual(profile["seconds"], 1440)
        self.assertEqual(profile["reservation"], "6.00")
        self.assertEqual(profile["count"], 4)

    @patch("runpod_trial.api")
    @patch("runpod_trial.transact")
    @patch("runpod_trial.load_keys", return_value={"runpod": "offline-test-key"})
    def test_existing_retry_is_refused_before_reservation_or_request(self, keys, transact, api):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(runpod_trial, "ROOT", Path(directory)):
                runpod_trial.configure_attempt(2)
                runpod_trial.PRIVATE.mkdir(parents=True)
                with self.assertRaises(FileExistsError):
                    runpod_trial.launch(Path("unused.env"))
        transact.assert_not_called()
        api.assert_not_called()


if __name__ == "__main__":
    unittest.main()
