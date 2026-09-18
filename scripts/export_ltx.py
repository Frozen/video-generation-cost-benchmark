"""Export the completed LTX smoke test without private prompts or credentials."""

import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from ltx_config import FPS, FRAMES, HEIGHT, HOURLY, IMAGE, MODEL, PROMPT_SHA256, REQUESTED_SECONDS, REVISION, RUN_ID, SOURCE, WIDTH

ROOT = Path(__file__).resolve().parents[1]
LEASE = ROOT / ("private/ltx-h100-p01-" + RUN_ID.rsplit("_", 1)[1])


def read(name):
    return json.loads((LEASE / name).read_text())


def main():
    state, runtime, preparation = read("state.json"), read("generation-status.json"), read("prepare-status.json")
    allocation = read("allocation-observation.json")
    if state["status"] != "terminated" or not state.get("decode_verified"):
        raise ValueError("Export requires a decoded artifact and verified shutdown")
    if runtime["phase"] != "completed" or state["generation_submissions"] != 1:
        raise ValueError("Expected one completed generation")
    if (runtime["run_id"], runtime["model_revision"], runtime["source_revision"]) != (RUN_ID, REVISION, SOURCE):
        raise ValueError("Runtime pin mismatch")
    video = LEASE / (RUN_ID + ".mp4")
    sha = hashlib.sha256(video.read_bytes()).hexdigest()
    if sha != runtime["output_sha256"]:
        raise ValueError("Video hash mismatch")
    probe = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(video)
    ]))
    stream = next(s for s in probe["streams"] if s["codec_type"] == "video")
    if (stream["width"], stream["height"], int(stream["nb_frames"]), stream["r_frame_rate"]) != (WIDTH, HEIGHT, FRAMES, str(FPS) + "/1"):
        raise ValueError("Output format does not match the contract")
    subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(video), "-f", "null", "-"], check=True)
    started = datetime.fromisoformat(allocation["startedAt"].replace("Z", "+00:00")).timestamp()
    ended = state["verified_absent_at"]
    seconds = ended - started
    rate = float(allocation["cost"])
    if seconds <= 0 or abs(rate - HOURLY) > 0.05:
        raise ValueError("Unexpected lease duration or price")
    compute = runtime["processing_seconds"] * rate / 3600
    lease_gpu = seconds * rate / 3600
    # Existing benchmark convention: temporary disk at USD 0.10/GB/30-day month.
    disk = seconds * 200 * 0.10 / (30 * 24 * 3600)
    with (LEASE / "gpu-samples.csv").open() as samples:
        gpu_rows = list(csv.DictReader(samples))
    # The sampler was still appending during export: retain complete rows only
    # and disclose any truncated trailing sample rather than inventing fields.
    complete = [row for row in gpu_rows if all(isinstance(k, str) and isinstance(v, str) for k, v in row.items())]
    normalized = [{k.strip(): v.strip() for k, v in row.items()} for row in complete]
    memory = [float(row["memory.used [MiB]"].split()[0]) for row in normalized]
    record = {
        "run_id": RUN_ID, "model": MODEL, "model_revision": REVISION,
        "source_revision": SOURCE, "container_image": IMAGE,
        "prompt_variant": "P01_EN", "prompt_sha256": PROMPT_SHA256,
        "requested_video_seconds": REQUESTED_SECONDS, "native_video_seconds": float(stream["duration"]),
        "runtime": runtime,
        "preparation": {key: preparation[key] for key in ("download_seconds", "verified_files")},
        "preparation_seconds": preparation["ready_at"] - preparation["started_at"],
        "allocation_to_ready_seconds": preparation["ready_at"] - started,
        "client_end_to_end_seconds": state["end_to_end_seconds"],
        "latency_target_seconds": 15,
        "latency_target_pass": state["end_to_end_seconds"] <= 15,
        "sampled_gpu_peak_used_mib": max(memory) if memory else None,
        "gpu_sample_count": len(normalized),
        "incomplete_gpu_samples_excluded": len(gpu_rows) - len(normalized),
        "cost": {
            "hourly_gpu_usd": rate,
            "processing_gpu_usd": compute,
            "processing_gpu_usd_per_requested_video_second": compute / REQUESTED_SECONDS,
            "processing_boundary": "First pipeline call through encoded MP4, including lazy weight loads; no warmup",
            "lease_window_seconds": seconds,
            "lease_window_gpu_usd_estimate": lease_gpu,
            "temporary_disk_usd_estimate": disk,
            "lease_window_total_usd_estimate": lease_gpu + disk,
            "lease_window_usd_per_requested_video_second_estimate": (lease_gpu + disk) / REQUESTED_SECONDS,
            "provider_actual_charge_usd": None,
            "provider_actual_charge_status": "Pending reconciliation; window estimate is not an invoice",
        },
        "quality_acceptance": "Pending human motion/audio review; no VBench run",
        "full_decode_verified": True, "pod_absence_verified": True,
        "artifact": {"path": "results/" + video.name, "bytes": video.stat().st_size, "sha256": sha},
        "streams": [{key: s[key] for key in ("codec_type", "codec_name", "width", "height", "nb_frames", "r_frame_rate", "duration", "sample_rate", "channels") if key in s} for s in probe["streams"]],
    }
    results = ROOT / "results"
    shutil.copyfile(video, results / video.name)
    (results / (RUN_ID + ".json")).write_text(json.dumps(record, indent=2) + "\n")
    with (results / "LTX_MEASUREMENTS.csv").open("w", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(["run_id", "end_to_end_seconds", "processing_seconds", "requested_video_seconds", "gpu_usd_per_requested_video_second", "lease_total_usd_estimate", "quality_accepted"])
        writer.writerow([RUN_ID, state["end_to_end_seconds"], runtime["processing_seconds"], REQUESTED_SECONDS, compute / REQUESTED_SECONDS, lease_gpu + disk, "pending"])
    print(json.dumps({"run_id": RUN_ID, "cost": record["cost"], "end_to_end_seconds": state["end_to_end_seconds"], "native_video_seconds": record["native_video_seconds"], "preparation_seconds": record["preparation_seconds"]}, indent=2))


if __name__ == "__main__":
    main()
