from decimal import Decimal
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from economics import scenario


class EconomicsTests(unittest.TestCase):
    def test_unknown_runtime_does_not_invent_cost(self):
        result = scenario("7.89", "1", "1", ".30")
        self.assertIsNone(result["cost_per_accepted_usd"])
        self.assertAlmostEqual(float(result["break_even_service_seconds"]), 136.882129, places=6)

    def test_lower_utilization_and_failures_increase_cost(self):
        baseline = scenario("7.89", "1", "1", ".30", "60")
        half = scenario("7.89", ".5", "1", ".30", "60")
        failures = scenario("7.89", "1", ".5", ".30", "60")
        self.assertEqual(half["cost_per_accepted_usd"], 2 * baseline["cost_per_accepted_usd"])
        self.assertEqual(failures["cost_per_accepted_usd"], half["cost_per_accepted_usd"])

    def test_zero_accepted_outputs_has_no_unit_cost(self):
        result = scenario("7.89", "1", "0", ".30", "60")
        self.assertTrue(all(value is None for value in result.values()))

    def test_overhead_and_break_even(self):
        result = scenario("6", ".5", ".8", ".30", "36", "2", ".02")
        self.assertEqual(result["cost_per_accepted_usd"], Decimal(".225"))
        self.assertEqual(result["reference_price_headroom_usd"], Decimal(".075"))
        at_limit = scenario("6", ".5", ".8", ".30", result["break_even_service_seconds"], "2", ".02")
        self.assertEqual(at_limit["cost_per_accepted_usd"], Decimal(".30"))

    def test_overhead_can_prevent_break_even(self):
        self.assertIsNone(scenario("7.89", "1", ".5", ".30", extra_per_attempt=".20")["break_even_service_seconds"])

    def test_invalid_assumptions(self):
        for value in ("NaN", "Infinity", "-1", "0"):
            with self.subTest(value=value), self.assertRaises((ValueError, ArithmeticError)):
                scenario(value, "1", "1", ".30")
        for utilization in ("0", "1.1"):
            with self.assertRaises(ValueError):
                scenario("7.89", utilization, "1", ".30")
        with self.assertRaises(ValueError):
            scenario("7.89", "1", "1.1", ".30")


if __name__ == "__main__":
    unittest.main()
