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

    def test_new_scene_is_verbatim_and_replaces_old_ids(self):
        scene = self.suite["scenes"][1]
        self.assertEqual(scene["id"], "S02")
        self.assertEqual(scene["source_index"], 29)
        self.assertEqual(scene["replaces_scene_id"], "S05")
        self.assertEqual(scene["prompt"], "A tranquil tableau of a bowl on the kitchen counter")
        rows = validate(self.suite)
        self.assertEqual(sum(row["scene_id"] == "S02" for row in rows), 6)
        self.assertFalse(any("S05" in row["run_id"] for row in rows))
        self.suite["scenes"][1]["prompt"] += "."
        with self.assertRaises(AssertionError):
            validate(self.suite)

    def test_missing_scene_rationale_or_requirements_rejected(self):
        for field, value in (("rationale", ""), ("prompt_match_requirements", [])):
            with self.subTest(field=field):
                suite = copy.deepcopy(self.suite)
                suite["scenes"][1][field] = value
                with self.assertRaises(AssertionError):
                    validate(suite)

    def test_partial_or_unreviewed_cannot_be_declared_accepted(self):
        changes = {
            "accepted_labels": ["pass", "partial"],
            "unreviewed_value": "pass",
            "method": "automatic",
            "evidence_required": False,
        }
        for field, value in changes.items():
            with self.subTest(field=field):
                suite = copy.deepcopy(self.suite)
                suite["human_review"]["prompt_match"][field] = value
                with self.assertRaises(AssertionError):
                    validate(suite)

    def test_both_durations_share_long_evaluator(self):
        self.assertTrue(all(item["evaluation_mode"] == "long_custom_input" for item in self.suite["durations"]))
        self.suite["durations"][0]["evaluation_mode"] = "custom_input"
        with self.assertRaises(AssertionError):
            validate(self.suite)

    def test_evaluator_duration_guard_and_metric_meaning_cannot_drift(self):
        changes = {
            "minimum_actual_duration_seconds": 4,
            "actual_duration_check": "trust_request_duration",
            "incompatible_duration_policy": "pad_short_files",
            "dynamic_degree_interpretation": "higher_is_better_quality",
            "partitions": ["model_id"],
        }
        for field, value in changes.items():
            with self.subTest(field=field):
                suite = copy.deepcopy(self.suite)
                suite["evaluation"][field] = value
                with self.assertRaises(AssertionError):
                    validate(suite)

    def test_input_mode_and_candidate_access_remain_distinct(self):
        rows = validate(self.suite)
        self.assertEqual({row["input_mode"] for row in rows}, {"text_to_video"})
        self.assertEqual({row["access_kind"] for row in rows if row["model_id"] == "WAN"}, {"vendor_api_candidate"})
        for field, value in (("input_mode", "first_last_frame"), ("access_kind", "self_host_candidate")):
            with self.subTest(field=field):
                suite = copy.deepcopy(self.suite)
                suite["models"][2][field] = value
                with self.assertRaises(AssertionError):
                    validate(suite)


if __name__ == "__main__":
    unittest.main()
