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


if __name__ == "__main__":
    unittest.main()
