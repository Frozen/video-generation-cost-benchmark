"""Export verified attempt-002 artifacts and allowlisted metrics, offline only.

Regenerate with: python3 scripts/export_acceleration.py
Requires completed private journals, exported service logs, ffmpeg and ffprobe.
No cloud calls, generation requests, invoice assumptions or raw prompt export.
"""

import csv
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

from h3_adapters import ADAPTERS
from h3_metrics import cost_estimate, gpu_summary, stage_metrics
from h3_trial import require_successful_warmup

ROOT = Path(__file__).resolve().parents[1]
LEASE = ROOT / "private/runpod-h100x4accel-p01-002"
RATE = "13.96"


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, record):
    path.write_text(json.dumps(record, indent=2) + "\n")


def video_metadata(path):
    probe = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)], text=True))
    subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(path), "-f", "null", "-"],
                   check=True, capture_output=True, timeout=60)
    video = next(s for s in probe["streams"] if s["codec_type"] == "video")
    audio = next(s for s in probe["streams"] if s["codec_type"] == "audio")
    if (video["width"], video["height"], int(video["nb_frames"])) != (1344, 768, 124):
        raise ValueError("Unexpected output dimensions or frame count")
    return {"bytes": path.stat().st_size, "sha256": digest(path),
            "width": video["width"], "height": video["height"], "frames": int(video["nb_frames"]),
            "fps_fraction": video["r_frame_rate"], "video_duration_seconds": float(video["duration"]),
            "container_duration_seconds": float(probe["format"]["duration"]),
            "video_codec": video["codec_name"], "audio_codec": audio["codec_name"],
            "audio_sample_rate": int(audio["sample_rate"]), "audio_channels": audio["channels"],
            "full_decode_pass": True, "reencoded_for_publication": False}


def main():
    lease = read(LEASE / "state.json")
    closeout = read(LEASE / "independent-closeout.json")
    if closeout["pod_get_status"] != 404:
        raise ValueError("Independent deletion check required")
    if not (lease.get("status") == "terminated" and lease.get("both_adapters_downloaded")
            and lease.get("generation_submissions") == 2):
        raise ValueError("Two downloaded requests and verified termination are required")
    allocation = read(LEASE / "allocation-observation.json")
    if Decimal(str(allocation["cost"])) != Decimal(RATE):
        raise ValueError("Hourly rate mismatch")
    allocated = datetime.strptime(allocation["startedAt"], "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc).timestamp()
    window = lease["terminated_at"] - allocated
    compute = cost_estimate(window, RATE, 10)
    disk = Decimal(str(window)) * Decimal(300) * Decimal("0.10") / (30 * 24 * 3600)
    whole = Decimal(compute["total_usd"]) + disk
    baseline = read(ROOT / "results/P01_EN_RUNPOD_H100X4_5S_001.json")
    telemetry = (LEASE / "gpu-samples.csv").read_text()
    records = []
    for recipe, adapter in ADAPTERS.items():
        output_dir = ROOT / f"private/h100-{recipe}-p01-en-002"
        state, job = read(output_dir / "state.json"), read(output_dir / "last-job.json")
        runtime = read(LEASE / f"runtime-{recipe}.json")
        log_path = LEASE / f"service-{recipe}.log"
        log = log_path.read_text(errors="replace")
        if state["status"] != "downloaded" or job["status"] != "completed":
            raise ValueError("Incomplete request")
        require_successful_warmup(log)
        steps = adapter["evaluations"]
        if not re.search(r"100%[^\n]*\b" + str(steps) + "/" + str(steps) + r"\b", log):
            raise ValueError("Missing completed denoising iteration evidence")
        if runtime["adapter"] != adapter or not runtime["adapter_checksum_verified"]:
            raise ValueError("Adapter pin mismatch")
        source = output_dir / (state["run_id"] + ".mp4")
        metadata = video_metadata(source)
        target = ROOT / "results" / source.name
        if target.exists() and digest(target) != digest(source):
            raise ValueError("Refusing to overwrite a different published video")
        shutil.copyfile(source, target)
        metadata["public_artifact"] = "results/" + source.name
        configuration = dict(baseline["configuration"], adapters=[adapter],
                             runtime_patch=dict(runtime["runtime_patch"], gpu_validation="warmup_and_request_completed"),
                             runtime_versions=runtime["versions"])
        request = dict(baseline["request"], num_inference_steps=adapter["sigma_points"],
                       denoising_iterations_observed=steps)
        payload = read(output_dir / "payload.json")
        request["canonical_payload_sha256"] = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if state["prompt_sha256"] != request["prompt_sha256"]:
            raise ValueError("Prompt mismatch")
        estimate = cost_estimate(job["inference_time_s"], RATE, 5)
        timing = {k: state[k] for k in ("end_to_end_seconds", "completion_observed_seconds", "submission_response_seconds")}
        timing.update(boundary="request_submission_to_download_complete", target_seconds=15,
                      latency_pass=state["end_to_end_seconds"] <= 15,
                      runtime_reported_inference_seconds=job["inference_time_s"],
                      cold_warm_status="first_user_request_after_builtin_warmup", builtin_warmup_count=1,
                      **stage_metrics(log))
        record = {"run_id": state["run_id"], "lease_run_id": lease["run_id"],
                  "backend": "Runpod self-host", "recipe": recipe, "result": "completed",
                  "submission_count": 1, "automatic_generation_retries": 0,
                  "request": request, "configuration": configuration, "timing": timing, "output": metadata,
                  "cost": {"primary_unit": "USD_per_requested_video_second", "normalization_video_seconds": 5,
                           "aggregate_compute_hourly_usd": RATE,
                           "runtime_compute_estimate_usd": estimate["total_usd"],
                           "runtime_compute_usd_per_video_second": estimate["usd_per_requested_video_second"],
                           "scope": "runtime inference only; excludes setup, idle time, disk and failed earlier attempts",
                           "whole_lease_record": "results/P01_RUNPOD_H100X4ACCEL_5S_002.json",
                           "actual_charge_usd": None, "ledger_settled": False, "accepted_output_unit_cost": None},
                  "gpu_telemetry": {"interval": "submission_to_download; host/client UTC alignment assumed",
                                    "sampled_not_continuous_peaks": True,
                                    "per_gpu": gpu_summary(telemetry, state["submitted_at"], state["downloaded_at"])},
                  "review": {"blind_human_review": "pending", "prompt_match": None,
                             "english_language_verified": False, "audio_quality": "unreviewed", "vbench_run": False},
                  "evidence_sha256": {"service_log": digest(log_path), "runtime_record": digest(LEASE / f"runtime-{recipe}.json")}}
        write(ROOT / "results" / (state["run_id"] + ".json"), record)
        records.append(record)
    lease_record = {"run_id": lease["run_id"], "result": "two_videos_downloaded", "submission_count": 2,
                    "configuration": {"region": "AP-IN-1", "gpu_count": 4, "gpu": "H100 SXM", "sequential": True},
                    "runs": [r["run_id"] for r in records],
                    "timing": {"allocation_to_verified_absence_seconds": window,
                               "allocated_at_utc": allocation["startedAt"],
                               "verified_absent_at_utc": datetime.fromtimestamp(lease["terminated_at"], timezone.utc).isoformat()},
                    "cost": {"aggregate_compute_hourly_usd": RATE, "window_compute_estimate_usd": compute["total_usd"],
                             "window_disk_estimate_usd": str(disk), "window_total_estimate_usd": str(whole),
                             "normalization_requested_video_seconds": 10,
                             "whole_window_usd_per_requested_video_second": str(whole / 10),
                             "scope": "this two-clip rental only; includes startup and idle time, excludes earlier failures and CPU preload",
                             "actual_charge_usd": None, "ledger_settled": False, "reservation_usd": "6.00",
                             "scoped_billing_record_count_at_closeout": closeout["scoped_billing_record_count"]},
                    "cleanup": {"pod_deleted": True, "original_videos_and_logs_exported": True,
                                "persistent_volume_created": False, "subsequent_get_status": closeout["pod_get_status"],
                                "subsequent_account_pod_count": closeout["account_pod_count"],
                                "subsequent_account_network_volume_count": closeout["account_network_volume_count"]},
                    "evidence_sha256": {"gpu_samples_csv": digest(LEASE / "gpu-samples.csv")}}
    write(ROOT / "results/P01_RUNPOD_H100X4ACCEL_5S_002.json", lease_record)
    with (ROOT / "results/ACCELERATION_MEASUREMENTS.csv").open("w") as stream:
        writer = csv.writer(stream)
        writer.writerow(["run_id", "denoising_evaluations", "end_to_end_seconds", "runtime_inference_seconds",
                         "latency_pass", "runtime_compute_usd_per_requested_video_second", "quality_review", "actual_charge_usd"])
        for r in records:
            writer.writerow([r["run_id"], r["request"]["denoising_iterations_observed"], r["timing"]["end_to_end_seconds"],
                             r["timing"]["runtime_reported_inference_seconds"], str(r["timing"]["latency_pass"]).lower(),
                             r["cost"]["runtime_compute_usd_per_video_second"], "pending", ""])
    print(json.dumps({"runs": [{"id": r["run_id"], "timing": r["timing"], "cost": r["cost"]} for r in records],
                      "lease": lease_record}, indent=2))


if __name__ == "__main__":
    main()
