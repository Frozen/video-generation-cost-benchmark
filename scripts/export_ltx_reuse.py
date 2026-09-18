"""Allowlisted offline export of the closed warm LTX comparison."""

import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from ltx_config import FPS, FRAMES, HEIGHT, HOURLY, IMAGE, MODEL, PROMPT_SHA256, REVISION, SOURCE, WIDTH
from ltx_reuse_config import CASES, RUN_ID, WARMUP_STAGE_1, WARMUP_STAGE_2, output_id

ROOT = Path(__file__).resolve().parents[1]
LEASE = ROOT / "private/ltx-reuse-h100-p01-001"


def read(path):
    return json.loads(path.read_text())


def decoded_hash(path, stream):
    result = subprocess.check_output(["ffmpeg", "-v", "error", "-xerror", "-i", str(path),
                                      "-map", stream, "-f", "hash", "-hash", "sha256", "-"], text=True)
    if not result.startswith("SHA256="):
        raise ValueError("Missing decoded-stream hash")
    return result.strip().split("=", 1)[1]


def main():
    state = read(LEASE / "state.json")
    if state["status"] != "terminated" or not state.get("decode_verified") or state["generation_submissions"] != 4:
        raise ValueError("Expected four exported requests and verified shutdown")
    allocation, preparation = read(LEASE / "allocation-observation.json"), read(LEASE / "prepare-status.json")
    rate = float(allocation["cost"])
    if abs(rate - HOURLY) > 0.05:
        raise ValueError("Unexpected rate")
    outputs = []
    for case, mode, warmup in CASES:
        runtime = read(LEASE / (output_id(case) + ".json"))
        if (runtime["run_id"], runtime["case"], runtime["mode"], runtime["warmup"], runtime["source_revision"], runtime["model_revision"]) != (RUN_ID, case, mode, warmup, SOURCE, REVISION):
            raise ValueError("Runtime contract mismatch")
        if warmup and (runtime["stage_1_sigmas"] != WARMUP_STAGE_1 or runtime["stage_2_sigmas"] != WARMUP_STAGE_2):
            raise ValueError("Warmup schedule mismatch")
        if not warmup and (len(runtime["stage_1_sigmas"]) != 9 or len(runtime["stage_2_sigmas"]) != 4):
            raise ValueError("Measured schedule mismatch")
        if not state["cases"][case].get("decode_verified"):
            raise ValueError("Missing client artifact validation")
        video = LEASE / (output_id(case) + ".mp4")
        if hashlib.sha256(video.read_bytes()).hexdigest() != runtime["output_sha256"]:
            raise ValueError("Video SHA mismatch")
        probe = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(video)]))
        stream = next(s for s in probe["streams"] if s["codec_type"] == "video")
        if (stream["width"], stream["height"], int(stream["nb_frames"]), stream["r_frame_rate"]) != (WIDTH, HEIGHT, FRAMES, str(FPS) + "/1"):
            raise ValueError("Native output shape mismatch")
        decoded = {"video": decoded_hash(video, "0:v:0"), "audio": decoded_hash(video, "0:a:0")}
        e2e = state["cases"][case]["end_to_end_seconds"]
        cost = runtime["processing_seconds"] * rate / 3600
        record = {"run_id": output_id(case), "lease_run_id": RUN_ID, "model": MODEL,
                  "runtime": runtime, "requested_video_seconds": 5, "native_video_seconds": float(stream["duration"]),
                  "prompt_sha256": PROMPT_SHA256, "prompt_variant": "P01_EN", "container_image": IMAGE,
                  "client_end_to_end_seconds": e2e, "latency_target_seconds": None if warmup else 15,
                  "latency_pass": None if warmup else e2e <= 15,
                  "cost": {"hourly_gpu_usd": rate, "processing_gpu_usd": cost,
                           "processing_gpu_usd_per_requested_video_second": cost / 5,
                           "boundary": "Pipeline call through encoded MP4 only; excludes setup, warmup, idle, storage and download"},
                  "artifact": "results/" + video.name, "decoded_stream_sha256": decoded,
                  "full_decode_verified": True,
                  "quality_acceptance": "Not applicable: technical warmup" if warmup else "Pending human motion/audio review"}
        outputs.append(record)
        shutil.copyfile(video, ROOT / "results" / video.name)
        (ROOT / "results" / (output_id(case) + ".json")).write_text(json.dumps(record, indent=2) + "\n")
    first, second = (next(r for r in outputs if r["runtime"]["case"] == case) for case in ("BASE_WARM", "REUSE_WARM"))
    if first["runtime"]["transformer_build_count"] != 2 or second["runtime"]["transformer_build_count"] != 0:
        raise ValueError("Observed transformer lifecycle does not establish the planned comparison")
    start = datetime.fromisoformat(allocation["startedAt"].replace("Z", "+00:00")).timestamp()
    window = state["verified_absent_at"] - start
    total = window / 3600 * rate + window * 200 * .10 / (30 * 24 * 3600)
    summary = {"run_id": RUN_ID, "case_order": [c[0] for c in CASES], "measured_output_count": 2, "technical_warmup_count": 2,
               "requested_measured_output_seconds": 10, "lease_window_seconds": window,
               "lease_window_total_usd_estimate": total, "whole_experiment_usd_per_measured_video_second_estimate": total / 10,
               "provider_actual_charge_usd": None, "provider_actual_charge_status": "Pending; rental window is an estimate",
               "download_seconds": preparation["download_seconds"],
               "prepare_seconds": preparation["ready_at"] - preparation["started_at"],
               "measured_processing_speedup": first["runtime"]["processing_seconds"] / second["runtime"]["processing_seconds"],
               "measured_end_to_end_speedup": first["client_end_to_end_seconds"] / second["client_end_to_end_seconds"],
               "measured_decoded_video_equal": first["decoded_stream_sha256"]["video"] == second["decoded_stream_sha256"]["video"],
               "measured_decoded_audio_equal": first["decoded_stream_sha256"]["audio"] == second["decoded_stream_sha256"]["audio"],
               "warmup_processing_gpu_usd": sum(r["cost"]["processing_gpu_usd"] for r in outputs if r["runtime"]["warmup"]),
               "measured_processing_gpu_usd": sum(r["cost"]["processing_gpu_usd"] for r in outputs if not r["runtime"]["warmup"]),
               "quality_acceptance": "Pending; equal hashes are not proof of acceptable quality",
               "pod_absence_verified": True,
               "cases": [{"case": r["runtime"]["case"], "warmup": r["runtime"]["warmup"], "processing_seconds": r["runtime"]["processing_seconds"],
                          "end_to_end_seconds": r["client_end_to_end_seconds"], "gpu_usd_per_requested_video_second": r["cost"]["processing_gpu_usd_per_requested_video_second"],
                          "build_count": r["runtime"]["transformer_build_count"]} for r in outputs]}
    (ROOT / "results" / (RUN_ID + ".json")).write_text(json.dumps(summary, indent=2) + "\n")
    with (ROOT / "results/LTX_REUSE_MEASUREMENTS.csv").open("w", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=list(summary["cases"][0]))
        writer.writeheader()
        writer.writerows(summary["cases"])
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
