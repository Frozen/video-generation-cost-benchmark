"""Validate the public protocol offline. --ready additionally checks launch gates."""

import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import sys
from decimal import Decimal

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM_HASHES = {
    "source/LICENSE": "43070e2d4e532684de521b885f385d0841030efa2b1a20bafb76133a5e1379c1",
    "source/PROMPTS_README.md": "7f90b414d60e4075e5c21685aaa046686e7a11ca52f36872353744b919b1198a",
}


def planned_rows(suite):
    scenes = {scene["id"]: scene for scene in suite["scenes"]}
    durations = {duration["id"]: duration for duration in suite["durations"]}
    for model in suite["models"]:
        for scene_id, duration_id in suite["order_per_model"]:
            yield {"run_id": f"pilot_{model['id']}_{scene_id}_{duration_id}_42_1",
                   "model_id": model["id"], "scene_id": scene_id,
                   "duration_id": duration_id, "target_seconds": durations[duration_id]["target_seconds"],
                   "seed": suite["seed"], "sample_index": suite["sample_index"],
                   "prompt": scenes[scene_id]["prompt"], "status": "not_run",
                   "output_path": f"videos/{model['id']}/{duration_id}/{scenes[scene_id]['prompt']}-0.mp4"}


def validate(suite):
    for name, expected_hash in UPSTREAM_HASHES.items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected_hash, name
    raw = (ROOT / suite["source"]["file"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == suite["source"]["sha256"], "source hash mismatch"
    upstream = json.loads(raw)
    assert {model["id"] for model in suite["models"]} == {"H3", "LTX", "WAN"}
    assert len(suite["models"]) == 3 and len(suite["scenes"]) == 2 and len(suite["durations"]) == 2
    for scene in suite["scenes"]:
        assert upstream[scene["source_index"]]["prompt_en"] == scene["prompt"]
        assert hashlib.sha256(scene["prompt"].encode()).hexdigest() == scene["source_prompt_sha256"]
        assert not any(char in scene["prompt"] for char in ("/", "\\", "\n", "\r")), "unsafe filename"
    assert Decimal(suite["budget_usd"]) == Decimal("25.00")
    assert sum(map(Decimal, suite["allocation_usd"].values())) == Decimal("25.00")
    assert Decimal(suite["new_compute_threshold_usd"]) == Decimal("22.50")
    assert suite["latency_target"] == {
        "status": "agreed",
        "stage": "pilot",
        "max_wait_seconds_per_video_second": 3,
        "measurement": "request_submission_to_download_complete",
        "duration_basis": "planned_target_seconds",
        "application": "each_attempt_including_cold_start_after_submission",
        "comparison": "less_than_or_equal",
        "limits_seconds": {"short": 15, "long": 30},
    }, "stage-one latency target differs from agreed 1:3 end-to-end limits"
    for duration in suite["durations"]:
        assert suite["latency_target"]["limits_seconds"][duration["id"]] == 3 * duration["target_seconds"]
    assert suite["automatic_retries"] == 0 and suite["concurrency"] == 1
    assert suite["seed"] == 42 and suite["sample_index"] == 0
    assert len(suite["evaluation"]["dimensions"]) == 6
    rows = list(planned_rows(suite))
    assert len(rows) == suite["planned_attempts"] == 12
    assert len({row["run_id"] for row in rows}) == len({row["output_path"] for row in rows}) == 12
    assert sum(row["target_seconds"] for row in rows) == 90
    for model in suite["models"]:
        assert len([row for row in rows if row["model_id"] == model["id"]]) == 4
    for name in ("README.md", "METHODOLOGY.md", "SOURCE.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert not re.search(r"[ \t]+$", text, flags=re.M), f"trailing whitespace: {name}"
        for target in re.findall(r"\]\(([^)]+)\)", text):
            if not target.startswith("https://"):
                assert (ROOT / target.split("#")[0]).is_file(), f"broken local link: {target}"
    return rows


def pending_gates(suite):
    pending = []
    if suite["latest_policy"].startswith("pending"):
        pending.append("latest-release vs latest-open-weights selection")
    required = ("model_id", "revision_or_vendor_version", "workflow_hash_or_vendor_managed",
                "runtime_pin", "pricing_quote", "exposure_bound_usd", "independent_stop_or_fixed_price",
                "access_verified", "export_verified")
    for model in suite["models"]:
        profile = model["execution_profile"] or {}
        for field in required:
            if not profile.get(field):
                pending.append(f"{model['id']}: {field}")
    for duration in suite["durations"]:
        if not duration["native_shapes"] or not duration["evaluation_mode"]:
            pending.append(f"{duration['id']}: native output/evaluator profile")
    return pending


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ready", action="store_true")
    parser.add_argument("--plan", action="store_true", help="Print deterministic CSV; does not execute")
    args = parser.parse_args()
    suite = json.loads((ROOT / "suite.json").read_text(encoding="utf-8"))
    try:
        rows = validate(suite)
    except (AssertionError, ValueError, KeyError, OSError) as exc:
        parser.exit(1, f"Protocol invalid: {exc}\n")
    if args.plan:
        writer = csv.DictWriter(sys.stdout, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
        return
    with (ROOT / "pilot-plan.csv").open(encoding="utf-8", newline="") as handle:
        saved = list(csv.DictReader(handle))
    expected = [{key: str(value) for key, value in row.items()} for row in rows]
    if saved != expected:
        parser.exit(1, "Protocol invalid: pilot-plan.csv differs from suite.json\n")
    pending = pending_gates(suite)
    print(json.dumps({"protocol_valid": True, "models": 3, "planned_attempts": len(rows),
                      "latency_target": suite["latency_target"],
                      "paid_execution_ready": not pending, "pending_gates": pending}, indent=2))
    if args.ready and pending:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
