import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from budget import cents, empty_ledger, exposure, reserve, settle, transact


class BudgetTests(unittest.TestCase):
    def test_quote_rounds_up(self):
        self.assertEqual(cents("0.001"), 1)
        self.assertEqual(cents("2.09"), 209)

    def test_invalid_amounts(self):
        for value in ("-1", "NaN", "Infinity", "invalid"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                cents(value)

    def test_zero_quote_refused(self):
        with self.assertRaises(ValueError):
            reserve(empty_ledger(), "a", "0", "generation")

    def test_compute_threshold_and_closeout(self):
        state = reserve(empty_ledger(), "a", "22.50", "generation")
        with self.assertRaises(ValueError):
            reserve(state, "b", "0.01", "evaluation")
        state = reserve(state, "close", "2.50", "closeout")
        self.assertEqual(exposure(state), 2500)
        with self.assertRaises(ValueError):
            reserve(state, "extra", "0.01", "closeout")

    def test_outstanding_work_counts(self):
        state = reserve(empty_ledger(), "h3", "12", "generation")
        with self.assertRaises(ValueError):
            reserve(state, "ltx", "12", "generation")

    def test_duplicate_never_retries(self):
        state = reserve(empty_ledger(), "h3", "2", "generation")
        with self.assertRaises(ValueError):
            reserve(state, "h3", "2", "generation")
        state = settle(state, "h3", "1")
        with self.assertRaises(ValueError):
            reserve(state, "h3", "2", "generation")

    def test_actual_charge_releases_only_difference(self):
        state = reserve(empty_ledger(), "h3", "6", "generation")
        state = settle(state, "h3", "2.30")
        self.assertEqual(exposure(state), 230)

    def test_unquoted_actual_charge_preserved_and_blocks(self):
        state = reserve(empty_ledger(), "h3", "6", "generation")
        state = settle(state, "h3", "26")
        self.assertEqual(exposure(state), 2600)
        self.assertTrue(state["blocked"])
        with self.assertRaises(ValueError):
            reserve(state, "next", "1", "generation")

    def test_missing_and_double_settlement(self):
        with self.assertRaises(ValueError):
            settle(empty_ledger(), "missing", "0")
        state = settle(reserve(empty_ledger(), "a", "1", "generation"), "a", "0")
        with self.assertRaises(ValueError):
            settle(state, "a", "0")

    def test_functions_do_not_mutate_input(self):
        state = empty_ledger()
        reserve(state, "a", "1", "generation")
        self.assertEqual(state, empty_ledger())

    def test_cap_cannot_be_changed(self):
        state = empty_ledger()
        state["cap_cents"] = 5000
        with self.assertRaises(ValueError):
            reserve(state, "a", "1", "generation")

    def test_durable_ledger_refuses_reset_and_corruption(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.json"
            transact(path, "init")
            transact(path, "reserve", "a", "2", "generation")
            self.assertEqual(transact(path, "show")["exposure_usd"], "2.00")
            with self.assertRaises(ValueError):
                transact(path, "init")
            state = json.loads(path.read_text())
            state["entries"]["a"]["reserved_cents"] = -1
            path.write_text(json.dumps(state))
            with self.assertRaises(ValueError):
                transact(path, "show")

    def test_missing_ledger_does_not_start_at_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                transact(Path(directory) / "missing.json", "reserve", "a", "1", "generation")


if __name__ == "__main__":
    unittest.main()
