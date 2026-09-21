"""Offline regressions for paid-lifecycle failures; never contact a provider."""

from copy import deepcopy
from contextlib import redirect_stderr, redirect_stdout
from decimal import Decimal
import io
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import vast_trial as trial
from vast_api import API, APIError, SafetyError, save
from vast_deadline import accounting_exposure, local_guard, network_counters, remote_main, stop_reason


def offer():
    return {"id": 100, "machine_id": 200, "gpu_name": "H100 SXM", "num_gpus": 1,
            "gpu_ram": 81920, "cpu_ram": 112834, "disk_space": 400, "cpu_arch": "amd64",
            "driver_version": "595.71.05", "cuda_max_good": 13.2, "reliability": 0.9918,
            "verification": "verified", "rentable": True, "rented": False, "direct_port_count": 8,
            "dph_base": 3.4, "dph_total": 3.5, "storage_total_cost": 0.1,
            "storage_cost": 0.36, "inet_down_cost": 0.04, "inet_up_cost": 0.04}


def state(run_id=trial.RUN_ID):
    return {"provider": "vast.ai", "run_id": run_id, "label": run_id + "-0123456789abcdef",
            "status": "armed", "instance_id": None, "image": trial.IMAGE,
            "source_revision": trial.SOURCE, "model_revision": trial.REVISION,
            "prompt_sha256": trial.PROMPT_SHA256, "quote": trial.check_quote(offer()),
            "cases": {}, "create_submissions": 0, "generation_submissions": 0,
            "create_requested_at": None, "deadline": None, "absence_verified": False,
            "reservation_usd": "8.00", "prior_exposure_usd": "0",
            "provider_actual_charge_usd": None,
            "transfer_admission": {"image_compressed_bytes": 10_000_000_000}}


def resource(journal, instance_id=123):
    return {"id": instance_id, "label": journal["label"], "machine_id": journal["quote"]["machine_id"],
            "image_uuid": journal["image"]}


class Provider:
    def __init__(self, journal=None):
        self.journal = journal
        self.rows = []
        self.calls = []
        self.balance = "0"
        self.credit = "8.00"
        self.total_spend = "0"
        self.can_pay = True
        self.ambiguous_create = False
        self.invisible_create = False
        self.delete_fails = False

    def instances(self):
        return deepcopy(self.rows)

    def request(self, method, path, payload=None):
        self.calls.append((method, path))
        if path == "/api/v0/users/current/":
            return {"balance": self.balance, "credit": self.credit, "can_pay": self.can_pay, "total_spend": self.total_spend,
                    "api_key": "must-not-escape", "email": "private@example.invalid"}
        if method == "POST" and path == "/api/v0/bundles/":
            return {"offers": [] if "id" in payload else [offer(), offer() | {"id": 101}]}
        if method == "PUT" and path.startswith("/api/v0/asks/"):
            if not self.invisible_create:
                self.rows.append(resource(self.journal))
            if self.ambiguous_create:
                raise APIError()
            return {"success": True, "new_contract": 123}
        if method == "DELETE":
            if self.delete_fails:
                raise APIError(503)
            identifier = int(path.rstrip("/").rsplit("/", 1)[1])
            self.rows = [row for row in self.rows if row["id"] != identifier]
            return {"success": True}
        raise AssertionError("Unexpected offline provider operation")

    def pages(self, *args, **kwargs):
        return []


def closed_original(lease):
    baseline = {"credit": "10", "total_spend": "0", "can_pay": True, "observed_at": 90}
    current = {"credit": "9.80663782", "total_spend": "-0.19336218", "can_pay": True, "observed_at": 210}
    journal = state() | {
        "status": "failed", "instance_id": 51778886, "create_submissions": 1,
        "create_requested_at": 100, "verified_absent_at": 200, "deadline": 2800,
        "absence_verified": True, "ssh_key_removed": True,
        "account_before_create": baseline, "account_after_closeout": current,
        "account_drawdown_observed_usd": "0.19336218", "provider_actual_charge_usd": 0.194}
    journal["quote"] = journal["quote"] | {"dph_total": 3, "inet_down_cost": 0.0053, "inet_up_cost": 0.0065}
    guard = {"run_id": trial.RUN_ID, "label": journal["label"], "instance_id": 51778886,
             "status": "closed", "absence_verified": True, "ssh_key_removed": True,
             "verified_absent_at": 199, "account_baseline": baseline,
             "account": baseline, "observed_exposure_usd": "0"}
    lease.mkdir()
    save(lease / "state.json", journal)
    save(lease / "guard-state.json", guard)
    return journal, guard


def retry_approval():
    return {"status": "approved", "provider": "vast.ai", "run_id": trial.VAST_RETRY_RUN_ID,
            "verified_only": True, "max_usd": "8.00",
            "budget_scope": "cumulative_vast_stage_including_first_attempt",
            "max_instances": 1, "gpu_name": "H100 SXM", "gpu_count": 1,
            "max_lease_seconds": 2700,
            "case_order": ["BASE_WARMUP", "BASE_WARM_5S", "BASE_WARM_20S",
                           "REUSE_WARMUP", "REUSE_WARM_5S", "REUSE_WARM_20S"],
            "prompt_sha256": trial.PROMPT_SHA256, "allow_temporary_ssh_key": True,
            "allow_owned_resource_deletion": True, "automatic_generation_retries": 0,
            "prior_run_id": trial.RUN_ID, "max_stage_paid_creates": 2,
            "max_additional_paid_creates": 1, "cumulative_allowance_usd": "8.00",
            "requested_durations_seconds": [5, 20], "measured_outputs": 4, "technical_warmups": 2}


class IsolatedTrialTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.original = self.root / "initial"
        self.retry = self.root / "retry"
        self.recovery = self.root / "recovery"
        for name, value in (("LEASE", self.original), ("RETRY_LEASE", self.retry),
                            ("RECOVERY_LEASE", self.recovery), ("INPUT", self.root / "inputs")):
            patcher = patch.object(trial, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)


class AdmissionTests(IsolatedTrialTests):
    def test_zero_credit_refuses_arm_and_key_upload_without_mutation(self):
        api = Provider()
        api.credit, api.can_pay = "0", False
        with tempfile.TemporaryDirectory() as directory:
            lease = Path(directory) / "lease"
            with self.assertRaises(SafetyError):
                trial.arm(api, lease, Path(directory), Path(directory) / "missing.tar.gz")
            with self.assertRaises(SafetyError):
                trial.upload_key(api, lease, state())
            self.assertFalse(lease.exists())
        self.assertTrue(all(method == "GET" for method, _ in api.calls))

    def test_prepaid_credit_not_host_balance_controls_funding(self):
        api = Provider()
        api.credit = "10"
        self.assertEqual(trial.preflight(api)["blockers"], [])
        api.credit, api.balance = "7.99", "1000"
        with self.assertRaises(SafetyError):
            trial.require_credit(trial.account(api))

    def test_selected_offer_uses_returned_identity_not_unsupported_search_filter(self):
        api = Provider()
        self.assertEqual([item["id"] for item in trial.offers(api, 100)], [100])
        self.assertEqual(trial.offers(api, 999), [])

    def test_quote_rejects_disk_hidden_above_hourly_limit(self):
        quote = offer()
        quote.update(dph_base=3.95, dph_total=3.95, storage_total_cost=0.2)
        with self.assertRaises(SafetyError):
            trial.check_quote(quote)

    def test_advertised_low_rate_does_not_bypass_transfer_or_verification(self):
        for changes in ({"inet_down_cost": 0.04001}, {"verification": "unverified"},
                        {"reliability": 0.98}, {"gpu_ram": 40000}, {"cuda_max_good": 13.1}):
            with self.subTest(changes=changes), self.assertRaises(SafetyError):
                trial.check_quote(offer() | changes)

    def test_cuda_minor_compatibility_still_requires_driver_and_total_budget(self):
        candidate = offer() | {"driver_version": "580.126.20", "cuda_max_good": 13.0,
                               "dph_base": 4.3, "dph_total": 4.4, "inet_down_cost": 0.0000013,
                               "inet_up_cost": 0.0000013}
        quote = trial.check_quote(candidate, trial.VAST_PROXY_RUN_ID)
        trial.admit_stage(quote, "4.05", allowance="9.99")
        with self.assertRaises(SafetyError):
            trial.check_quote(candidate)
        with self.assertRaises(SafetyError):
            trial.check_quote(candidate | {"driver_version": "579.99"}, trial.VAST_PROXY_RUN_ID)
        with self.assertRaises(SafetyError):
            trial.admit_stage(quote | {"inet_down_cost": 0.04}, "4.05", allowance="9.99")

    def test_account_secrets_are_not_returned_by_read_only_check(self):
        output = json.dumps(trial.account(Provider()))
        self.assertNotIn("must-not-escape", output)
        self.assertNotIn("private@example.invalid", output)


class PaidLifecycleTests(IsolatedTrialTests):
    def test_ambiguous_create_adopts_only_owned_instance_and_never_resubmits(self):
        journal = state()
        api = Provider(journal)
        api.ambiguous_create = True
        with tempfile.TemporaryDirectory() as directory:
            lease = Path(directory)
            trial.create_once(api, lease, journal)
            persisted = trial.read_state(lease)
            self.assertEqual(persisted["instance_id"], 123)
            with self.assertRaises(SafetyError):
                trial.create_once(api, lease, persisted)
            self.assertEqual(len([call for call in api.calls if call[0] == "PUT"]), 1)
            self.assertTrue(trial.destroy_owned(api, persisted))
            self.assertEqual(api.rows, [])

    def test_empty_listing_after_ambiguous_create_does_not_release_hold(self):
        journal = state()
        api = Provider(journal)
        api.ambiguous_create = api.invisible_create = True
        with tempfile.TemporaryDirectory() as directory:
            lease = Path(directory)
            with self.assertRaises(SafetyError):
                trial.create_once(api, lease, journal)
            self.assertFalse(trial.destroy_owned(api, trial.read_state(lease)))
            self.assertEqual(trial.read_state(lease)["status"], "create_ambiguous")
            self.assertEqual(len([call for call in api.calls if call[0] == "PUT"]), 1)

    def test_delete_never_targets_unrelated_label_or_machine(self):
        journal = state()
        journal.update(instance_id=123, create_requested_at=1, deadline=2701)
        api = Provider(journal)
        for changes in ({"label": "unrelated"}, {"machine_id": 999}):
            api.rows = [resource(journal) | changes]
            with self.subTest(changes=changes), self.assertRaises(SafetyError):
                trial.destroy_owned(api, journal)
        self.assertFalse(any(method == "DELETE" for method, _ in api.calls))

    def test_wrong_image_blocks_work_but_does_not_prevent_owned_cleanup(self):
        journal = state()
        journal.update(instance_id=123, create_requested_at=1, deadline=2701)
        api = Provider(journal)
        api.rows = [resource(journal) | {"image_uuid": "other:latest"}]
        self.assertFalse(trial.image_matches(api.rows[0]["image_uuid"]))
        self.assertTrue(trial.destroy_owned(api, journal))
        self.assertEqual(api.rows, [])

    def test_cleanup_failure_never_becomes_terminated_or_zero_charge(self):
        journal = state()
        journal.update(instance_id=123, create_requested_at=1, deadline=2701)
        journal["cases"] = {case: {"status": "exported", "decode_verified": True} for case, _, _ in trial.cases_for(trial.RUN_ID)}
        api = Provider(journal)
        api.rows, api.delete_fails = [resource(journal)], True
        with tempfile.TemporaryDirectory() as directory, patch.object(trial.time, "sleep"):
            lease = Path(directory)
            save(lease / "state.json", journal)
            with self.assertRaises(SafetyError):
                trial.close(api, lease)
            final = trial.read_state(lease)
            self.assertEqual(final["status"], "closeout_pending")
            self.assertFalse(final["absence_verified"])
            self.assertIsNone(final["provider_actual_charge_usd"])
            self.assertEqual(len(api.rows), 1)

    def test_late_discovery_can_be_closed_without_another_create(self):
        journal = state()
        journal.update(status="create_ambiguous", create_requested_at=1, deadline=2701, create_submissions=1)
        api = Provider(journal)
        api.rows = [resource(journal)]
        with tempfile.TemporaryDirectory() as directory:
            lease = Path(directory)
            save(lease / "state.json", journal)
            result = trial.recover(api, lease)
            self.assertEqual(result["instance_id"], 123)
            self.assertTrue(result["absence_verified"])
            self.assertFalse(any(method == "PUT" for method, _ in api.calls))


class RetryTests(IsolatedTrialTests):
    def setUp(self):
        super().setUp()
        self.prior, self.prior_guard = closed_original(self.original)
        self.api = Provider()
        self.api.credit, self.api.total_spend = "9.80663782", "-0.19336218"

    def arm(self):
        source = {"source_archive_sha256": "a" * 64, "source_archive_bytes": 1000}
        with patch.object(trial, "inputs", return_value=(retry_approval(), {}, source)), \
                patch.object(trial, "transfer_admission", return_value={"image_compressed_bytes": 10_000_000_000}), \
                patch.object(trial.subprocess, "run"):
            trial.arm(self.api, input_dir=self.root, archive=self.root / "source.tar.gz",
                      run_id=trial.VAST_RETRY_RUN_ID)
        return trial.read_state(self.retry)

    def test_funded_retry_below_initial_credit_threshold_keeps_cumulative_spend(self):
        self.api.credit, self.api.total_spend = "7.80", "-2.20"
        cheap_quote = trial.check_quote(offer() | {"inet_down_cost": 0, "inet_up_cost": 0})
        with patch.object(trial, "offers", return_value=[cheap_quote]):
            journal = self.arm()
        self.assertEqual(journal["status"], "armed")
        self.assertEqual(trial.retry_exposure(journal, trial.account(self.api)), Decimal("2.20"))
        self.assertFalse(any(method in ("PUT", "DELETE") for method, _ in self.api.calls))

    def test_offer_turnover_before_create_uses_fresh_approved_stock_once(self):
        journal = self.arm()
        self.api.journal = journal
        provider_request = self.api.request

        def current_inventory(method, path, payload=None):
            if path == "/api/v0/bundles/":
                return {"offers": [offer() | {"id": 999}]}
            return provider_request(method, path, payload)

        with patch.object(self.api, "request", side_effect=current_inventory), \
                patch.object(trial, "inputs", return_value=(
                    retry_approval(), {}, {"source_archive_sha256": journal["source_archive_sha256"]})), \
                patch.object(trial, "transfer_admission"), \
                patch.object(trial, "guard_ready"), \
                patch.object(trial, "upload_key"), \
                patch.object(trial, "workload", side_effect=RuntimeError("simulated workload failure")):
            with self.assertRaises(RuntimeError):
                trial.execute(self.api, self.root / "unused.env", self.retry)
        closed = trial.read_state(self.retry)
        self.assertEqual(closed["create_submissions"], 1)
        self.assertEqual([path for method, path in self.api.calls if method == "PUT"],
                         ["/api/v0/asks/999/"])
        self.assertTrue(closed["absence_verified"])
        self.assertEqual(self.api.rows, [])

    def test_prior_hold_covers_lifetime_and_admitted_traffic_not_only_lagged_charge(self):
        budget = trial.prior_attempt()
        self.assertEqual(budget["prior_attempt"]["observed_drawdown_usd"], "0.19336218")
        self.assertEqual(budget["prior_attempt"]["reported_charge_usd"], 0.194)
        self.assertEqual(budget["prior_exposure_usd"], "0.65")
        self.prior["provider_actual_charge_usd"] = None
        save(self.original / "state.json", self.prior)
        pending = trial.prior_attempt()
        self.assertEqual(pending["prior_exposure_usd"], "0.65")
        self.assertIsNone(pending["prior_attempt"]["reported_charge_usd"])

    def test_exact_six_case_approval_rejects_shorter_scope_or_extra_create(self):
        path = self.root / "approval.json"
        approved = retry_approval()
        save(path, approved)
        self.assertEqual(trial.approval(path, trial.VAST_RETRY_RUN_ID)["case_order"], approved["case_order"])
        for change in ({"case_order": approved["case_order"][:-1]}, {"requested_durations_seconds": [5]},
                       {"max_additional_paid_creates": 2}, {"max_stage_paid_creates": 3},
                       {"measured_outputs": 2}, {"budget_scope": "new_allowance"}):
            with self.subTest(change=change):
                save(path, approved | change)
                with self.assertRaises(SafetyError):
                    trial.approval(path, trial.VAST_RETRY_RUN_ID)

    def test_unclosed_or_mismatched_original_blocks_retry_before_mutation(self):
        for target, change in (
                ("state.json", {"status": "closeout_pending"}),
                ("state.json", {"absence_verified": False}),
                ("state.json", {"ssh_key_removed": False}),
                ("state.json", {"create_submissions": 2}),
                ("state.json", {"generation_submissions": 1}),
                ("guard-state.json", {"status": "watching"}),
                ("guard-state.json", {"absence_verified": False}),
                ("guard-state.json", {"ssh_key_removed": False}),
                ("guard-state.json", {"instance_id": 999}),
                ("guard-state.json", {"label": "unrelated"})):
            with self.subTest(target=target, change=change):
                save(self.original / "state.json", self.prior)
                save(self.original / "guard-state.json", self.prior_guard)
                original = self.prior if target == "state.json" else self.prior_guard
                save(self.original / target, original | change)
                with self.assertRaises(SafetyError):
                    trial.arm(self.api, run_id=trial.VAST_RETRY_RUN_ID)
                self.assertFalse(self.retry.exists())
        self.assertTrue(all(method == "GET" for method, _ in self.api.calls))

    def test_prior_spend_consumes_allowance_even_with_enough_prepaid_credit(self):
        self.prior["provider_actual_charge_usd"] = 1.19
        save(self.original / "state.json", self.prior)
        with self.assertRaises(SafetyError):
            self.arm()
        self.assertFalse(self.retry.exists())
        self.assertFalse(any(method == "PUT" for method, _ in self.api.calls))

    def test_deposit_between_attempts_cannot_reset_stage_budget(self):
        self.api.credit, self.api.total_spend = "10", "-0.19336218"
        with self.assertRaises(SafetyError):
            self.arm()
        self.assertFalse(self.retry.exists())

    def test_retry_cannot_rearm_or_resubmit_even_after_ambiguous_create(self):
        originals = {name: (self.original / name).read_bytes() for name in ("state.json", "guard-state.json")}
        journal = self.arm()
        self.api.journal = journal
        self.api.ambiguous_create = self.api.invisible_create = True
        with self.assertRaises(SafetyError):
            trial.create_once(self.api, self.retry, journal)
        persisted = trial.read_state(self.retry)
        self.assertEqual(persisted["status"], "create_ambiguous")
        with self.assertRaises(SafetyError):
            trial.create_once(self.api, self.retry, persisted)
        with self.assertRaises(SafetyError):
            trial.arm(self.api, self.root / "other-retry", run_id=trial.VAST_RETRY_RUN_ID)
        self.assertEqual(sum(method == "PUT" for method, _ in self.api.calls), 1)
        self.assertFalse(self.root.joinpath("other-retry").exists())
        for name, content in originals.items():
            self.assertEqual((self.original / name).read_bytes(), content)

    def test_changed_baseline_or_closeout_evidence_cannot_execute(self):
        journal = self.arm()
        journal["stage_account_baseline"] = self.prior["account_after_closeout"]
        save(self.retry / "state.json", journal)
        with self.assertRaises(SafetyError):
            trial.execute(self.api, self.root / "unused.env", self.retry)
        journal["stage_account_baseline"] = self.prior["account_before_create"]
        save(self.retry / "state.json", journal)
        save(self.original / "guard-state.json", self.prior_guard | {"absence_verified": False})
        with self.assertRaises(SafetyError):
            trial.execute(self.api, self.root / "unused.env", self.retry)
        self.assertFalse(any(method == "PUT" for method, _ in self.api.calls))

    def test_unapproved_identity_is_never_a_valid_journal_or_arm(self):
        fourth = trial.VAST_RETRY_RUN_ID.rsplit("_", 1)[0] + "_009"
        with self.assertRaises(SafetyError):
            trial.arm(self.api, self.root / "fourth", run_id=fourth)
        lease = self.root / "fourth"
        lease.mkdir()
        save(lease / "state.json", state(fourth))
        with self.assertRaises(SafetyError):
            trial.read_state(lease)
        self.assertEqual(self.api.calls, [])

    def test_six_exact_exports_and_submissions_required_for_complete_retry(self):
        journal = self.arm()
        self.api.journal = journal
        trial.create_once(self.api, self.retry, journal)
        expected = retry_approval()["case_order"]
        journal["cases"] = {case: {"status": "exported", "decode_verified": True} for case in expected}
        for count, final_status in ((4, "partial"), (6, "terminated")):
            with self.subTest(count=count):
                journal["generation_submissions"] = count
                save(self.retry / "state.json", journal)
                self.assertEqual(trial.close(self.api, self.retry)["status"], final_status)
        journal["cases"]["UNAPPROVED"] = journal["cases"].pop("BASE_WARM_20S")
        save(self.retry / "state.json", journal)
        self.assertEqual(trial.close(self.api, self.retry)["status"], "partial")

    def test_local_guard_uses_original_baseline_not_retry_funding_snapshot(self):
        journal = self.arm() | {"instance_id": 123, "create_requested_at": 100, "deadline": 2800,
                               "account_before_create": self.prior["account_after_closeout"]}
        save(self.retry / "state.json", journal)
        self.api.journal = journal
        self.api.rows = [resource(journal)]
        self.api.credit, self.api.total_spend = "3.60", "-6.40"
        with patch("vast_deadline.time.time", return_value=300):
            self.assertEqual(local_guard(self.api, self.retry), 0)
        result = json.loads((self.retry / "guard-state.json").read_text())
        self.assertIsNotNone(result["stop_reason"])
        self.assertEqual(Decimal(result["observed_exposure_usd"]), Decimal("6.40"))
        self.assertEqual(result["run_id"], trial.VAST_RETRY_RUN_ID)
        self.assertTrue(result["absence_verified"])
        self.assertEqual(self.api.rows, [])

    def test_guard_cannot_replace_original_baseline_during_retry(self):
        journal = self.arm() | {"instance_id": 123, "create_requested_at": 100, "deadline": 2800}
        changed = journal | {"stage_account_baseline": self.prior["account_after_closeout"]}
        self.api.journal = journal
        self.api.rows = [resource(journal)]
        with patch.object(trial, "read_state", side_effect=[journal, changed]), \
                patch("vast_deadline.time.time", return_value=300):
            self.assertEqual(local_guard(self.api, self.retry), 0)
        result = json.loads((self.retry / "guard-state.json").read_text())
        self.assertEqual(result["stop_reason"], "cumulative_account_baseline_changed")
        self.assertEqual(result["account_baseline"], self.prior["account_before_create"])
        self.assertEqual(self.api.rows, [])

    def test_remote_guard_closes_at_cumulative_limit_using_only_own_instance(self):
        journal = self.arm() | {"instance_id": 123, "create_requested_at": 100, "deadline": 2800}
        save(self.root / "prepare-status.json", {"phase": "ready"})
        own = resource(journal)
        environment = {"VAST_BENCHMARK_CONFIG": json.dumps(journal),
                       "CONTAINER_ID": "123", "CONTAINER_API_KEY": "offline-instance-only"}
        with patch.dict("os.environ", environment), patch("vast_deadline.Path", return_value=self.root), \
                patch("vast_deadline.API") as api_factory, \
                patch("vast_deadline.network_counters", return_value=(["eth0"], 85_000_000_000, 0)), \
                patch("vast_deadline.time.time", return_value=2110), patch("vast_deadline.time.sleep"):
            scoped = api_factory.return_value
            scoped.request.side_effect = [{"instances": own}, {"success": True},
                                          {"instances": own}, {"success": True}, APIError(404)]
            self.assertEqual(remote_main(), 0)
        result = json.loads((self.root / "guard-ready.json").read_text())
        self.assertIsNotNone(result["stop_reason"])
        current_only = trial.accounting_estimate(journal | {"prior_exposure_usd": "0"}, 2110, 85_000_000_000, 0)
        self.assertLess(current_only, trial.STOP_USD)
        self.assertGreaterEqual(Decimal(result["estimated_exposure_usd"]), trial.STOP_USD)
        self.assertEqual(Decimal(result["estimated_exposure_usd"]) - current_only, Decimal("0.65"))
        deletions = [call.args[1] for call in scoped.request.call_args_list if call.args[0] == "DELETE"]
        self.assertEqual(deletions, ["/api/v0/instances/123/"])

    def test_estimated_exposure_holds_prior_cost_once_in_addition_to_current_lease(self):
        journal = self.arm() | {"create_requested_at": 100}
        current_only = trial.accounting_estimate(journal | {"prior_exposure_usd": "0"}, 1000,
                                                 1_000_000_000, 100_000_000)
        cumulative = trial.accounting_estimate(journal, 1000, 1_000_000_000, 100_000_000)
        self.assertEqual(cumulative - current_only, Decimal("0.65"))

    def test_worker_phase_from_original_attempt_cannot_complete_retry_case(self):
        journal = self.arm()
        original = {"phase": "completed", "case": "BASE_WARMUP", "run_id": trial.RUN_ID}
        retry = original | {"run_id": trial.VAST_RETRY_RUN_ID}
        with patch.object(trial, "check_watchdogs"), \
                patch.object(trial, "read_remote", side_effect=[{}, original, {}, retry]), \
                patch.object(trial.time, "time", return_value=100), patch.object(trial.time, "sleep"):
            result = trial.wait_phase(self.retry, {}, journal, "completed", "BASE_WARMUP", 200)
        self.assertEqual(result["run_id"], trial.VAST_RETRY_RUN_ID)


class RecoveryTests(IsolatedTrialTests):
    def setUp(self):
        super().setUp()
        self.prior, self.prior_guard = closed_original(self.original)
        original_budget = trial.prior_attempt()
        closed_account = {"credit": "9.540194597", "total_spend": "-0.459805403",
                          "can_pay": True, "observed_at": 410}
        self.second = state(trial.VAST_RETRY_RUN_ID) | original_budget | {
            "status": "failed", "instance_id": 51807213, "create_submissions": 1,
            "create_requested_at": 300, "verified_absent_at": 400, "deadline": 3000,
            "absence_verified": True, "ssh_key_removed": True,
            "account_before_create": self.prior["account_after_closeout"],
            "account_after_closeout": closed_account, "provider_actual_charge_usd": 0.267,
            "hardware": {"gpu_name": "NVIDIA H100"}, "prepare_started_at": 350,
            "failure": {"type": "CalledProcessError", "at": 351}}
        self.quote = trial.check_quote(offer() | {
            "dph_base": 3.295111111111111, "dph_total": 3.395111111111111,
            "inet_down_cost": 0.037760416666666664, "inet_up_cost": 0.037760416666666664})
        self.second["quote"] = self.quote
        self.second_guard = {
            "run_id": trial.VAST_RETRY_RUN_ID, "label": self.second["label"], "instance_id": 51807213,
            "status": "closed", "absence_verified": True, "ssh_key_removed": True,
            "verified_absent_at": 399, "account_baseline": self.prior["account_before_create"],
            "prior_exposure_usd": "0.65",
            "account": {"credit": "9.769749687", "total_spend": "-0.230250313",
                        "can_pay": True, "observed_at": 399},
            "observed_exposure_usd": "0.230250313",
            "estimated_exposure_usd": "1.129706167496001833874090522"}
        self.retry.mkdir()
        save(self.retry / "state.json", self.second)
        save(self.retry / "guard-state.json", self.second_guard)
        save(trial.retry_claim_path(), {"run_id": trial.VAST_RETRY_RUN_ID,
                                       "label": self.second["label"], "lease": str(self.retry.resolve())})
        self.api = Provider()
        self.api.credit, self.api.total_spend = closed_account["credit"], closed_account["total_spend"]
        self.approved = retry_approval() | {
            "run_id": trial.VAST_RECOVERY_RUN_ID, "max_stage_paid_creates": 3,
            "previous_run_id": trial.VAST_RETRY_RUN_ID}

    def arm(self):
        with patch.object(trial, "inputs", return_value=(
                self.approved, {}, {"source_archive_sha256": "a" * 64, "source_archive_bytes": 1000})), \
                patch.object(trial, "transfer_admission", return_value={"image_compressed_bytes": 10_000_000_000}), \
                patch.object(trial, "offers", return_value=[self.quote]), patch.object(trial.subprocess, "run"):
            trial.arm(self.api, input_dir=self.root, archive=self.root / "source.tar.gz",
                      run_id=trial.VAST_RECOVERY_RUN_ID)
        return trial.read_state(self.recovery)

    def test_third_hold_includes_both_leases_without_resetting_baseline(self):
        original = trial.prior_attempt()
        budget = trial.prior_attempt(trial.VAST_RECOVERY_RUN_ID)
        self.assertEqual(budget["stage_account_baseline"], self.prior["account_before_create"])
        self.assertEqual(budget["prior_attempt"], original["prior_attempt"])
        self.assertEqual(budget["prior_account_at_close"], self.second["account_after_closeout"])
        self.assertEqual(budget["prior_exposure_usd"], "1.40")
        self.assertEqual(budget["additional_prior_attempts"], [{
            "run_id": trial.VAST_RETRY_RUN_ID, "instance_id": 51807213, "absence_verified": True,
            "reported_charge_usd": 0.267, "observed_drawdown_usd": "0.266443223",
            "exposure_hold_usd": "0.75"}])
        journal = self.arm() | {"create_requested_at": 500}
        estimate = trial.accounting_estimate(journal, 600, 1000, 100)
        current = trial.accounting_estimate(journal | {"prior_exposure_usd": "0"}, 600, 1000, 100)
        self.assertEqual(estimate - current, Decimal("1.40"))
        with self.assertRaises(SafetyError):
            trial.admit_stage(trial.check_quote(offer()), journal["prior_exposure_usd"])

    def test_unknown_second_invoice_remains_unknown_and_hold_is_not_an_invoice(self):
        save(self.retry / "state.json", self.second | {"provider_actual_charge_usd": None})
        budget = trial.prior_attempt(trial.VAST_RECOVERY_RUN_ID)
        self.assertIsNone(budget["additional_prior_attempts"][0]["reported_charge_usd"])
        self.assertEqual(budget["prior_exposure_usd"], "1.40")

    def test_closed_second_and_proven_pre_model_failure_are_required(self):
        for target, change in (
                ("state.json", {"status": "closeout_pending"}),
                ("state.json", {"instance_id": 999}),
                ("state.json", {"absence_verified": False}),
                ("state.json", {"ssh_key_removed": False}),
                ("state.json", {"generation_submissions": 1}),
                ("state.json", {"prepare_pid": 12}),
                ("state.json", {"prepared_at": 360}),
                ("state.json", {"hardware": {}}),
                ("state.json", {"prepare_started_at": None}),
                ("state.json", {"failure": {"type": "SafetyError"}}),
                ("state.json", {"bootstrap_phase": "link_resolution"}),
                ("guard-state.json", {"status": "watching"}),
                ("guard-state.json", {"absence_verified": False}),
                ("guard-state.json", {"ssh_key_removed": False}),
                ("guard-state.json", {"label": "unrelated"})):
            with self.subTest(target=target, change=change):
                save(self.retry / "state.json", self.second)
                save(self.retry / "guard-state.json", self.second_guard)
                original = self.second if target == "state.json" else self.second_guard
                save(self.retry / target, original | change)
                with self.assertRaises(SafetyError):
                    trial.arm(self.api, run_id=trial.VAST_RECOVERY_RUN_ID)
                self.assertFalse(self.recovery.exists())
        self.assertTrue(all(method == "GET" for method, _ in self.api.calls))

    def test_original_closeout_is_still_required_for_recovery(self):
        save(self.original / "guard-state.json", self.prior_guard | {"absence_verified": False})
        with self.assertRaises(SafetyError):
            trial.arm(self.api, run_id=trial.VAST_RECOVERY_RUN_ID)
        self.assertFalse(self.recovery.exists())

    def test_recovery_requires_one_additional_create_and_all_six_cases(self):
        path = self.root / "recovery-approval.json"
        save(path, self.approved)
        trial.approval(path, trial.VAST_RECOVERY_RUN_ID)
        for change in ({"max_stage_paid_creates": 4}, {"max_additional_paid_creates": 2},
                       {"previous_run_id": trial.RUN_ID}, {"prior_run_id": trial.VAST_RETRY_RUN_ID},
                       {"case_order": self.approved["case_order"][:-1]}):
            with self.subTest(change=change):
                save(path, self.approved | change)
                with self.assertRaises(SafetyError):
                    trial.approval(path, trial.VAST_RECOVERY_RUN_ID)

    def test_recovery_has_distinct_claim_and_exactly_one_create_even_if_ambiguous(self):
        paths = [lease / name for lease in (self.original, self.retry)
                 for name in ("state.json", "guard-state.json")]
        paths.append(trial.retry_claim_path())
        originals = {path: path.read_bytes() for path in paths}
        journal = self.arm()
        self.api.journal = journal
        self.api.ambiguous_create = self.api.invisible_create = True
        with self.assertRaises(SafetyError):
            trial.create_once(self.api, self.recovery, journal)
        with self.assertRaises(SafetyError):
            trial.create_once(self.api, self.recovery, trial.read_state(self.recovery))
        with self.assertRaises(SafetyError):
            trial.arm(self.api, self.root / "another-recovery", run_id=trial.VAST_RECOVERY_RUN_ID)
        self.assertEqual(sum(method == "PUT" for method, _ in self.api.calls), 1)
        self.assertTrue(trial.retry_claim_path(trial.VAST_RECOVERY_RUN_ID).exists())
        for path, content in originals.items():
            self.assertEqual(path.read_bytes(), content)

    def test_additional_cost_evidence_cannot_be_tampered_with_before_execute(self):
        journal = self.arm()
        journal["additional_prior_attempts"][0]["reported_charge_usd"] = 0
        save(self.recovery / "state.json", journal)
        with self.assertRaises(SafetyError):
            trial.execute(self.api, self.root / "unused.env", self.recovery)
        journal["additional_prior_attempts"][0]["exposure_hold_usd"] = "0"
        save(self.recovery / "state.json", journal)
        with self.assertRaises(SafetyError):
            trial.read_state(self.recovery)
        self.assertFalse(any(method == "PUT" for method, _ in self.api.calls))

    def test_recovery_deposit_cannot_reset_the_original_allowance(self):
        self.api.credit = "10"
        with self.assertRaises(SafetyError):
            self.arm()
        self.assertFalse(self.recovery.exists())


class DiagnosticTests(IsolatedTrialTests):
    def test_rate_limited_read_recovers_but_paid_mutation_never_replays(self):
        api = API("offline-key")
        limited = HTTPError("https://console.vast.ai/api/v0/users/current/", 429, "Too Many Requests", {}, None)
        with patch.object(api._opener, "open", side_effect=[limited, io.BytesIO(b'{"credit":10}')]), \
                patch.object(trial.time, "sleep"):
            self.assertEqual(api.request("GET", "/api/v0/users/current/"), {"credit": 10})
        with patch.object(api._opener, "open", side_effect=limited) as execute, \
                patch.object(trial.time, "sleep"):
            with self.assertRaises(APIError) as failure:
                api.request("PUT", "/api/v0/asks/100/", {})
            self.assertEqual(failure.exception.status, 429)
            self.assertEqual(execute.call_count, 1)

    def test_persistent_read_throttling_still_fails_closed(self):
        api = API("offline-key")
        limited = HTTPError("https://console.vast.ai/api/v0/users/current/", 429, "Too Many Requests", {}, None)
        with patch.object(api._opener, "open", side_effect=limited) as execute, \
                patch.object(trial.time, "sleep"):
            with self.assertRaises(APIError) as failure:
                api.request("GET", "/api/v0/users/current/")
            self.assertEqual(failure.exception.status, 429)
            self.assertEqual(execute.call_count, 3)

    def test_transient_transport_read_recovers_without_replaying_mutation(self):
        api = API("offline-key")
        failed = OSError("private transport details")
        with patch.object(api._opener, "open", side_effect=[failed, io.BytesIO(b'{"credit":10}')]), \
                patch.object(trial.time, "sleep"):
            self.assertEqual(api.request("GET", "/api/v0/users/current/"), {"credit": 10})
        with patch.object(api._opener, "open", side_effect=failed) as execute:
            with self.assertRaises(APIError) as failure:
                api.request("PUT", "/api/v0/asks/100/", {})
            self.assertEqual(execute.call_count, 1)
            self.assertEqual(failure.exception.cause_type, "OSError")
            self.assertNotIn("private transport details", str(failure.exception))

    def test_transport_timeouts_exhaust_the_original_eight_second_read_bound(self):
        api, clock = API("offline-key"), [0.0]

        def slow_read(request, timeout):
            clock[0] += timeout
            raise TimeoutError("private endpoint")

        with patch.object(api._opener, "open", side_effect=slow_read) as execute, \
                patch.object(trial.time, "monotonic", side_effect=lambda: clock[0]), \
                patch.object(trial.time, "sleep", side_effect=lambda seconds: clock.__setitem__(0, clock[0] + seconds)):
            with self.assertRaises(APIError) as failure:
                api.request("GET", "/api/v0/users/current/")
        self.assertEqual(failure.exception.cause_type, "TimeoutError")
        self.assertGreater(execute.call_count, 1)
        self.assertLessEqual(execute.call_count, 3)
        self.assertLessEqual(clock[0], 8)

    def test_malformed_control_response_is_not_retried(self):
        api = API("offline-key")
        with patch.object(api._opener, "open", return_value=io.BytesIO(b"not JSON")) as execute:
            with self.assertRaises(APIError) as failure:
                api.request("GET", "/api/v0/users/current/")
        self.assertEqual(execute.call_count, 1)
        self.assertEqual(failure.exception.cause_type, "JSONDecodeError")

    def test_failed_scp_retains_private_actual_error_without_publishing_it(self):
        connection = {"host": "offline.invalid", "port": 22}
        failure = subprocess.CalledProcessError(
            255, ["scp", "private-command"], output=b"partial stdout", stderr=b"actual private transport error")
        public = io.StringIO()
        with patch.object(trial.subprocess, "run", side_effect=failure), \
                redirect_stdout(public), redirect_stderr(public):
            with self.assertRaises(subprocess.CalledProcessError):
                trial.transfer(self.root, connection, [self.root / "source.tar.gz"], True)
        paths = list(self.root.glob("transfer-failure-*.json"))
        self.assertEqual(len(paths), 1)
        diagnostic = json.loads(paths[0].read_text())
        self.assertEqual(diagnostic["stderr"], "actual private transport error")
        self.assertEqual(diagnostic["stdout"], "partial stdout")
        self.assertEqual(diagnostic["returncode"], 255)
        self.assertEqual(diagnostic["direction"], "upload")
        self.assertEqual(diagnostic["local_basenames"], ["source.tar.gz"])
        self.assertEqual(paths[0].stat().st_mode & 0o777, 0o600)
        self.assertNotIn("private-command", paths[0].read_text())
        self.assertEqual(public.getvalue(), "")

    def test_read_only_ssh_observation_recovers_transient_refusal_without_replaying_mutations(self):
        connection = {"host": "proxy.invalid", "port": 22}
        refused = subprocess.CompletedProcess([], 255, stdout="", stderr="Connection refused")
        success = subprocess.CompletedProcess([], 0, stdout='{"heartbeat": 100}', stderr="")
        with patch.object(trial.subprocess, "run", side_effect=[refused, success]), \
                patch.object(trial.time, "sleep"):
            self.assertEqual(trial.read_remote(self.root, connection, "guard-ready.json"), {"heartbeat": 100})
        with patch.object(trial.subprocess, "run", return_value=refused) as execute:
            with self.assertRaises(SafetyError):
                trial.remote(self.root, connection, "raise RuntimeError('mutation')")
            self.assertEqual(execute.call_count, 1)

    def test_read_only_ssh_refusal_is_bounded_and_command_errors_are_not_retried(self):
        connection = {"host": "proxy.invalid", "port": 22}
        for returncode, count in ((255, 3), (1, 1)):
            with self.subTest(returncode=returncode), \
                    patch.object(trial.subprocess, "run", return_value=subprocess.CompletedProcess(
                        [], returncode, stdout="", stderr="failure")) as execute, \
                    patch.object(trial.time, "sleep"):
                with self.assertRaises(SafetyError):
                    trial.read_remote(self.root, connection, "guard-ready.json")
                self.assertEqual(execute.call_count, count)

    def test_remote_failure_diagnostics_are_bounded_private_and_exclude_inputs(self):
        result = subprocess.CompletedProcess([], 1, stdout="x" * 70_000, stderr="actual remote failure")
        public = io.StringIO()
        with patch.object(trial.subprocess, "run", return_value=result), \
                redirect_stdout(public), redirect_stderr(public):
            with self.assertRaises(SafetyError) as caught:
                trial.remote(self.root, {"host": "offline.invalid", "port": 22},
                             "private-command-code", input_text="private-signed-download-credentials")
        path, = self.root.glob("remote-failure-*.json")
        diagnostic = json.loads(path.read_text())
        self.assertEqual(diagnostic["stderr"], result.stderr)
        self.assertLessEqual(len(diagnostic["stdout"].encode()) + len(diagnostic["stderr"].encode()), 64 * 1024)
        self.assertTrue(diagnostic["stdout_truncated"])
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertNotIn("private-command-code", path.read_text())
        self.assertNotIn("private-signed-download-credentials", path.read_text())
        self.assertNotIn(result.stderr, str(caught.exception))
        self.assertEqual(public.getvalue(), "")

    def test_source_upload_failure_persists_phase_and_never_launches_preparation(self):
        journal = state() | {"instance_id": 123, "create_requested_at": 100, "deadline": 2800,
                             "source_archive": str(self.root / "source.tar.gz"), "source_archive_sha256": "a" * 64}
        api = Provider(journal)
        api.rows = [resource(journal) | {
            "actual_status": "running", "ports": {"22/tcp": [{"HostPort": "22"}]},
            "public_ipaddr": "offline.invalid"}]
        boot = {"instance_id": 123, "label": journal["label"], "heartbeat": 200}
        failure = subprocess.CalledProcessError(255, ["scp"], stderr=b"offline source upload failed")
        with patch.object(trial, "guard_ready"), patch.object(trial, "check_watchdogs"), \
                patch.object(trial, "read_remote", return_value=boot), patch.object(trial, "remote"), \
                patch.object(trial, "hardware", return_value={"gpu_name": "NVIDIA H100"}), \
                patch.object(trial, "digest", return_value="a" * 64), \
                patch.object(trial, "transfer", side_effect=[None, failure]), \
                patch.object(trial, "spawn") as spawn, patch.object(trial.time, "time", return_value=200):
            with self.assertRaises(subprocess.CalledProcessError):
                trial.workload(api, self.root / "unused.env", self.root, journal)
        persisted = trial.read_state(self.root)
        self.assertEqual(persisted["bootstrap_phase"], "source_upload")
        self.assertNotIn("prepare_pid", persisted)
        self.assertEqual(persisted["generation_submissions"], 0)
        spawn.assert_not_called()


class GuardTests(IsolatedTrialTests):
    def test_deadline_and_generation_cutoffs_begin_at_create_not_ready(self):
        journal = state()
        journal.update(create_requested_at=100, deadline=2800)
        self.assertIsNone(stop_reason(journal, 1899, Decimal(0)))
        self.assertEqual(stop_reason(journal, 1900, Decimal(0)), "preparation_cutoff")
        journal["prepared_at"] = 1890
        journal["cases"] = {"BASE_WARM": {"status": "submission_claimed", "submitted_at": 2000}}
        self.assertEqual(stop_reason(journal, 2300, Decimal(0)), "generation_timeout")
        journal["cases"]["BASE_WARM"]["status"] = "completed"
        self.assertEqual(stop_reason(journal, 2680, Decimal(0)), "deadline_closeout_reserve")

    def test_traffic_headroom_and_spend_trigger_do_not_wait_for_full_allowance(self):
        journal = state() | {"create_requested_at": 100, "deadline": 2800, "prepared_at": 200}
        self.assertIsNotNone(stop_reason(journal, 300, Decimal("6.40")))
        self.assertEqual(stop_reason(journal, 300, Decimal(0), 88_000_000_000, 0), "inbound_transfer_headroom")
        self.assertEqual(stop_reason(journal, 300, Decimal(0), 0, 4_000_000_000), "outbound_transfer_headroom")

    def test_credit_drawdown_closes_even_when_other_counters_lag(self):
        baseline = {"credit": "10", "balance": "0", "total_spend": "0"}
        current = {"credit": "3.60", "balance": "0", "total_spend": "0"}
        spent = accounting_exposure(baseline, current)
        self.assertEqual(spent, Decimal("6.40"))
        self.assertIsNotNone(stop_reason(state(), 300, spent))

    def test_signed_provider_debits_continue_until_the_spend_limit(self):
        api = Provider()
        api.credit = "10"
        baseline = trial.account(api)
        api.credit, api.total_spend = "9.90371279", "-0.09628721"
        spent = accounting_exposure(baseline, trial.account(api))
        self.assertEqual(spent, Decimal("0.09628721"))
        self.assertIsNone(stop_reason(state(), 300, spent))
        api.credit, api.total_spend = "3.60", "-6.40"
        self.assertIsNotNone(stop_reason(state(), 300, accounting_exposure(baseline, trial.account(api))))

    def test_provider_float_roundoff_is_not_a_deposit_or_counter_reset(self):
        baseline = {"credit": "10", "total_spend": "0"}
        previous = {"credit": "9.043238258", "total_spend": "-0.9567617420000002"}
        current = {"credit": "9.043238258", "total_spend": "-0.956761742"}
        self.assertEqual(accounting_exposure(baseline, current, previous), Decimal("0.956761742"))
        with self.assertRaises(SafetyError):
            accounting_exposure(baseline, current | {"credit": "9.043239258"}, previous)

    def test_deposit_or_counter_reset_invalidates_spend_isolation(self):
        baseline = {"credit": "8", "total_spend": "-20"}
        self.assertEqual(accounting_exposure(baseline, {"credit": "7", "total_spend": "-21.5"}), Decimal("1.5"))
        for snapshot in ({"credit": "9", "total_spend": "-20"}, {"credit": "7", "total_spend": "-19"}):
            with self.subTest(snapshot=snapshot), self.assertRaises(SafetyError):
                accounting_exposure(baseline, snapshot)

    def test_namespace_counters_do_not_misrepresent_loopback_as_billable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, incoming, outgoing in (("lo", 9999, 9999), ("eth0", 120, 30)):
                stats = root / name / "statistics"
                stats.mkdir(parents=True)
                (stats / "rx_bytes").write_text(str(incoming))
                (stats / "tx_bytes").write_text(str(outgoing))
            self.assertEqual(network_counters(root), (["eth0"], 120, 30))

    def test_incomplete_paginated_listing_cannot_prove_absence(self):
        api = API("offline-key")
        with patch.object(api, "request", return_value={"success": True, "instances": [], "total_instances": 1, "next_token": None}):
            with self.assertRaises(SafetyError):
                api.instances()


if __name__ == "__main__":
    unittest.main()
