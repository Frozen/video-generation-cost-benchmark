"""Finite, preloaded sequential requests; artifact export does not gate generation.

The provider lease must have a separate, verified termination guard. This module
does not provision, reserve money, retry uncertain work, or prove output quality.
"""

import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import time


def finite(value, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Expected a finite number")
    if not math.isfinite(value) or value < 0 or (positive and value == 0):
        raise ValueError("Expected a finite nonnegative number")
    return value


def identity(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", value):
        raise ValueError("Invalid run/request identity")
    return value


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_manifest(plan):
    if type(plan.get("version")) is not int or plan["version"] != 1:
        raise ValueError("Unsupported load manifest")
    identity(plan["run_id"])
    quality = plan["quality_contract"]
    if (type(quality.get("audio_required")) is not bool
            or not re.fullmatch(r"[0-9a-f]{64}", str(quality.get("criteria_sha256", "")))):
        raise ValueError("A frozen quality contract is required before generation")
    profile = plan["profile"]
    for field in ("width", "height", "frames"):
        if type(profile.get(field)) is not int or profile[field] <= 0:
            raise ValueError("Native output dimensions and frame count must be positive integers")
    finite(profile["fps"], positive=True)
    finite(profile["requested_video_seconds"], positive=True)
    if type(profile.get("audio")) is not bool:
        raise ValueError("The native audio capability must be explicit")
    if quality["audio_required"] and not profile["audio"]:
        raise ValueError("A silent profile cannot satisfy an audio-required comparison")
    if type(plan.get("batch_size")) is not int or plan["batch_size"] != 1:
        raise ValueError("This runner measures batch size one")
    if type(plan.get("concurrency")) is not int or plan["concurrency"] != 1:
        raise ValueError("This runner measures one generation at a time")
    limits = plan["limits"]
    cutoff = finite(limits["admission_deadline_epoch"], positive=True)
    deadline = finite(limits["shutdown_deadline_epoch"], positive=True)
    drain = finite(limits["export_reserve_seconds"], positive=True)
    request_bound = finite(limits["request_bound_seconds"], positive=True)
    if cutoff + request_bound + drain > deadline:
        raise ValueError("Admission cutoff leaves insufficient generation/export allowance")
    requests = plan["requests"]
    if not isinstance(requests, list) or not requests:
        raise ValueError("A finite, nonempty request list is required")
    if type(limits.get("max_requests")) is not int or not 1 <= len(requests) <= limits["max_requests"]:
        raise ValueError("Request count exceeds the manifest bound")
    seen = set()
    generation_inputs = set()
    for request in requests:
        request_id = identity(request["request_id"])
        if request_id in seen:
            raise ValueError("Repeated scenes need distinct attempt IDs")
        seen.add(request_id)
        prompt = request["prompt"]
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("A frozen prompt is required")
        if hashlib.sha256(prompt.encode()).hexdigest() != request["prompt_sha256"]:
            raise ValueError("Frozen prompt hash mismatch")
        if type(request["seed"]) is not int or not 0 <= request["seed"] < 2**32:
            raise ValueError("An explicit 32-bit seed is required")
        generation_key = (request["prompt_sha256"], request["seed"])
        if generation_key in generation_inputs:
            raise ValueError("Load requests must use distinct prompt/seed pairs")
        generation_inputs.add(generation_key)
        finite(request["requested_video_seconds"], positive=True)
        if request["requested_video_seconds"] != profile["requested_video_seconds"]:
            raise ValueError("Requested seconds differ from the frozen generation profile")
        if request.get("input_assets"):
            raise ValueError("These text-only workers do not implement input media")
        for field in ("source_url", "scene_id"):
            if not isinstance(request.get(field), str) or not request[field].strip():
                raise ValueError("Request provenance and scene identity are required")
    return plan


def warmup_request(plan):
    """Derive a reproducible technical warmup that cannot match measured inputs."""
    validate_manifest(plan)
    request = dict(plan["requests"][0])
    used = {r["seed"] for r in plan["requests"]
            if r["prompt_sha256"] == request["prompt_sha256"]}
    seed = (request["seed"] + 2**31) % 2**32
    while seed in used:
        seed = (seed + 1) % 2**32
    request["seed"] = seed
    return request


def read_manifest(path):
    data = Path(path).read_bytes()
    return validate_manifest(json.loads(data)), hashlib.sha256(data).hexdigest()


def verify_checkout(path, revision):
    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=path, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=path, text=True)
    if actual != revision or dirty.strip():
        raise ValueError("Runtime source is not the clean pinned checkout")


def verify_guard(path, deadline):
    guard = json.loads(Path(path).read_text())
    if guard.get("read_own_pod_verified") is not True or guard.get("deadline") != deadline:
        raise ValueError("Independent lease deadline does not match the load manifest")
    if type(guard.get("pid")) is not int or guard["pid"] <= 0:
        raise ValueError("Invalid guard process")
    os.kill(guard["pid"], 0)
    if time.time() >= deadline:
        raise ValueError("Lease deadline has already elapsed")


def wait_for_start(plan, manifest_digest, output, journal, base):
    verify_guard(base / "guard-ready.json", plan["limits"]["shutdown_deadline_epoch"])
    journal.write("ready")
    trigger = output / "start.json"
    deadline = plan["limits"]["admission_deadline_epoch"]
    monotonic_deadline = time.monotonic() + deadline - time.time()
    while not trigger.exists():
        if time.time() >= deadline or time.monotonic() >= monotonic_deadline:
            raise TimeoutError("No start trigger before admission cutoff")
        time.sleep(0.05)
    if json.loads(trigger.read_text()) != {"run_id": plan["run_id"], "manifest_sha256": manifest_digest}:
        raise ValueError("Start trigger does not match the frozen manifest")


class Journal:
    """Exclusive creation prevents an uncertain request from being submitted again."""

    def __init__(self, path, run_id, monotonic=time.monotonic, wall=time.time):
        self.file = Path(path).open("x", encoding="utf-8")
        os.chmod(path, 0o600)
        self.run_id, self.monotonic, self.wall = run_id, monotonic, wall
        self.origin = monotonic()
        self.sequence = 0

    def write(self, event, **fields):
        record = {"version": 1, "run_id": self.run_id, "sequence": self.sequence,
                  "event": event, "worker_elapsed_seconds": self.monotonic() - self.origin,
                  "epoch": self.wall(), **fields}
        self.file.write(json.dumps(record, allow_nan=False) + "\n")
        self.file.flush()
        os.fsync(self.file.fileno())
        self.sequence += 1
        return record

    def close(self):
        self.file.close()


class OutputContractError(ValueError):
    """An incompatible output ends the window instead of spending on more work."""


def run_queue(plan, generate, output_dir, journal, *, wall=time.time, monotonic=time.monotonic,
              stop_requested=lambda: False):
    """Call an already warmed, persistent backend; never wait for export receipts.

    generate(request, path) must synchronously encode the complete artifact and
    return JSON metadata. A transport timeout is unresolved, not a verified
    technical failure, and ends the queue without retry. An external supervisor
    must bound a backend that hangs inside generate().
    """
    validate_manifest(plan)
    output_dir = Path(output_dir)
    limits = plan["limits"]
    failed_in_a_row = 0
    submitted = 0
    stop_reason = "request_limit"
    # Translate the wall deadline once so a backward wall-clock adjustment does
    # not extend admission. A forward adjustment can still shorten it.
    mono_cutoff = monotonic() + limits["admission_deadline_epoch"] - wall()
    window_start = monotonic()
    journal.write("window_started", request_count=len(plan["requests"]))
    for index, request in enumerate(plan["requests"]):
        if stop_requested():
            stop_reason = "controller_stop"
            break
        if wall() >= limits["admission_deadline_epoch"] or monotonic() >= mono_cutoff:
            stop_reason = "admission_deadline"
            break
        request_id = request["request_id"]
        path = output_dir / (request_id + ".mp4")
        if path.exists():
            raise FileExistsError("Refusing to overwrite an existing artifact")
        # This record is durable before invoking the backend. A journal ending
        # here denotes uncertain work, never permission for implicit resubmission.
        journal.write("request_started", request_id=request_id, ordinal=index,
                      requested_video_seconds=request["requested_video_seconds"],
                      prompt_sha256=request["prompt_sha256"], seed=request["seed"],
                      scene_id=request["scene_id"])
        submitted += 1
        started = monotonic()
        try:
            metadata = generate(request, path)
            if not path.is_file() or path.stat().st_size == 0:
                raise OutputContractError("Backend did not produce a nonempty artifact")
            artifact_hash = sha256(path)
        except (TimeoutError, ConnectionError):
            journal.write("request_unresolved", request_id=request_id,
                          processing_seconds=monotonic() - started)
            stop_reason = "uncertain_backend_outcome"
            break
        except Exception as exc:
            failed_in_a_row += 1
            journal.write("request_failed", request_id=request_id,
                          error_type=type(exc).__name__, processing_seconds=monotonic() - started)
            if isinstance(exc, OutputContractError) or failed_in_a_row >= 2:
                stop_reason = "output_contract" if isinstance(exc, OutputContractError) else "consecutive_failures"
                break
        else:
            failed_in_a_row = 0
            journal.write("artifact_ready", request_id=request_id, artifact=path.name,
                          artifact_sha256=artifact_hash, output_bytes=path.stat().st_size,
                          processing_seconds=monotonic() - started, runtime=metadata)
        if monotonic() - started > limits["request_bound_seconds"]:
            stop_reason = "request_bound_exceeded"
            break
    result = {"submitted": submitted, "not_submitted": len(plan["requests"]) - submitted,
              "stop_reason": stop_reason, "worker_window_seconds": monotonic() - window_start}
    journal.write("window_finished", **result)
    return result
