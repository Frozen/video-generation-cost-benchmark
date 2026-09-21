"""A timed, continuously backlogged queue with explicit bounded retry attempts."""

import time
from pathlib import Path

from load_window import OutputContractError, sha256, validate_manifest


def validate_sustained(plan):
    validate_manifest(plan)
    if plan["limits"].get("target_queue_seconds") != 3600:
        raise ValueError("The registered measurement window is one hour")
    if len({r["scene_id"] for r in plan["requests"]}) != 20:
        raise ValueError("Twenty preregistered scenes are required")
    retries = plan.get("retry_requests", [])
    originals = {r["request_id"]: r for r in plan["requests"]}
    if len(retries) != len(originals):
        raise ValueError("One predeclared retry opportunity per original is required")
    for retry in retries:
        original = originals[retry["retry_of"]]
        expected = dict(original, request_id=original["request_id"] + "_retry1", retry_of=original["request_id"])
        if retry != expected:
            raise ValueError("A retry must retain the original input and have its own attempt ID")
    return plan


def run_queue(plan, generate, output_dir, journal, *, wall=time.time, monotonic=time.monotonic,
              stop_requested=lambda: False):
    validate_sustained(plan)
    output_dir = Path(output_dir)
    limits = plan["limits"]
    started = monotonic()
    mono_cutoff = started + limits["admission_deadline_epoch"] - wall()
    target = limits["target_queue_seconds"]
    retries = {r["retry_of"]: r for r in plan["retry_requests"]}
    primary = iter(plan["requests"])
    pending_retry = None
    submitted = successful = failed = unresolved = retried = consecutive_failures = 0
    stop_reason = "input_pool_exhausted"
    journal.write("window_started", target_queue_seconds=target,
                  input_pool_size=len(plan["requests"]), batch_size=1, concurrency=1)
    while True:
        if monotonic() - started >= target:
            stop_reason = "target_duration_reached"
            break
        if stop_requested():
            stop_reason = "controller_stop"
            break
        if wall() >= limits["admission_deadline_epoch"] or monotonic() >= mono_cutoff:
            stop_reason = "admission_deadline"
            break
        if pending_retry is not None:
            request, pending_retry = pending_retry, None
            retried += 1
        else:
            request = next(primary, None)
            if request is None:
                break
        attempt_id = request["request_id"]
        path = output_dir / (attempt_id + ".mp4")
        if path.exists():
            raise FileExistsError("Refusing to overwrite an existing attempt")
        journal.write("request_started", request_id=attempt_id, ordinal=submitted,
                      retry_of=request.get("retry_of"), scene_id=request["scene_id"],
                      seed=request["seed"], prompt_sha256=request["prompt_sha256"],
                      requested_video_seconds=request["requested_video_seconds"])
        submitted += 1
        request_start = monotonic()
        try:
            metadata = generate(request, path)
            if not path.is_file() or path.stat().st_size == 0:
                raise OutputContractError("Generation did not produce a nonempty artifact")
            artifact_hash = sha256(path)
        except (TimeoutError, ConnectionError) as exc:
            unresolved += 1
            journal.write("request_unresolved", request_id=attempt_id,
                          retry_of=request.get("retry_of"), error_type=type(exc).__name__,
                          processing_seconds=monotonic() - request_start)
            stop_reason = "uncertain_backend_outcome"
            break
        except Exception as exc:
            failed += 1
            consecutive_failures += 1
            fatal = isinstance(exc, OutputContractError) or type(exc).__name__ in ("OutOfMemoryError", "CudaError")
            retryable = not fatal and "retry_of" not in request and consecutive_failures < 2
            journal.write("request_failed", request_id=attempt_id,
                          retry_of=request.get("retry_of"), error_type=type(exc).__name__,
                          processing_seconds=monotonic() - request_start,
                          retry_scheduled=retryable)
            if fatal or consecutive_failures >= 2:
                stop_reason = "fatal_or_consecutive_failures"
                break
            if retryable:
                pending_retry = retries[attempt_id]
        else:
            successful += 1
            consecutive_failures = 0
            journal.write("artifact_ready", request_id=attempt_id,
                          retry_of=request.get("retry_of"), artifact=path.name,
                          artifact_sha256=artifact_hash, output_bytes=path.stat().st_size,
                          processing_seconds=monotonic() - request_start, runtime=metadata)
        if monotonic() - request_start > limits["request_bound_seconds"]:
            stop_reason = "request_bound_exceeded"
            break
    result = {"submitted": submitted, "successful": successful, "failed": failed,
              "unresolved": unresolved, "retry_attempts": retried,
              "stop_reason": stop_reason, "worker_window_seconds": monotonic() - started,
              "target_queue_seconds": target,
              "unstarted_primary_requests": len(plan["requests"]) - (submitted - retried)}
    journal.write("window_finished", **result)
    return result
