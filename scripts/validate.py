"""Validate the current planning-only protocol; never launch paid work."""

import argparse
import csv
import hashlib
import json
from decimal import Decimal
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PLAN_FIELDS = [
    "run_id", "pair_id", "request_id", "backend", "phase", "configuration_id",
    "duration_id", "target_seconds", "payload_sha256", "upper_bound_usd",
    "status", "output_path",
]
UPSTREAM_HASHES = {
    "source/VBench_full_info.json": "5dd2de80ee43cda750b2b72ea7023657c0b90d3702041c7e4608c65dbe50dccd",
    "source/LICENSE": "43070e2d4e532684de521b885f385d0841030efa2b1a20bafb76133a5e1379c1",
    "source/PROMPTS_README.md": "7f90b414d60e4075e5c21685aaa046686e7a11ca52f36872353744b919b1198a",
}
LATENCY_TARGET = {
    "status": "agreed",
    "stage": "pilot",
    "max_wait_seconds_per_video_second": 3,
    "measurement": "request_submission_to_download_complete",
    "duration_basis": "planned_target_seconds",
    "application": "each_attempt_including_cold_start_after_submission",
    "comparison": "less_than_or_equal",
    "limits_seconds": {"short": 15, "long": 30},
}
REFERENCE_ENDPOINT = "minimax/h3/text-to-video"
REFERENCE_URL = "https://fal.ai/models/" + REFERENCE_ENDPOINT
MODEL_URL = "https://huggingface.co/MiniMaxAI/MiniMax-H3"
REFERENCE_PARAMETERS = {
    "resolution": "768P", "aspect_ratio": "16:9", "seed": 42,
    "prompt_expansion_mode": "disabled", "enable_safety_checker": True,
    "sync_mode": False,
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def planned_rows(suite):
    return list(suite["attempts"])


def validate(suite):
    require(suite["version"] == "0.8.1", "unsupported protocol revision")
    require(suite["status"] == "planning_only_no_generations", "not a planning-only contract")
    require(suite["objective"] == "api_matched_operator_economics", "wrong comparison objective")
    require(suite["current_scope"] == {
        "stage": "baseline_comparison_only", "initial_prompt_count": 1,
        "initial_target_seconds": 5, "backend_order": ["fal.ai", "self_host"],
        "optimization_status": "deferred_requires_new_approval",
        "load_testing_status": "deferred_requires_new_approval",
        "long_clip_status": "deferred_until_first_pair_review",
    }, "current baseline scope changed or deferred work was enabled")
    require(Decimal(suite["budget_usd"]) == Decimal("25.00"), "total cap must remain USD 25")
    require(Decimal(suite["new_compute_threshold_usd"]) == Decimal("22.50"), "closeout guard changed")
    require(suite["allocation_usd"] == {
        "paired_setup_generation": "18.00",
        "bounded_load_optimization": "4.00",
        "storage_closeout_fees": "3.00",
    }, "allocation differs from the published plan")
    require(suite["latency_target"] == LATENCY_TARGET, "agreed end-to-end 1:3 limits changed")
    require([(d["id"], d["target_seconds"]) for d in suite["durations"]] ==
            [("short", 5), ("long", 10)], "duration targets changed")
    require(all(d["native_profiles"] is None for d in suite["durations"]),
            "native profiles need a reviewed execution-plan revision")

    pair = suite["comparison"]
    require(pair["pair_id"] == "P01" and pair["scope"] == "one_api_matched_pair",
            "first stage must not silently become a cross-model sweep")
    require(pair["reference_provider"] == "fal.ai", "reference provider changed")
    require(pair["candidate_families"] == ["H3", "LTX-2.5", "Wan"], "candidate scope changed")
    require(pair["first_candidate_to_investigate"] == "H3", "initial candidate changed")
    require(pair["selection_status"] == "reference_selected" and
            pair["endpoint_id"] == REFERENCE_ENDPOINT, "selected reference endpoint changed")
    require(pair["matching_status"] == "unverified" and pair["self_host_profile"] is None,
            "a candidate is not a verified self-host deployment")
    require(pair["reference_profile"] == {
        "configuration_id": "P01_FAL_H3_768P_NOEXP_V1", "task": "text_to_video",
        "parameters": REFERENCE_PARAMETERS, "duration_seconds": [5, 10],
        "input_assets": "none", "audio_policy": "native_generated_audio_no_target_audio_url",
        "contract_url": REFERENCE_URL + "/api", "checked_on": "2026-09-17",
        "runtime_verified": False,
    }, "selected API profile changed or claimed runtime verification")
    require(pair["matching_evidence"] == [
        {"kind": "provider_contract", "source_url": REFERENCE_URL + "/api",
         "checked_on": "2026-09-17", "status": "documented_not_runtime_verified"},
        {"kind": "self_host_candidate", "source_url": MODEL_URL,
         "checked_on": "2026-09-17", "status": "candidate_not_verified_equivalent"},
    ], "documentary evidence must not become a claim of verified equivalence")
    require(pair["unknown_provider_settings_policy"] == "record_unknown_do_not_claim_exact_replica",
            "unknown implementation details cannot establish equivalence")
    require(pair["self_host_candidate"] == {
        "model": "MiniMax H3 Base FL2VA", "repository": MODEL_URL,
        "task": "t2va", "revision": None, "training_required": False,
        "deployment": {
            "provider": "Runpod", "type": "gpu_pod", "status": "proposed_not_provisioned",
            "gpu_type": "NVIDIA B300 SXM6 AC", "gpu_count": 1, "gpu_memory_gb": 288,
            "runtime": "SGLang Diffusion", "runtime_revision": None, "container_digest": None,
            "purpose": "diagnostic_base_model_measurement_not_sla_validated",
            "precision": "native_bf16_fp32", "quantization": "none", "adapters": [],
            "catalog_reference": {
                "cloud": "SECURE", "product": "POD", "gpu_count": 1,
                "usd_per_hour": "7.89", "availability": "LOW", "checked_on": "2026-09-17",
                "status": "catalog_not_reserved_or_all_in_quote",
            },
        },
    }, "selected diagnostic candidate changed; revise the plan before execution")
    price = pair["price_reference"]
    require(price == {
        "usd_per_generated_second": "0.06", "resolution": "768P",
        "source_url": REFERENCE_URL, "checked_on": "2026-09-17",
        "status": "published_rate_not_measured_charge_or_spending_bound",
        "derived_usd": {"short": "0.30", "long": "0.60", "one_of_each": "0.90"},
    }, "dated API reference price changed or treated as a spending bound")
    rate = Decimal(price["usd_per_generated_second"])
    for label, seconds in (("short", 5), ("long", 10), ("one_of_each", 15)):
        require(Decimal(price["derived_usd"][label]) == rate * seconds,
                "reference-only price calculation differs: " + label)

    policy = suite["request_policy"]
    require(policy["source_suggestions"] == [
        "https://awesomevideoprompts.com/en/models/minimaxh3",
    ], "selected H3 prompt collection changed")
    require(policy["selection_status"] == "pending", "request selection is not yet frozen")
    for field in ("realistic_customer_use_cases", "identical_logical_request_per_pair",
                  "asset_hashes_required", "source_and_reuse_permissions_required",
                  "freeze_before_generation"):
        require(policy[field] is True, "request policy missing: " + field)
    require(policy["legacy_vbench_scenes_active"] is False, "old scenes must not remain active")
    require(suite["execution_plan_frozen"] is False, "paid execution needs a new reviewed plan")
    require(suite["planned_attempts"] == 0 and suite["requests"] == suite["attempts"] == [],
            "unselected requests must not produce a funded schedule")
    require(suite["automatic_retries"] == 0, "automatic retries are not authorized")

    require(suite["measurement_policy"] == {
        "interactive_batch_size": 1,
        "interactive_concurrency": 1,
        "load_tests": "separate_predeclared_bounded_configurations",
        "latency_and_throughput_reported_separately": True,
        "throughput_basis": "accepted_completions_per_wall_clock_interval",
        "include_pipeline_and_delivery": True,
        "provider_reported_measured_modeled_separate": True,
    }, "interactive/load measurement boundaries changed")
    review = suite["human_review"]
    require(review["prompt_match"] == {
        "labels": ["pass", "partial", "fail"], "accepted_labels": ["pass"],
        "unreviewed_value": None, "method": "blind_manual", "evidence_required": True,
    }, "prompt-match acceptance weakened")
    require(review["compare_to_api_reference"] is True, "missing API-relative quality review")
    require(review["accept_requires"] == [
        "output_profile_valid", "prompt_match_pass", "visual_quality_pass", "latency_pass",
    ], "interactive acceptance requirements changed")
    require(suite["evaluation"] == {
        "vbench_status": "deferred", "vbench_budget_usd": "0.00",
        "mode": "blind_human_contract_comparison", "minimum_duration_for_evaluator": None,
        "reuse_outputs": True,
    }, "VBench must remain outside this stage")
    require(suite["economics"] == {
        "experiment_and_service_costs_separate": True,
        "utilization_scenarios": [0.25, 0.5, 0.75, 1.0],
        "scenario_status": "modeled_not_measured",
        "utilization_definition": "fraction_of_billed_wall_time_serving_measured_workload",
        "api_reference_price_is_guaranteed_revenue": False,
        "api_benchmark_bill_in_recurring_self_host_cost": False,
        "zero_accepted_output_unit_cost": "undefined",
        "net_profit_claim": False,
    }, "cost or utilization interpretation changed")
    decisions = suite["pending_decisions"]
    require(isinstance(decisions, list) and len(decisions) == 5 and
            all(isinstance(item, str) and item.strip() for item in decisions),
            "missing unresolved execution decisions")

    previous = suite["supersedes"]
    require(previous["version"] == "0.6.0" and previous["planned_attempts"] == 12 and
            previous["executed_attempts"] == 0, "legacy schedule history changed")
    for name, expected in UPSTREAM_HASHES.items():
        require(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected,
                "retained upstream asset changed: " + name)
    for name in ("README.md", "START_HERE.md", "METHODOLOGY.md", "SOURCE.md",
                 "PREFLIGHT.md", "CLAIMS.md", "AGENTS.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        require(not re.search(r"[ \t]+$", text, flags=re.M), "trailing whitespace: " + name)
        require(not re.search(r"[\u0400-\u04ff]", text), "non-English draft text: " + name)
        for target in re.findall(r"\]\(([^)]+)\)", text):
            if not target.startswith("https://"):
                require((ROOT / target.split("#")[0]).is_file(), "broken local link: " + target)
    return planned_rows(suite)


def pending_gates(suite):
    # This revision is intentionally not an execution schema. A reviewed revision
    # must define actual requests, evidence and a bounded runner before paid work.
    return ["Current protocol is planning-only, not an executable paid-run plan"] + list(suite["pending_decisions"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ready", action="store_true")
    parser.add_argument("--plan", action="store_true", help="Print deterministic CSV; does not execute")
    args = parser.parse_args()
    try:
        suite = json.loads((ROOT / "suite.json").read_text(encoding="utf-8"))
        rows = validate(suite)
        if args.plan:
            import sys
            writer = csv.DictWriter(sys.stdout, fieldnames=PLAN_FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
            return
        with (ROOT / "pilot-plan.csv").open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            require(reader.fieldnames == PLAN_FIELDS, "pilot-plan.csv header differs from the contract")
            require(list(reader) == rows, "pilot-plan.csv must not retain superseded attempts")
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.exit(1, f"Protocol invalid: {exc}\n")
    pending = pending_gates(suite)
    print(json.dumps({
        "protocol_valid": True, "version": suite["version"],
        "comparison_scope": suite["comparison"]["scope"],
        "current_scope": suite["current_scope"],
        "endpoint_selected": suite["comparison"]["selection_status"] == "reference_selected",
        "endpoint_id": suite["comparison"]["endpoint_id"],
        "matching_status": suite["comparison"]["matching_status"],
        "self_host_candidate": suite["comparison"]["self_host_candidate"]["deployment"],
        "planned_attempts": len(rows),
        "latency_target": suite["latency_target"], "vbench_status": "deferred",
        "paid_execution_ready": False, "pending_gates": pending,
    }, indent=2))
    if args.ready:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
