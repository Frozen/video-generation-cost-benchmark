import copy
import csv
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from validate import PLAN_FIELDS, pending_gates, validate


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.suite = json.loads((ROOT / "suite.json").read_text(encoding="utf-8"))

    def test_planning_contract_has_no_active_legacy_attempts(self):
        self.assertEqual(validate(self.suite), [])
        self.assertEqual(self.suite["planned_attempts"], 0)
        self.assertEqual(self.suite["supersedes"]["planned_attempts"], 12)
        self.assertTrue(pending_gates(self.suite))
        self.assertFalse(self.suite["request_policy"]["legacy_vbench_scenes_active"])

    def test_budget_and_closeout_limits_remain_fixed(self):
        for key, value in (("budget_usd", "30.00"), ("new_compute_threshold_usd", "25.00")):
            with self.subTest(key=key):
                suite = copy.deepcopy(self.suite)
                suite[key] = value
                with self.assertRaises(ValueError):
                    validate(suite)

    def test_agreed_end_to_end_latency_cannot_be_weakened(self):
        changes = {
            "measurement": "inference_only", "duration_basis": "actual_output_seconds",
            "application": "average_warm_requests", "max_wait_seconds_per_video_second": 4,
            "limits_seconds": {"short": 16, "long": 31},
        }
        for key, value in changes.items():
            with self.subTest(key=key):
                suite = copy.deepcopy(self.suite)
                suite["latency_target"][key] = value
                with self.assertRaises(ValueError):
                    validate(suite)

    def test_matching_cannot_be_claimed_without_a_reviewed_plan(self):
        for key, value in (("reference_provider", "other"), ("matching_status", "verified"),
                           ("scope", "three_model_quality_ranking"), ("endpoint_id", "unreviewed-endpoint")):
            with self.subTest(key=key):
                suite = copy.deepcopy(self.suite)
                suite["comparison"][key] = value
                with self.assertRaises(ValueError):
                    validate(suite)

    def test_realistic_paired_request_requirements_cannot_be_dropped(self):
        for key in ("realistic_customer_use_cases", "identical_logical_request_per_pair",
                    "asset_hashes_required", "source_and_reuse_permissions_required",
                    "freeze_before_generation"):
            with self.subTest(key=key):
                suite = copy.deepcopy(self.suite)
                suite["request_policy"][key] = False
                with self.assertRaises(ValueError):
                    validate(suite)

    def test_no_implicit_schedule_retries_or_execution_switch(self):
        for key, value in (("planned_attempts", 12), ("attempts", [{"run_id": "old"}]),
                           ("execution_plan_frozen", True), ("automatic_retries", 1)):
            with self.subTest(key=key):
                suite = copy.deepcopy(self.suite)
                suite[key] = value
                with self.assertRaises(ValueError):
                    validate(suite)

    def test_vbench_and_duration_boundary_remain_deferred(self):
        for key, value in (("vbench_status", "active"), ("vbench_budget_usd", "4.00"),
                           ("minimum_duration_for_evaluator", 5)):
            with self.subTest(key=key):
                suite = copy.deepcopy(self.suite)
                suite["evaluation"][key] = value
                with self.assertRaises(ValueError):
                    validate(suite)

    def test_unreviewed_and_partial_outputs_are_not_accepted(self):
        for key, value in (("accepted_labels", ["pass", "partial"]), ("unreviewed_value", "pass"),
                           ("method", "automatic"), ("evidence_required", False)):
            with self.subTest(key=key):
                suite = copy.deepcopy(self.suite)
                suite["human_review"]["prompt_match"][key] = value
                with self.assertRaises(ValueError):
                    validate(suite)

    def test_load_tests_do_not_replace_interactive_measurements(self):
        for key, value in (("interactive_concurrency", 8), ("load_tests", "unbounded"),
                           ("latency_and_throughput_reported_separately", False),
                           ("include_pipeline_and_delivery", False)):
            with self.subTest(key=key):
                suite = copy.deepcopy(self.suite)
                suite["measurement_policy"][key] = value
                with self.assertRaises(ValueError):
                    validate(suite)

    def test_modeled_economics_are_not_observed_profit(self):
        for key, value in (("scenario_status", "measured"),
                           ("api_reference_price_is_guaranteed_revenue", True),
                           ("api_benchmark_bill_in_recurring_self_host_cost", True),
                           ("experiment_and_service_costs_separate", False),
                           ("zero_accepted_output_unit_cost", "zero"), ("net_profit_claim", True)):
            with self.subTest(key=key):
                suite = copy.deepcopy(self.suite)
                suite["economics"][key] = value
                with self.assertRaises(ValueError):
                    validate(suite)

    def test_generated_schedule_has_only_header(self):
        result = subprocess.run([sys.executable, str(ROOT / "scripts/validate.py"), "--plan"],
                                capture_output=True, text=True, check=True)
        reader = csv.DictReader(io.StringIO(result.stdout))
        self.assertEqual(reader.fieldnames, PLAN_FIELDS)
        self.assertEqual(list(reader), [])
        self.assertEqual(result.stdout, (ROOT / "pilot-plan.csv").read_text())

    def test_ready_cli_stays_blocked(self):
        result = subprocess.run([sys.executable, str(ROOT / "scripts/validate.py"), "--ready"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2, result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report["protocol_valid"])
        self.assertFalse(report["paid_execution_ready"])
        self.assertEqual(report["planned_attempts"], 0)
        self.assertTrue(report["pending_gates"])


if __name__ == "__main__":
    unittest.main()
