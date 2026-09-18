"""Published retry evidence must retain measured cost and acceptance boundaries."""

import csv
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RetryResultsTests(unittest.TestCase):
    def records(self):
        return [json.loads((ROOT / f"results/P01_EN_RUNPOD_H100X4_{recipe}_5S_002.json").read_text())
                for recipe in ("LARRY8", "LIGHT4")]

    def test_original_videos_and_same_request_contract(self):
        records = self.records()
        self.assertEqual(len({r["request"]["prompt_sha256"] for r in records}), 1)
        for r, steps in zip(records, (8, 4)):
            content = (ROOT / r["output"]["public_artifact"]).read_bytes()
            self.assertEqual(hashlib.sha256(content).hexdigest(), r["output"]["sha256"])
            self.assertEqual(len(content), r["output"]["bytes"])
            self.assertFalse(r["output"]["reencoded_for_publication"])
            self.assertTrue(r["output"]["full_decode_pass"])
            self.assertEqual(r["request"]["requested_seconds"], 5)
            self.assertEqual(r["request"]["denoising_iterations_observed"], steps)
            self.assertEqual(r["request"]["num_inference_steps"], steps + 1)
            self.assertEqual(r["submission_count"], 1)
            self.assertEqual(r["automatic_generation_retries"], 0)

    def test_inference_cost_is_normalized_by_video_not_runtime(self):
        for r in self.records():
            cost = r["cost"]
            expected = Decimal(str(r["timing"]["runtime_reported_inference_seconds"])) * Decimal("13.96") / 3600
            self.assertEqual(Decimal(cost["runtime_compute_estimate_usd"]), expected)
            self.assertEqual(Decimal(cost["runtime_compute_usd_per_video_second"]), expected / 5)
            self.assertIsNone(cost["actual_charge_usd"])
            self.assertFalse(cost["ledger_settled"])
            self.assertIsNone(cost["accepted_output_unit_cost"])

    def test_latency_gate_is_not_quality_acceptance(self):
        for r, passed in zip(self.records(), (False, True)):
            self.assertEqual(r["timing"]["latency_pass"], passed)
            self.assertEqual(r["timing"]["latency_pass"], r["timing"]["end_to_end_seconds"] <= 15)
            self.assertEqual(r["review"]["blind_human_review"], "pending")
            self.assertFalse(r["review"]["english_language_verified"])
            self.assertIsNone(r["review"]["prompt_match"])
            self.assertEqual(r["configuration"]["runtime_patch"]["gpu_validation"], "warmup_and_request_completed")

    def test_shared_rental_includes_setup_without_double_counting(self):
        lease = json.loads((ROOT / "results/P01_RUNPOD_H100X4ACCEL_5S_002.json").read_text())
        c = lease["cost"]
        self.assertEqual(lease["submission_count"], 2)
        self.assertEqual(c["normalization_requested_video_seconds"], 10)
        expected = Decimal(str(lease["timing"]["allocation_to_verified_absence_seconds"])) * Decimal("13.96") / 3600
        self.assertEqual(Decimal(c["window_compute_estimate_usd"]), expected)
        total = expected + Decimal(c["window_disk_estimate_usd"])
        self.assertEqual(total, Decimal(c["window_total_estimate_usd"]))
        self.assertEqual(total / 10, Decimal(c["whole_window_usd_per_requested_video_second"]))
        self.assertLess(total, Decimal(c["reservation_usd"]))
        self.assertTrue(lease["cleanup"]["pod_deleted"])
        self.assertIsNone(c["actual_charge_usd"])

    def test_csv_matches_records(self):
        with (ROOT / "results/ACCELERATION_MEASUREMENTS.csv").open() as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 2)
        for row, r in zip(rows, self.records()):
            self.assertEqual(row["run_id"], r["run_id"])
            self.assertEqual(float(row["end_to_end_seconds"]), r["timing"]["end_to_end_seconds"])
            self.assertEqual(row["runtime_compute_usd_per_requested_video_second"], r["cost"]["runtime_compute_usd_per_video_second"])
            self.assertEqual(row["actual_charge_usd"], "")
