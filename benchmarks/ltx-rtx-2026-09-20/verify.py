"""Recompute the published estimate from original logs, without a GPU or API."""

import hashlib
import json
from decimal import Decimal
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parent


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def verify():
    checksums = json.loads((ROOT / "SHA256SUMS.json").read_text())
    for name, expected in checksums.items():
        assert digest(ROOT / name) == expected, name
    evidence = ROOT / "evidence"
    raw_manifest = (evidence / "resident.json").read_bytes()
    manifest = json.loads(raw_manifest)
    plan = json.loads((evidence / "original-plan.json").read_text())
    prices = json.loads((evidence / "prices.json").read_text())
    events = [json.loads(line) for line in (evidence / "events.jsonl").read_text().splitlines()]
    receipts = json.loads((evidence / "delivery-receipts.json").read_text())
    assert events[0]["manifest_sha256"] == hashlib.sha256(raw_manifest).hexdigest()
    assert events[0]["profile"] == manifest["profile"]
    assert not any(e["event"] in ("worker_failed", "request_failed") for e in events)
    warmups = [e for e in events if e["event"] == "warmup_finished"]
    assert len(warmups) == 2
    starts = [e for e in events if e["event"] == "request_started"]
    outputs = [e for e in events if e["event"] == "artifact_ready"]
    assert len(starts) == len(outputs) == len(manifest["requests"]) == 10
    assert len({r["seed"] for r in manifest["requests"]}) == 10
    assert receipts["controller_complete"] and len(receipts["receipts"]) == 10
    for request, start, output, receipt in zip(manifest["requests"], starts, outputs, receipts["receipts"], strict=True):
        assert request["request_id"] == start["request_id"] == output["request_id"] == receipt["request_id"]
        assert request["seed"] == start["seed"]
        assert hashlib.sha256(request["prompt"].encode()).hexdigest() == request["prompt_sha256"]
        assert request["requested_video_seconds"] == 5
        assert output["artifact_sha256"] == receipt["artifact_sha256"] == digest(ROOT / "videos" / output["artifact"])
        assert receipt["decode_verified"] and receipt["output_contract_pass"]
        runtime = output["runtime"]
        assert runtime["resident_total_build_count"] == 1
        assert runtime["transformer_builds_this_request"] == 0
        assert runtime["warmup"] is False
        assert len(runtime["transformer_calls"]) == 11
        assert all(call == {"video": True, "audio": True} for call in runtime["transformer_calls"])
    for name, expected in plan["worker_sha256"].items():
        assert digest(ROOT / "original-worker" / name) == expected, name
    assert digest(evidence / "uv.lock") == plan["dependency_lock_sha256"]
    assert digest(evidence / "quality-criteria.json") == manifest["quality_contract"]["criteria_sha256"]
    assert prices["gpu_hourly_usd"] == plan["compute_hourly_usd"]
    window = next(e for e in events if e["event"] == "window_finished")
    assert window["submitted"] == 10 and window["not_submitted"] == 0
    assert window["stop_reason"] == "request_limit"
    elapsed = Decimal(str(window["worker_window_seconds"]))
    output_seconds = sum(Decimal(str(r["requested_video_seconds"])) for r in manifest["requests"])
    hourly = (Decimal(prices["gpu_hourly_usd"]) + Decimal(prices["disk_gb"])
              * Decimal(prices["disk_usd_per_gb_month"]) / Decimal(prices["month_hours"]))
    cost = hourly * elapsed / Decimal(3600) / output_seconds
    result = {
        "verified_outputs": len(outputs),
        "warmups_excluded_from_queue_cost": len(warmups),
        "requested_output_seconds": float(output_seconds),
        "worker_window_seconds": float(elapsed),
        "mean_processing_seconds": statistics.mean(e["processing_seconds"] for e in outputs),
        "gpu_plus_disk_usd_per_video_second": float(cost),
        "h3_max_published_price_divided_by_our_cost": float(Decimal(prices["fal_768p_h3_max_usd_per_video_second"]) / cost),
        "h3_max_turbo_published_price_divided_by_our_cost": float(Decimal(prices["fal_768p_h3_max_turbo_usd_per_video_second"]) / cost),
        "quality_parity_evaluated": False,
        "fal_request_executed_for_this_comparison": False,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    verify()
