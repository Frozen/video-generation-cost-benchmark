"""Verify the archived Verda queue and paired Runpod reference without an API."""

import argparse
import hashlib
import json
from decimal import Decimal
from pathlib import Path
import statistics
import subprocess

ROOT = Path(__file__).resolve().parent
REFERENCE = ROOT.parent / "ltx-rtx-2026-09-20"


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def load(path):
    return json.loads(path.read_text())


def journal(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def verify(decode=False):
    if not __debug__:
        raise RuntimeError("Do not disable assertions when verifying evidence")
    for name, expected in load(ROOT / "SHA256SUMS.json").items():
        assert digest(ROOT / name) == expected, name
    evidence = ROOT / "evidence"
    transport = load(evidence / "transport-manifest.json")["files"]
    for name, expected in transport.items():
        if name.startswith("reproduction/"):
            assert digest(REFERENCE / name.removeprefix("reproduction/")) == expected, name
    assert digest(ROOT / "execution/verda_remote.py") == transport["verda_remote.py"]
    manifest = load(REFERENCE / "evidence/resident.json")
    overrides = load(evidence / "manifest-overrides.json")
    manifest["run_id"] = overrides["run_id"]
    for key in ("shutdown_deadline_epoch", "admission_deadline_epoch"):
        manifest["limits"][key] = overrides[key]
    raw_manifest = (json.dumps(manifest, indent=2) + "\n").encode()
    manifest_hash = hashlib.sha256(raw_manifest).hexdigest()
    assert manifest_hash == overrides["original_manifest_sha256"] == transport["workload-manifest.json"]
    preparation = load(evidence / "prepare-status.json")
    assert preparation["manifest_sha256"] == manifest_hash
    assert preparation["transport_sha256"] == digest(evidence / "transport-manifest.json")
    assert preparation["dependency_lock_sha256"] == digest(REFERENCE / "evidence/uv.lock")
    assert preparation["source_revision"] == manifest["profile"]["source_revision"]
    events = journal(evidence / "events.jsonl")
    assert [event["sequence"] for event in events] == list(range(len(events)))
    assert all(event["run_id"] == manifest["run_id"] for event in events)
    assert events[0]["manifest_sha256"] == manifest_hash
    assert events[0]["profile"] == manifest["profile"]
    assert not any(event["event"] in ("worker_failed", "request_failed") for event in events)
    warmups = [event for event in events if event["event"] == "warmup_finished"]
    starts = [event for event in events if event["event"] == "request_started"]
    outputs = [event for event in events if event["event"] == "artifact_ready"]
    assert len(warmups) == 2
    assert len(starts) == len(outputs) == len(manifest["requests"]) == 10
    assert len({request["seed"] for request in manifest["requests"]}) == 10
    receipts = load(evidence / "delivery-receipts.json")
    result = load(evidence / "verified-result.json")
    assert len(receipts) == len(result["outputs"]) == 12
    for request, start, output in zip(manifest["requests"], starts, outputs, strict=True):
        assert request["request_id"] == start["request_id"] == output["request_id"]
        assert request["seed"] == start["seed"]
        assert hashlib.sha256(request["prompt"].encode()).hexdigest() == request["prompt_sha256"]
        assert request["requested_video_seconds"] == 5
        receipt = receipts[output["artifact"]]
        assert output["artifact_sha256"] == receipt["sha256"] == digest(ROOT / "videos" / output["artifact"])
        runtime = output["runtime"]
        assert runtime["resident_total_build_count"] == 1
        assert runtime["transformer_builds_this_request"] == 0
        assert runtime["warmup"] is False
        assert len(runtime["transformer_calls"]) == 11
        assert all(call == {"video": True, "audio": True} for call in runtime["transformer_calls"])
    for output in result["outputs"]:
        path = ROOT / "videos" / output["artifact"]
        assert digest(path) == output["sha256"] == receipts[path.name]["sha256"]
        assert path.stat().st_size == output["bytes"] == receipts[path.name]["bytes"]
        if decode:
            probe = json.loads(subprocess.check_output([
                "ffprobe", "-v", "error", "-show_streams", "-of", "json", str(path)
            ]))
            video = [stream for stream in probe["streams"] if stream["codec_type"] == "video"]
            audio = [stream for stream in probe["streams"] if stream["codec_type"] == "audio"]
            assert len(video) == len(audio) == 1, path.name
            assert (video[0]["codec_name"], video[0]["width"], video[0]["height"]) == ("h264", 1344, 768)
            assert int(video[0]["nb_frames"]) == 121 and video[0]["r_frame_rate"] == "24/1"
            assert audio[0]["codec_name"] == "aac"
            subprocess.run([
                "ffmpeg", "-v", "error", "-xerror", "-i", str(path),
                "-map", "0:v:0", "-map", "0:a:0", "-f", "null", "-"
            ], check=True, stdin=subprocess.DEVNULL)
    window = events[-1]
    assert window["event"] == "window_finished"
    assert window["submitted"] == 10 and window["not_submitted"] == 0
    assert window["stop_reason"] == "request_limit"
    elapsed = Decimal(str(window["worker_window_seconds"]))
    seconds = sum(Decimal(str(request["requested_video_seconds"])) for request in manifest["requests"])
    prices = load(evidence / "prices.json")
    assert prices["pricing_mode"] == "spot" and result["is_spot"]
    assert Decimal(prices["gpu_hourly_usd"]) == Decimal(str(result["compute_usd_hour"]))
    assert Decimal(prices["disk_hourly_usd"]) == Decimal(str(result["disk_usd_hour"]))
    hourly = Decimal(prices["gpu_hourly_usd"]) + Decimal(prices["disk_hourly_usd"])
    cost = hourly * elapsed / Decimal(3600) / seconds
    reference_prices = load(REFERENCE / "evidence/prices.json")
    reference_window = next(event for event in journal(REFERENCE / "evidence/events.jsonl") if event["event"] == "window_finished")
    reference_hourly = (Decimal(reference_prices["gpu_hourly_usd"]) + Decimal(reference_prices["disk_gb"])
                        * Decimal(reference_prices["disk_usd_per_gb_month"]) / Decimal(reference_prices["month_hours"]))
    reference_cost = reference_hourly * Decimal(str(reference_window["worker_window_seconds"])) / Decimal(3600) / seconds
    assert abs(float(cost) - result["warmed_queue_usd_per_requested_video_second"]) < 1e-14
    assert abs(float(reference_cost) - result["runpod_reference_usd_per_requested_video_second"]) < 1e-14
    reconciliation = load(evidence / "reconciliation.json")
    assert len(reconciliation["attempts"]) == 4
    assert reconciliation["cumulative_credit_drawdown_usd"] < reconciliation["stage_cap_usd"]
    assert all(reconciliation[key] == 0 for key in ("owned_instances_remaining", "owned_volumes_remaining", "owned_ssh_keys_remaining"))
    print(json.dumps({
        "verified_measured_outputs": len(outputs),
        "verified_warmup_outputs": len(warmups),
        "full_media_decode_performed": decode,
        "requested_video_seconds": float(seconds),
        "worker_window_seconds": float(elapsed),
        "mean_processing_seconds": statistics.mean(output["processing_seconds"] for output in outputs),
        "spot_gpu_plus_disk_usd_per_requested_video_second": float(cost),
        "reference_gpu_plus_disk_usd_per_requested_video_second": float(reference_cost),
        "warmed_queue_price_reduction_percent": float((1 - cost / reference_cost) * 100),
        "whole_stage_observed_credit_drawdown_usd": reconciliation["cumulative_credit_drawdown_usd"],
        "provider_invoice_final": reconciliation["provider_invoice_final"],
        "quality_parity_evaluated": False,
    }, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decode", action="store_true", help="Probe and fully decode all MP4s with ffprobe/ffmpeg")
    verify(parser.parse_args().decode)
