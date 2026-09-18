from decimal import Decimal
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class AccelerationResultTests(unittest.TestCase):
    def record(self):
        return json.loads((ROOT / "results/P01_RUNPOD_H100X4ACCEL_5S_001.json").read_text())

    def test_failed_and_unstarted_are_not_video_results(self):
        record = self.record()
        first, second = record["attempts"]
        self.assertEqual((first["submission_count"], second["submission_count"]), (1, 0))
        self.assertEqual(first["result"], "generation_failed")
        self.assertEqual(second["result"], "not_started_after_predecessor_failure")
        for attempt in record["attempts"]:
            self.assertIsNone(attempt["output"])
            self.assertIsNone(attempt["end_to_end_seconds"])
            self.assertIsNone(attempt["runtime_inference_seconds"])
        self.assertIsNone(record["configuration"]["runtime_patch"])

    def test_failed_rental_is_not_a_successful_unit_cost_or_invoice(self):
        record = self.record()
        cost = record["cost"]
        window = Decimal(str(record["timing"]["allocation_to_verified_absence_seconds"]))
        compute = window * Decimal(cost["aggregate_gpu_hourly_usd"]) / 3600
        self.assertEqual(compute, Decimal(cost["window_compute_estimate_usd"]))
        total = compute + Decimal(cost["window_disk_estimate_usd"])
        self.assertEqual(total, Decimal(cost["window_total_estimate_usd"]))
        self.assertEqual(total / 5, Decimal(cost["failed_spend_per_requested_second_usd"]))
        self.assertEqual(cost["successful_generated_seconds"], 0)
        self.assertIsNone(cost["cost_per_successful_video_second_usd"])
        self.assertIsNone(cost["actual_charge_usd"])
        self.assertFalse(cost["ledger_settled"])

    def test_cleanup_and_telemetry_limits_are_explicit(self):
        record = self.record()
        self.assertTrue(record["cleanup"]["pod_deleted"])
        self.assertEqual(record["cleanup"]["subsequent_get_status"], 404)
        self.assertFalse(record["cleanup"]["persistent_volume_created"])
        self.assertEqual(record["gpu_telemetry"]["incomplete_trailing_rows_omitted"], 1)
        self.assertEqual(set(record["gpu_telemetry"]["per_gpu"]), {"0", "1", "2", "3"})
        self.assertEqual(record["timing"]["builtin_warmup_status"], "failed")
        self.assertTrue(record["timing"]["http_health_returned_200_despite_warmup_failure"])
