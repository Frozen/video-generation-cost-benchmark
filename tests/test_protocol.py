import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from validate import pending_gates, validate


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.suite = json.loads((ROOT / "suite.json").read_text(encoding="utf-8"))

    def test_agreed_target_preserves_twelve_attempts(self):
        rows = validate(self.suite)
        self.assertEqual(len(rows), 12)
        for row in rows:
            limit = self.suite["latency_target"]["limits_seconds"][row["duration_id"]]
            self.assertEqual(limit, 3 * row["target_seconds"])
        self.assertTrue(pending_gates(self.suite), "latency agreement alone must not enable paid execution")

    def test_changed_ratio_or_limits_rejected(self):
        for duration_id, bad_limit in (("short", 5), ("short", 16), ("long", 10), ("long", 31)):
            with self.subTest(duration=duration_id, limit=bad_limit):
                suite = copy.deepcopy(self.suite)
                suite["latency_target"]["limits_seconds"][duration_id] = bad_limit
                with self.assertRaises(AssertionError):
                    validate(suite)
        self.suite["latency_target"]["max_wait_seconds_per_video_second"] = 1
        with self.assertRaises(AssertionError):
            validate(self.suite)

    def test_weaker_measurement_or_acceptance_rejected(self):
        changes = {
            "measurement": "inference_only",
            "duration_basis": "actual_output_seconds",
            "application": "average_warm_requests",
            "comparison": "less_than",
            "status": "pending",
        }
        for field, value in changes.items():
            with self.subTest(field=field):
                suite = copy.deepcopy(self.suite)
                suite["latency_target"][field] = value
                with self.assertRaises(AssertionError):
                    validate(suite)

    def test_missing_target_or_changed_duration_rejected(self):
        suite = copy.deepcopy(self.suite)
        del suite["latency_target"]
        with self.assertRaises(KeyError):
            validate(suite)
        self.suite["durations"][0]["target_seconds"] = 6
        with self.assertRaises(AssertionError):
            validate(self.suite)


if __name__ == "__main__":
    unittest.main()
