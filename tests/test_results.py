import csv
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ResultTests(unittest.TestCase):
    def records(self):
        return [json.loads(path.read_text()) for path in sorted((ROOT / "results").glob("P01_FAL*5S_001.json"))]

    def test_three_distinct_attempts_with_identical_requests(self):
        records = self.records()
        self.assertEqual(len(records), 3)
        self.assertEqual(len({r["endpoint"] for r in records}), 3)
        self.assertEqual(len({r["request"]["payload_sha256"] for r in records}), 1)
        for record in records:
            self.assertEqual(record["submission_count"], 1)
            self.assertEqual(record["automatic_retries"], 0)
            self.assertFalse(record["self_host"]["measured"])

    def test_published_videos_match_records(self):
        for record in self.records():
            video = (ROOT / record["output"]["public_artifact"]).read_bytes()
            self.assertEqual(len(video), record["output"]["bytes"])
            self.assertEqual(hashlib.sha256(video).hexdigest(), record["output"]["sha256"])

    def test_costs_are_consistent_but_not_claimed_reconciled(self):
        total = Decimal(0)
        for record in self.records():
            cost = record["cost"]
            computed = Decimal(cost["response_billable_units"]) * Decimal(cost["authenticated_base_unit_price_usd"])
            self.assertEqual(computed, Decimal(cost["tariff_derived_generation_usd"]))
            self.assertIsNone(cost["actual_charge_usd"])
            self.assertFalse(cost["ledger_settled"])
            total += computed
        self.assertEqual(total, Decimal("0.60"))

    def test_latency_is_not_a_full_quality_acceptance(self):
        for record in self.records():
            timing = record["timing"]
            self.assertEqual(timing["latency_pass"], timing["end_to_end_seconds"] <= timing["target_seconds"])
            self.assertEqual(record["review"]["blind_human_review"], "pending")
            self.assertIsNone(record["review"]["prompt_match"])

    def test_measurement_csv_matches_json(self):
        with (ROOT / "results" / "MEASUREMENTS.csv").open() as stream:
            rows = {r["run_id"]: r for r in csv.DictReader(stream)}
        self.assertEqual(len(rows), 3)
        for record in self.records():
            row = rows[record["run_id"]]
            self.assertEqual(float(row["measured_end_to_end_seconds"]), record["timing"]["end_to_end_seconds"])
            self.assertEqual(row["tariff_generation_usd"], record["cost"]["tariff_derived_generation_usd"])


class SelfHostResultTests(unittest.TestCase):
    def record(self):
        return json.loads((ROOT / "results/P01_EN_RUNPOD_H100X4_5S_001.json").read_text())

    def test_original_video_integrity(self):
        output = self.record()["output"]
        content = (ROOT / output["public_artifact"]).read_bytes()
        self.assertEqual(len(content), output["bytes"])
        self.assertEqual(hashlib.sha256(content).hexdigest(), output["sha256"])
        self.assertFalse(output["reencoded_for_publication"])

    def test_cost_estimate_matches_processing_interval_not_full_bill(self):
        r = self.record()
        expected = Decimal(str(r["timing"]["runtime_reported_inference_seconds"])) * Decimal("13.96") / 3600
        self.assertLess(abs(expected - Decimal(r["cost"]["request_window_compute_estimate_usd"])), Decimal("0.000000001"))
        self.assertIsNone(r["cost"]["actual_charge_usd"])
        self.assertFalse(r["cost"]["ledger_settled"])

    def test_language_change_is_not_an_exact_paired_prompt(self):
        r = self.record()
        self.assertTrue(r["request"]["prompt_modified"])
        self.assertFalse(r["request"]["exact_prompt_match_to_fal"])
        self.assertNotEqual(r["request"]["prompt_sha256"], r["request"]["source_prompt_sha256"])
        self.assertFalse(r["review"]["english_language_verified"])

    def test_latency_failure_and_verified_cleanup(self):
        r = self.record()
        self.assertGreater(r["timing"]["end_to_end_seconds"], r["timing"]["target_seconds"])
        self.assertFalse(r["timing"]["latency_pass"])
        self.assertIsNone(r["cost"]["accepted_output_unit_cost"])
        self.assertEqual(r["submission_count"], 1)
        self.assertEqual(r["timing"]["builtin_warmup_count"], 1)
        self.assertTrue(r["cleanup"]["pod_deleted"])

    def test_separate_csv_preserves_comparison_scope(self):
        r = self.record()
        with (ROOT / "results/SELF_HOST_MEASUREMENTS.csv").open() as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["run_id"], r["run_id"])
        self.assertEqual(float(rows[0]["measured_end_to_end_seconds"]), r["timing"]["end_to_end_seconds"])
        self.assertEqual(rows[0]["exact_prompt_match_to_fal"], "false")
        self.assertEqual(rows[0]["actual_reconciled_charge_usd"], "")


if __name__ == "__main__":
    unittest.main()
