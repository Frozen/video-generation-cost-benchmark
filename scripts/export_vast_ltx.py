"""Validate and publish a closed Vast LTX lease without private host responses."""

import argparse
import csv
from decimal import Decimal, InvalidOperation
from fractions import Fraction
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from ltx_config import FILES, FPS, HEIGHT, IMAGE, MODEL, PROMPT_SHA256, REVISION, SOURCE, WIDTH
from ltx_reuse_config import RUN_ID as HISTORICAL_RUN_ID, VAST_RUN_ID, VAST_RETRY_RUN_ID, VAST_RECOVERY_RUN_ID, VAST_HANDOFF_RUN_ID, VAST_RESUME_RUN_ID, VAST_PROXY_RUN_ID, VAST_STABLE_RUN_ID, VAST_ALTERNATE_RUN_ID, VAST_EXTENDED_RUN_IDS, VAST_RUN_IDS, WARMUP_STAGE_1, WARMUP_STAGE_2, case_settings, cases_for, output_id
from ltx_worker import digest

ROOT = Path(__file__).resolve().parents[1]
# Verified against constants.py in the pinned native source, not just step counts.
STAGE_1 = [1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0]
STAGE_2 = [0.909375, 0.725, 0.421875, 0.0]
GPU_NAMES = ("NVIDIA H100 80GB HBM3", "NVIDIA H100-SXM5-80GB", "NVIDIA H100 SXM 80GB")
SHA256 = re.compile(r"[0-9a-f]{64}")


def read(path):
    return json.loads(path.read_text())


def number(value, minimum=0):
    if type(value) not in (int, float) or not math.isfinite(value) or value < minimum:
        raise ValueError("Invalid numeric observation")
    return value


def integer(value, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError("Invalid integer observation")
    return value


def checked_text(value, pattern):
    if not isinstance(value, str) or not re.fullmatch(pattern, value):
        raise ValueError("Invalid public observation")
    return value


def public_runtime(runtime, run_id=None):
    """Validate values as well as keys: an allowlisted field is not a free-text channel."""
    if not isinstance(runtime, dict):
        raise ValueError("Runtime must be an object")
    case = runtime.get("case")
    identity = runtime.get("run_id")
    if identity not in VAST_RUN_IDS or (run_id is not None and identity != run_id):
        raise ValueError("Foreign artifact identity")
    settings = case_settings(case, identity)
    mode, warmup = settings["mode"], settings["warmup"]
    expected = {
        "run_id": identity, "case": case, "mode": mode, "warmup": warmup,
        "source_revision": SOURCE, "model_revision": REVISION, "prompt_sha256": PROMPT_SHA256,
        "width": WIDTH, "height": HEIGHT, "frames": settings["frames"], "fps": FPS, "seed": 42,
        "stage_1_sigmas": WARMUP_STAGE_1 if warmup else STAGE_1,
        "stage_2_sigmas": WARMUP_STAGE_2 if warmup else STAGE_2,
        "precision": "BF16", "compile": False, "quantization": None, "offload": "none",
        "prompt_enhancement": False, "output_cache": False, "embedding_cache": False,
        "diffvae_mode": "chunked_eager", "torch": "2.13.0+cu132", "cuda": "13.2",
        "natten": "0.21.7+torch2130cu132", "gpu_count": 1,
        "transformer_build_count": 2 if mode == "baseline" else int(warmup),
        "resident_total_build_count": None if mode == "baseline" else 1,
    }
    # Retain compatibility with immutable initial artifacts predating this field.
    if identity in VAST_EXTENDED_RUN_IDS or "requested_video_seconds" in runtime:
        expected["requested_video_seconds"] = settings["requested_seconds"]
    for key, value in expected.items():
        if key not in runtime or type(runtime[key]) is not type(value) or runtime[key] != value:
            raise ValueError("Runtime contract mismatch: " + key)
    result = {key: runtime[key] for key in expected}
    if runtime.get("gpu") not in GPU_NAMES:
        raise ValueError("Runtime is not the reviewed H100 SXM")
    result["gpu"] = runtime["gpu"]
    memory = integer(runtime.get("gpu_total_memory_bytes"))
    if not 79_000_000_000 <= memory <= 86_000_000_000:
        raise ValueError("Unexpected H100 memory capacity")
    result["gpu_total_memory_bytes"] = memory
    for key in ("processing_seconds", "pipeline_return_seconds", "lazy_video_decode_and_encode_seconds", "completed_at"):
        result[key] = number(runtime.get(key), minimum=0.000001)
    if not math.isclose(result["pipeline_return_seconds"] + result["lazy_video_decode_and_encode_seconds"],
                        result["processing_seconds"], abs_tol=0.001):
        raise ValueError("Inconsistent pipeline timing")
    for key in ("peak_allocated_bytes", "peak_reserved_bytes", "output_bytes"):
        result[key] = integer(runtime.get(key), minimum=1)
    result["output_sha256"] = checked_text(runtime.get("output_sha256"), SHA256)
    tiling = r"TileSizeConfig\(frames=DimensionSizeConfig\(tile_size=\d+, overlap=\d+\), height=DimensionSizeConfig\(tile_size=\d+, overlap=\d+\), width=DimensionSizeConfig\(tile_size=\d+, overlap=\d+\)\)"
    result["resolved_tiling"] = checked_text(runtime.get("resolved_tiling"), tiling)
    stages = runtime.get("stages_including_weight_loading")
    if not isinstance(stages, list) or not stages or len(stages) > 12:
        raise ValueError("Missing native stage timings")
    result["stages_including_weight_loading"] = []
    for stage in stages:
        if not isinstance(stage, dict) or stage.get("stage") not in ("prompt_encoder", "stage", "upsampler", "audio_decoder"):
            raise ValueError("Unknown timed stage")
        result["stages_including_weight_loading"].append({"stage": stage["stage"], "seconds": number(stage.get("seconds"))})
    builds = runtime.get("transformer_build_seconds")
    if not isinstance(builds, list) or len(builds) != result["transformer_build_count"]:
        raise ValueError("Transformer lifecycle mismatch")
    result["transformer_build_seconds"] = [number(value) for value in builds]
    return result


def decoded_hash(video, stream):
    result = subprocess.check_output([
        "ffmpeg", "-v", "error", "-xerror", "-protocol_whitelist", "file,pipe", "-i", str(video),
        "-map", stream, "-f", "hash", "-hash", "sha256", "-",
    ], text=True, stderr=subprocess.PIPE, timeout=120).strip()
    if not result.startswith("SHA256="):
        raise ValueError("Missing decoded-stream hash")
    return checked_text(result[7:], SHA256)


def validate_artifact(video, runtime, run_id=None):
    """Fully decode a downloaded original before acknowledging its export to the worker."""
    video = Path(video)
    clean = public_runtime(runtime, run_id=run_id)
    frames = clean["frames"]
    if video.name != output_id(clean["case"], clean["run_id"]) + ".mp4" or video.is_symlink():
        raise ValueError("Foreign artifact filename")
    if video.stat().st_size != clean["output_bytes"] or digest(video) != clean["output_sha256"]:
        raise ValueError("Encoded artifact integrity mismatch")
    probe = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe", "-count_frames",
        "-show_streams", "-show_format", "-of", "json", str(video),
    ], stderr=subprocess.PIPE, timeout=120))
    streams = probe.get("streams", [])
    videos = [stream for stream in streams if stream.get("codec_type") == "video"]
    audios = [stream for stream in streams if stream.get("codec_type") == "audio"]
    if len(streams) != 2 or len(videos) != 1 or len(audios) != 1:
        raise ValueError("Expected exactly one native video and audio stream")
    visual, audio = videos[0], audios[0]
    try:
        shape = (visual["width"], visual["height"], int(visual["nb_frames"]), int(visual["nb_read_frames"]))
        rates = (Fraction(visual["r_frame_rate"]), Fraction(visual["avg_frame_rate"]))
        duration = number(float(visual["duration"]), minimum=0.001)
        audio_duration = number(float(audio["duration"]), minimum=0.001)
        channels, sample_rate = int(audio["channels"]), int(audio["sample_rate"])
        audio_frames = int(audio["nb_read_frames"])
    except (KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
        raise ValueError("Incomplete stream readout") from exc
    if shape != (WIDTH, HEIGHT, frames, frames) or rates != (FPS, FPS):
        raise ValueError("Native output shape mismatch")
    if abs(duration - frames / FPS) > 0.00001 or abs(audio_duration - duration) > 0.1:
        raise ValueError("Native output duration mismatch")
    if channels not in (1, 2) or sample_rate <= 0 or audio_frames <= 0:
        raise ValueError("Missing native audio samples")
    hashes = {"video": decoded_hash(video, "0:v:0"), "audio": decoded_hash(video, "0:a:0")}
    return {"width": WIDTH, "height": HEIGHT, "frames": frames, "fps": FPS,
            "duration_seconds": duration, "audio_duration_seconds": audio_duration,
            "audio_channels": channels, "audio_sample_rate": sample_rate,
            "output_sha256": clean["output_sha256"], "output_bytes": clean["output_bytes"],
            "decoded_stream_sha256": hashes, "full_decode_verified": True}


def public_quote(quote):
    result = {}
    for key in ("id", "machine_id", "num_gpus", "allocated_storage"):
        result[key] = integer(quote.get(key), minimum=1)
    if quote.get("gpu_name") != "H100 SXM" or quote.get("verification") != "verified":
        raise ValueError("Unreviewed Vast quote")
    if result["num_gpus"] != 1 or result["allocated_storage"] != 200:
        raise ValueError("Unreviewed Vast allocation")
    result.update(gpu_name=quote["gpu_name"], verification=quote["verification"])
    for key in ("gpu_ram", "cpu_ram", "cuda_max_good", "reliability", "dph_base", "dph_total",
                "storage_total_cost", "storage_cost", "inet_down_cost", "inet_up_cost"):
        result[key] = number(quote.get(key))
    result["driver_version"] = checked_text(quote.get("driver_version"), r"\d+\.\d+(?:\.\d+)?")
    if result["dph_base"] <= 0 or result["dph_total"] < result["dph_base"]:
        raise ValueError("Invalid compute and disk quote")
    return result


def public_hardware(hardware):
    if not isinstance(hardware, dict) or hardware.get("architecture") != "x86_64" or hardware.get("gpu_name") not in GPU_NAMES:
        raise ValueError("Unexpected observed host hardware")
    if hardware.get("mig_mode") not in ("Disabled", "N/A", "[N/A]"):
        raise ValueError("Unexpected MIG configuration")
    result = {key: hardware[key] for key in ("architecture", "gpu_name", "mig_mode")}
    result["driver_version"] = checked_text(hardware.get("driver_version"), r"\d+\.\d+(?:\.\d+)?")
    for key in ("gpu_memory_mib", "memory_bytes", "disk_total_bytes", "disk_free_bytes", "cpu_count"):
        result[key] = integer(hardware.get(key), minimum=1)
    return result


def network_cost(observation, quote):
    """Admission traffic headroom is not measured usage or an invoice."""
    observation = observation if isinstance(observation, dict) else {}
    observed = {}
    for key in ("inbound_bytes", "outbound_bytes", "local_upload_bytes", "local_download_bytes",
                "provider_inbound_bytes", "provider_outbound_bytes"):
        observed[key] = None if observation.get(key) is None else integer(observation[key])
    measured = None
    billable = {}
    # Only provider-labelled billable units can establish a transfer cost estimate.
    if observation.get("billable_source") == "provider":
        for key in ("billable_inbound_gb", "billable_outbound_gb"):
            billable[key] = number(observation.get(key))
        unit = integer(observation.get("billing_unit_bytes"), minimum=1)
        if unit not in (1_000_000_000, 1_073_741_824):
            raise ValueError("Unknown provider transfer unit")
        billable["billing_unit_bytes"] = unit
        measured = billable["billable_inbound_gb"] * quote["inet_down_cost"] + billable["billable_outbound_gb"] * quote["inet_up_cost"]
    return {"status": "provider_usage_estimate" if measured is not None else "pending_unknown_actual",
            "transfer_usd_estimate": measured, "observed_counters": observed, "provider_billable_usage": billable or None,
            "counter_scope": "Network namespace/local counters, not provider billable units; image and other host-side traffic may be excluded",
            "admission_inbound_gb_limit": 100, "admission_outbound_gb_limit": 5,
            "admission_transfer_usd_bound": 100 * quote["inet_down_cost"] + 5 * quote["inet_up_cost"],
            "unit_note": "Quote USD/GB retained; local bytes do not prove billable usage or zero transfer cost",
            "bound_note": "Operational admission allowance, not a provider-enforced cap or a measured bill"}


def preparation_evidence(lease_dir, complete):
    path = lease_dir / "prepare-status.json"
    preparation = read(path) if path.is_file() else {}
    if not isinstance(preparation, dict):
        raise ValueError("Preparation evidence must be an object")
    result = {}
    if preparation.get("phase") in ("installing", "downloading", "hash_verification", "ready", "failed"):
        result["phase"] = preparation["phase"]
    for key in ("started_at", "ready_at", "download_started_at", "download_seconds"):
        if key in preparation:
            result[key] = number(preparation[key])
    if complete or preparation.get("phase") == "ready":
        expected = [{"file": name, "bytes": size, "sha256": sha} for name, (size, sha) in FILES.items()]
        if (preparation.get("phase"), preparation.get("source_revision"), preparation.get("model_revision")) != ("ready", SOURCE, REVISION):
            raise ValueError("Missing pinned preparation evidence")
        if preparation.get("verified_files") != expected:
            raise ValueError("Missing six-file integrity verification")
        if preparation.get("frozen") is not True:
            raise ValueError("Preparation did not use the supplied lock")
        result["frozen"] = True
        result["uv_lock_sha256"] = checked_text(preparation.get("uv_lock_sha256"), SHA256)
        result["natten_wheel_manifest_sha256"] = checked_text(preparation.get("natten_wheel_manifest_sha256"), SHA256)
        result.update(source_revision=SOURCE, model_revision=REVISION, verified_files=expected)
    if "started_at" in result and "ready_at" in result:
        result["prepare_seconds"] = number(result["ready_at"] - result["started_at"])
    freeze = lease_dir / "dependencies.txt"
    dependencies, omitted = [], 0
    if freeze.is_file():
        for line in freeze.read_text().splitlines():
            if re.fullmatch(r"(?:torch|natten|transformers|nvidia-cudnn-cu13|numpy|av|ltx-core|ltx-pipelines)==[0-9][A-Za-z0-9_.+!-]*", line):
                dependencies.append(line)
            elif line.strip():
                omitted += 1
        result["dependency_freeze_sha256"] = digest(freeze)
    elif complete:
        raise ValueError("Missing dependency freeze")
    result["dependencies"] = dependencies
    result["unpublished_dependency_lines"] = omitted
    result["dependency_publication"] = ("Critical package versions only; full private freeze retained by its SHA256"
                                        if "dependency_freeze_sha256" in result else "No dependency freeze was exported")
    return result


def decimal_observation(value):
    """Read a nonnegative journal decimal without exposing arbitrary text."""
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError("Invalid decimal observation")
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("Invalid decimal observation") from exc
    if not amount.is_finite() or amount < 0 or not math.isfinite(float(amount)):
        raise ValueError("Invalid decimal observation")
    return float(amount)


def public_prior_attempt(prior, run_id, instance_id):
    if (not isinstance(prior, dict) or prior.get("run_id") != run_id
            or type(prior.get("instance_id")) is not int or prior["instance_id"] != instance_id
            or prior.get("absence_verified") is not True):
        raise ValueError("Missing closed prior attempt evidence")
    reported = prior.get("reported_charge_usd")
    result = {"run_id": run_id, "instance_id": instance_id, "absence_verified": True,
              "reported_charge_usd": None if reported is None else decimal_observation(reported),
              "observed_drawdown_usd": decimal_observation(prior.get("observed_drawdown_usd")),
              "exposure_hold_usd": decimal_observation(prior.get("exposure_hold_usd"))}
    if result["exposure_hold_usd"] < max(result["observed_drawdown_usd"], result["reported_charge_usd"] or 0):
        raise ValueError("Inconsistent prior attempt exposure")
    return result


def comparison(baseline, resident):
    return {
        "processing_speedup": baseline["runtime"]["processing_seconds"] / resident["runtime"]["processing_seconds"],
        "end_to_end_speedup": (baseline["client_end_to_end_seconds"] / resident["client_end_to_end_seconds"]
                              if baseline["client_end_to_end_seconds"] is not None and resident["client_end_to_end_seconds"] is not None else None),
        "decoded_streams_equal": {stream: baseline["artifact_validation"]["decoded_stream_sha256"][stream] == resident["artifact_validation"]["decoded_stream_sha256"][stream] for stream in ("video", "audio")},
        "interpretation": "One sample per mode, fixed order/cache bias; hash equality is not quality acceptance or a provider-wide performance ranking"}


def export(lease_dir: Path, output_dir: Path):
    lease_dir, output_dir = Path(lease_dir), Path(output_dir)
    state = read(lease_dir / "state.json")
    run_id = state.get("run_id")
    if state.get("provider") != "vast.ai" or run_id not in VAST_RUN_IDS:
        raise ValueError("Foreign lease identity")
    cases = cases_for(run_id)
    prior, additional_priors = None, []
    additional = state.get("additional_prior_attempts", [])
    if run_id in (VAST_RECOVERY_RUN_ID, VAST_HANDOFF_RUN_ID, VAST_RESUME_RUN_ID, VAST_PROXY_RUN_ID, VAST_STABLE_RUN_ID, VAST_ALTERNATE_RUN_ID):
        expected = [(VAST_RETRY_RUN_ID, 51807213)]
        if run_id in (VAST_HANDOFF_RUN_ID, VAST_RESUME_RUN_ID, VAST_PROXY_RUN_ID, VAST_STABLE_RUN_ID, VAST_ALTERNATE_RUN_ID):
            expected.append((VAST_RECOVERY_RUN_ID, 51811500))
        if run_id in (VAST_RESUME_RUN_ID, VAST_PROXY_RUN_ID, VAST_STABLE_RUN_ID, VAST_ALTERNATE_RUN_ID):
            expected.append((VAST_HANDOFF_RUN_ID, 51812997))
        if run_id in (VAST_PROXY_RUN_ID, VAST_STABLE_RUN_ID, VAST_ALTERNATE_RUN_ID):
            expected.append((VAST_RESUME_RUN_ID, 51815605))
        if run_id in (VAST_STABLE_RUN_ID, VAST_ALTERNATE_RUN_ID):
            expected.append((VAST_PROXY_RUN_ID, 51818794))
        if run_id == VAST_ALTERNATE_RUN_ID:
            expected.append((VAST_STABLE_RUN_ID, 51821924))
        if not isinstance(additional, list) or len(additional) != len(expected):
            raise ValueError("Recovery is missing a required additional closed attempt")
        additional_priors = [public_prior_attempt(item, identity, instance)
                             for item, (identity, instance) in zip(additional, expected)]
    elif additional != []:
        raise ValueError("Unreviewed additional prior attempts")
    if run_id in VAST_EXTENDED_RUN_IDS:
        prior = public_prior_attempt(state.get("prior_attempt"), VAST_RUN_ID, 51778886)
        prior["reported_charge_status"] = "pending" if prior["reported_charge_usd"] is None else "reported_to_date_not_final"
        prior["exposure_hold_status"] = "Conservative admission reserve, not an invoice or measured cost"
        prior_hold = decimal_observation(state.get("prior_exposure_usd"))
        expected_hold = sum(Decimal(str(attempt["exposure_hold_usd"])) for attempt in (prior, *additional_priors))
        if Decimal(str(prior_hold)) != expected_hold:
            raise ValueError("Inconsistent cumulative prior attempt exposure")
    if state.get("status") not in ("terminated", "failed", "partial") or state.get("absence_verified") is not True:
        raise ValueError("Publication requires a closed lease and verified instance absence")
    if (state.get("image"), state.get("source_revision"), state.get("model_revision"), state.get("prompt_sha256")) != (IMAGE, SOURCE, REVISION, PROMPT_SHA256):
        raise ValueError("Lease pin mismatch")
    instance_id = integer(state.get("instance_id"), minimum=1)
    guard = read(lease_dir / "guard-state.json")
    if guard.get("absence_verified") is not True or any(guard.get(key) != state.get(key) for key in ("instance_id", "label", "run_id")):
        raise ValueError("Independent owned-instance absence verification is missing")
    start = number(state.get("create_requested_at"), minimum=1)
    controller_end = number(state.get("verified_absent_at"), minimum=start)
    independent_end = number(guard.get("verified_absent_at"), minimum=start)
    end = min(controller_end, independent_end)
    deadline = number(state.get("deadline"), minimum=start)
    if state.get("reservation_usd") != ("9.99" if run_id in (VAST_HANDOFF_RUN_ID, VAST_RESUME_RUN_ID, VAST_PROXY_RUN_ID, VAST_STABLE_RUN_ID, VAST_ALTERNATE_RUN_ID) else "8.00"):
        raise ValueError("Unreviewed allowance")
    submissions = integer(state.get("generation_submissions"))
    if submissions > len(cases):
        raise ValueError("Extra generation submissions are not the approved trial")
    quote = public_quote(state["quote"])
    network = network_cost(state.get("transfer_observation"), quote)
    actual = state.get("provider_actual_charge_usd")
    if actual is not None:
        actual = number(actual)
    outputs, rows = [], []
    case_states = state.get("cases", {})
    if not isinstance(case_states, dict) or set(case_states) - {case for case, _, _ in cases}:
        raise ValueError("Foreign case state")
    for case, mode, warmup in cases:
        settings = case_settings(case, run_id)
        seconds = settings["requested_seconds"]
        case_id = output_id(case, run_id)
        video, runtime_path = lease_dir / (case_id + ".mp4"), lease_dir / (case_id + ".json")
        case_state = case_states.get(case, {})
        row = {"case": case, "warmup": warmup, "status": "not_exported", "processing_seconds": None,
               "end_to_end_seconds": None, "compute_usd_per_requested_video_second": None, "build_count": None}
        if run_id in VAST_EXTENDED_RUN_IDS:
            row["requested_video_seconds"] = seconds
        if video.is_file() and runtime_path.is_file():
            try:
                runtime = public_runtime(read(runtime_path), run_id=run_id)
                if runtime["case"] != case:
                    raise ValueError("Cross-case artifact")
                metadata = validate_artifact(video, runtime, run_id=run_id)
                e2e = case_state.get("end_to_end_seconds")
                if e2e is not None:
                    e2e = number(e2e, minimum=0.000001)
            except (ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError):
                row["status"] = "artifact_validation_failed"
            else:
                cost = runtime["processing_seconds"] * quote["dph_base"] / 3600
                record = {"provider": "vast.ai", "run_id": case_id, "lease_run_id": run_id,
                          "model": MODEL, "runtime": runtime, "container_image": IMAGE,
                          "prompt_sha256": PROMPT_SHA256, "prompt_variant": "P01_EN",
                          "requested_video_seconds": seconds, "native_video_seconds": metadata["duration_seconds"],
                          "client_end_to_end_seconds": e2e, "latency_target_seconds": None if warmup else 15,
                          "latency_pass": None if warmup or e2e is None else e2e <= 15,
                          "cost": {"compute_hourly_usd": quote["dph_base"], "pipeline_compute_usd": cost,
                                   "compute_usd_per_requested_video_second": cost / seconds,
                                   "boundary": "Pipeline through encoded MP4; excludes preparation, warmups, idle, disk and network; a subset of lease cost, never added to it"},
                          "artifact": video.name, "artifact_validation": metadata,
                          "quality_acceptance": "Not applicable: technical warmup" if warmup else "Pending human motion/audio and prompt-adherence review"}
                outputs.append((video, record))
                row.update(status="exported", processing_seconds=runtime["processing_seconds"],
                           end_to_end_seconds=e2e, compute_usd_per_requested_video_second=cost / seconds,
                           build_count=runtime["transformer_build_count"])
        rows.append(row)
    complete = (len(outputs) == len(cases) and submissions == len(cases) and state["status"] == "terminated"
                and all(case_states.get(case, {}).get("status") == "exported"
                        and case_states.get(case, {}).get("decode_verified") is True
                        and case_states.get(case, {}).get("end_to_end_seconds") is not None for case, _, _ in cases))
    try:
        preparation = preparation_evidence(lease_dir, complete)
    except (ValueError, KeyError, TypeError, OSError):
        preparation = {"status": "invalid_or_missing_evidence"}
        complete = False
    try:
        hardware = public_hardware(state["hardware"]) if state.get("hardware") is not None else None
        if complete and hardware is None:
            raise ValueError("Missing observed hardware")
    except (ValueError, KeyError, TypeError):
        hardware = None
        complete = False
    window = end - start
    compute_disk = window / 3600 * quote["dph_total"]
    total = None if network["transfer_usd_estimate"] is None else compute_disk + network["transfer_usd_estimate"]
    pipeline_seconds = sum(record["runtime"]["processing_seconds"] for _, record in outputs)
    summary = {"provider": "vast.ai", "run_id": run_id, "status": "completed" if complete else "failed" if state["status"] == "failed" or not outputs else "partial",
               "controller_status": state["status"], "instance_id": instance_id, "absence_verified": True,
               "independent_absence_verified": True, "create_requested_at": start, "verified_absent_at": end,
               "controller_verified_absent_at": controller_end, "independent_verified_absent_at": independent_end,
               "controller_observation_window_seconds": controller_end - start,
               "verified_lifetime_upper_bound_seconds": window, "deadline_exceeded": end > deadline,
               "provider_billed_seconds": None, "provider_billed_duration_status": "Unknown; create-to-absence wall time is not an exact billing interval",
               "reservation_usd": state["reservation_usd"], "allowance_boundary": "Cumulative Vast-stage allowance including the first attempt; unrelated to the historical USD25 ledger" if prior else "New additional Vast-stage allowance; unrelated to the historical USD25 ledger",
               "quote": quote, "container_image": IMAGE, "source_revision": SOURCE, "model_revision": REVISION,
               "prompt_sha256": PROMPT_SHA256, "case_order": [case for case, _, _ in cases],
               "generation_submissions": submissions, "completed_output_count": len(outputs), "cases": rows,
               "measured_output_count": sum(not record["runtime"]["warmup"] for _, record in outputs),
               "technical_warmup_count": sum(record["runtime"]["warmup"] for _, record in outputs),
               "preparation": preparation, "hardware": hardware, "network": network,
               "completed_pipeline_seconds": pipeline_seconds,
               "window_outside_completed_pipeline_seconds": window - pipeline_seconds,
               "unattributed_time_note": "Includes preparation, transfers, idle, teardown and any failed/unexported processing; not a measured idle-only duration. A negative value indicates inconsistent observations",
               "warmup_pipeline_compute_usd": sum(record["cost"]["pipeline_compute_usd"] for _, record in outputs if record["runtime"]["warmup"]),
               "measured_pipeline_compute_usd": sum(record["cost"]["pipeline_compute_usd"] for _, record in outputs if not record["runtime"]["warmup"]),
               "compute_and_disk_window_usd_estimate": compute_disk,
               "whole_experiment_usd_estimate": total,
               "window_plus_admission_network_usd_bound": compute_disk + network["admission_transfer_usd_bound"],
               "cost_boundary": "dph_total includes allocated disk once; all preparation, generation, idle and failures lie inside the observation window. Pipeline subtotals are not additional charges. Network separate; taxes and credit purchases are not usage charges",
               "provider_actual_charge_usd": actual,
               "provider_actual_charge_status": "pending" if actual is None else "reported_to_date_not_final",
               "software_environment": "Same-model/settings replication; historical private uv.lock unavailable, not a proven bit-identical software environment",
               "quality_acceptance": "Pending human motion/audio and prompt-adherence review" if outputs else "Not evaluated: no generated artifact"}
    if run_id in (VAST_PROXY_RUN_ID, VAST_STABLE_RUN_ID, VAST_ALTERNATE_RUN_ID):
        summary.update(ssh_transport=state.get("ssh_transport", "proxy" if run_id == VAST_PROXY_RUN_ID else "direct"),
                       pre_model_container_reconfigured=bool(state.get("network_reconfiguration")),
                       cuda_driver_compatibility="CUDA 13.x minor-version compatibility; driver >= 580, frozen runtime remains CUDA 13.2")
    if prior:
        reported_charges = [actual, prior["reported_charge_usd"], *(attempt["reported_charge_usd"] for attempt in additional_priors)]
        cumulative_reported = (None if any(charge is None for charge in reported_charges)
                               else float(sum(Decimal(str(charge)) for charge in reported_charges)))
        summary.update(
            prior_attempt=prior, prior_exposure_usd=prior_hold,
            cumulative_stage_reported_usd=cumulative_reported,
            cumulative_stage_reported_status="pending" if cumulative_reported is None else "reported_to_date_not_final",
            cumulative_stage_usd_estimate=None,
            cumulative_stage_estimate_status="Unknown: prior attempt network usage is not established; exposure hold is not measured cost",
            cumulative_window_plus_admission_network_usd_bound=prior_hold + compute_disk + network["admission_transfer_usd_bound"],
            warmup_scope="Two 5s technical warmups; each 20s case is the first 20s shape in its mode",
        )
        if additional_priors:
            summary["additional_prior_attempts"] = additional_priors
            summary["allowance_boundary"] = "Cumulative Vast-stage allowance including all prior attempts; unrelated to the historical USD25 ledger"
    by_case = {record["runtime"]["case"]: record for _, record in outputs}
    if run_id in VAST_EXTENDED_RUN_IDS:
        summary["comparison_by_requested_seconds"] = {}
        for seconds in (5, 20):
            baseline, resident = by_case.get(f"BASE_WARM_{seconds}S"), by_case.get(f"REUSE_WARM_{seconds}S")
            if baseline is not None and resident is not None:
                summary["comparison_by_requested_seconds"][str(seconds)] = comparison(baseline, resident)
    elif all(case in by_case for case in ("BASE_WARM", "REUSE_WARM")):
        summary["comparison"] = comparison(by_case["BASE_WARM"], by_case["REUSE_WARM"])
    historical = {}
    for _, record in outputs:
        case = record["runtime"]["case"]
        if record["requested_video_seconds"] != 5:
            continue
        historical_case = case.removesuffix("_5S") if run_id in VAST_EXTENDED_RUN_IDS else case
        historical_path = ROOT / "results" / (output_id(historical_case, HISTORICAL_RUN_ID) + ".json")
        if historical_path.is_file():
            hashes = read(historical_path).get("decoded_stream_sha256", {})
            if all(isinstance(hashes.get(stream), str) and SHA256.fullmatch(hashes[stream]) for stream in ("video", "audio")):
                historical[case] = {stream: hashes[stream] == record["artifact_validation"]["decoded_stream_sha256"][stream] for stream in ("video", "audio")}
    summary["historical_runpod_decoded_streams_equal"] = historical
    # Finish validation before creating any public success record; reserve every destination
    # exclusively so historical files, symlinks and prior exports cannot be overwritten.
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_name = {
        VAST_RUN_ID: "VAST_LTX_REUSE_MEASUREMENTS.csv",
        VAST_RETRY_RUN_ID: "VAST_LTX_REUSE_RETRY_MEASUREMENTS.csv",
        VAST_RECOVERY_RUN_ID: "VAST_LTX_REUSE_RECOVERY_MEASUREMENTS.csv",
        VAST_HANDOFF_RUN_ID: "VAST_LTX_REUSE_HANDOFF_MEASUREMENTS.csv",
        VAST_RESUME_RUN_ID: "VAST_LTX_REUSE_RESUME_MEASUREMENTS.csv",
        VAST_PROXY_RUN_ID: "VAST_LTX_REUSE_PROXY_MEASUREMENTS.csv",
        VAST_STABLE_RUN_ID: "VAST_LTX_REUSE_STABLE_MEASUREMENTS.csv",
        VAST_ALTERNATE_RUN_ID: "VAST_LTX_REUSE_ALTERNATE_MEASUREMENTS.csv",
    }[run_id]
    names = [run_id + ".json", csv_name]
    names.extend(name for video, record in outputs for name in (video.name, record["run_id"] + ".json"))
    if any((output_dir / name).exists() or (output_dir / name).is_symlink() for name in names):
        raise FileExistsError("Refusing to replace an earlier public artifact")
    with tempfile.TemporaryDirectory(prefix="vast-export-") as directory:
        stage = Path(directory)
        for video, record in outputs:
            shutil.copyfile(video, stage / video.name)
            (stage / (record["run_id"] + ".json")).write_text(json.dumps(record, indent=2, allow_nan=False) + "\n")
        (stage / (run_id + ".json")).write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
        with (stage / csv_name).open("w", newline="") as out:
            writer = csv.DictWriter(out, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        created = []
        try:
            # Summary last: its presence indicates the complete set was published.
            for name in names[1:] + names[:1]:
                with (output_dir / name).open("xb") as out:
                    created.append(output_dir / name)
                    with (stage / name).open("rb") as source:
                        shutil.copyfileobj(source, out)
        except Exception:
            for path in created:
                path.unlink()
            raise
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lease", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export(args.lease, args.output), indent=2))


if __name__ == "__main__":
    main()
