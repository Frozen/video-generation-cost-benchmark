"""Twenty preregistered API pairs, with durable claims and no hidden retries."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from urllib.parse import urlparse

from budget import transact
from check_access import load_keys, check
from fal_reference import save, curl as download
import fal_reference

ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "FAL_SUSTAINED_PAIRED_001"
ENDPOINT = "minimax/h3-max-turbo/text-to-video"
fal_reference.ENDPOINT = ENDPOINT
PRIVATE = ROOT / "private/fal-sustained-paired-001"


def request(url, key, folder, label, payload=None):
    if not fal_reference.allowed_queue(url):
        raise ValueError("Unexpected authenticated destination")
    config = "url = " + json.dumps(url) + "\nheader = " + json.dumps("Authorization: Key " + key) + "\n"
    command = ["curl", "-q", "--config", "-", "--silent", "--show-error", "--proto", "=https",
               "--max-redirs", "0", "--connect-timeout", "10", "--max-time", "30",
               "--max-filesize", "4194304", "--output", str(folder / (label + ".json")),
               "--dump-header", str(folder / (label + "-headers.txt")), "--write-out", "%{http_code}"]
    if payload is not None:
        command += ["--request", "POST", "--header", "Content-Type: application/json",
                    "--header", "X-Fal-No-Retry: 1", "--header", "X-Fal-Request-Timeout: 120",
                    "--data-binary", "@" + str(payload)]
    reply = subprocess.run(command, input=config, text=True, capture_output=True, timeout=35)
    if reply.returncode:
        raise ConnectionError("Uncertain transport outcome; never repeat a submission")
    code = int(reply.stdout)
    try:
        body = json.loads((folder / (label + ".json")).read_text())
    except ValueError:
        body = {}
    return code, body


def payload_for(item, settings):
    fields = ("duration", "resolution", "aspect_ratio", "prompt_expansion_mode", "enable_safety_checker", "sync_mode")
    result = {k: settings[k] for k in fields}
    result.update(prompt=item["prompt"], seed=item["seed"])
    if hashlib.sha256(item["prompt"].encode()).hexdigest() != item["prompt_sha256"]:
        raise ValueError("Frozen prompt hash differs")
    return result


def collect(folder, key, monotonic_start=None):
    state = json.loads((folder / "state.json").read_text())
    if state.get("submission_http") in (401, 402, 403):
        raise RuntimeError("Original authorization/payment rejection remains unresolved")
    if state["status"] in ("download_complete", "provider_failed", "rejected"):
        return state
    queue = state.get("queue")
    if not queue:
        raise RuntimeError("Submission has no confirmed request ID; do not replay")
    deadline = time.monotonic() + 1200
    while time.monotonic() < deadline:
        code, status = request(queue["status_url"], key, folder, "status")
        if code not in (200, 202):
            raise RuntimeError("Queue observation failed; resume the same request")
        state.setdefault("events", []).append({"epoch": time.time(), "status": status.get("status")})
        save(folder / "state.json", state)
        if status.get("status") == "COMPLETED":
            state.setdefault("completion_observed_epoch", time.time())
            state.setdefault("submit_to_completion_seconds", (
                time.monotonic() - monotonic_start if monotonic_start is not None
                else time.time() - state["submitted_epoch"]))
            state["timing_clock"] = "monotonic" if monotonic_start is not None else "wall_clock_resumed_collection"
            save(folder / "state.json", state)
            if status.get("error"):
                state["status"] = "provider_failed"
                save(folder / "state.json", state)
                return state
            code, response = request(queue["response_url"], key, folder, "response")
            if code == 422 or (code == 200 and response.get("error")):
                state.update(status="provider_failed", response_http=code)
                save(folder / "state.json", state)
                return state
            if code != 200:
                raise RuntimeError("Result retrieval failed; do not submit again")
            url = response["video"]["url"]
            parsed = urlparse(url)
            if parsed.scheme != "https" or not (parsed.hostname or "").endswith(".fal.media"):
                raise ValueError("Unexpected artifact destination")
            download(url, output=folder / "video.mp4.part")
            os.replace(folder / "video.mp4.part", folder / "video.mp4")
            state["submit_to_download_seconds"] = (time.monotonic() - monotonic_start
                if monotonic_start is not None else time.time() - state["submitted_epoch"])
            state["video_sha256"] = hashlib.sha256((folder / "video.mp4").read_bytes()).hexdigest()
            state["video_bytes"] = (folder / "video.mp4").stat().st_size
            probe = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_streams",
                    "-show_format", "-of", "json", str(folder / "video.mp4")], timeout=20))
            save(folder / "probe.json", probe)
            decoded = subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(folder / "video.mp4"),
                        "-f", "null", "-"], capture_output=True, timeout=30)
            state["decode_verified"] = decoded.returncode == 0
            state["provider_dit_seconds"] = response.get("timings", {}).get("inference")
            state["status"] = "download_complete"
            save(folder / "state.json", state)
            return state
        if status.get("status") not in ("IN_QUEUE", "IN_PROGRESS"):
            raise RuntimeError("Unknown queue state; retain original request")
        time.sleep(2)
    raise TimeoutError("Poll original request again; never create a replacement")


def attempt(item, settings, key, retry=False):
    attempt_id = item["request_id"] + ("_retry1" if retry else "")
    folder = PRIVATE / attempt_id
    expected = payload_for(item, settings)
    if folder.exists():
        if json.loads((folder / "payload.json").read_text()) != expected:
            raise ValueError("Input changed during resume")
        return collect(folder, key)
    folder.mkdir(mode=0o700)
    save(folder / "payload.json", expected)
    state = {"attempt_id": attempt_id, "pair_id": item["request_id"], "scene_id": item["scene_id"],
             "seed": item["seed"], "prompt_sha256": item["prompt_sha256"],
             "retry_of": item["request_id"] if retry else None, "endpoint": ENDPOINT,
             "status": "submission_started_do_not_replay", "submitted_epoch": time.time(),
             "quoted_usd": "0.10", "actual_charge_usd": None}
    save(folder / "state.json", state)
    start = time.monotonic()
    code, reply = request("https://queue.fal.run/" + ENDPOINT, key, folder, "submit", folder / "payload.json")
    if code in (400, 401, 402, 403, 422):
        state.update(status="rejected", submission_http=code)
        save(folder / "state.json", state)
        if code in (401, 402, 403):
            raise RuntimeError("Provider authorization or payment rejection; batch stopped")
        return state
    if code not in (200, 201, 202) or not reply.get("request_id"):
        raise RuntimeError("No confirmed accepted request; do not replay")
    if not all(fal_reference.allowed_queue(reply.get(k, "")) for k in ("status_url", "response_url")):
        raise ValueError("Unexpected queue URLs; preserve original acceptance")
    state.update(status="submitted", queue=reply)
    save(folder / "state.json", state)
    return collect(folder, key, start)


def run(env_file):
    proposal = json.loads((ROOT / "ltx-sustained-proposal.json").read_text())
    settings, items = proposal["fal"], proposal["fal_reference_requests"]
    if len(items) != 20 or len({r["scene_id"] for r in items}) != 20 or settings["reservation_usd"] != "2.20":
        raise ValueError("Unexpected preregistered pair set")
    ledger = json.loads((ROOT / "private/ledger.json").read_text())
    entry = ledger["entries"].get(RUN_ID, {})
    if ledger["blocked"] or entry.get("status") != "reserved" or entry.get("reserved_cents") != 220:
        raise ValueError("The explicit batch reservation must exist before submission")
    key = load_keys(env_file)["fal"]
    pricing = check("fal_pricing", key, endpoint=ENDPOINT)
    if pricing.get("status") != "ok" or float(pricing["pricing"]["unit_price"]) != 0.0125:
        raise ValueError("Authentication or base billing-unit quote changed")
    PRIVATE.mkdir(mode=0o700, exist_ok=True)
    save(PRIVATE / "pricing-check.json", pricing)
    # An OS lock permits safe polling/resume but excludes concurrent submissions.
    import fcntl
    with (PRIVATE / "controller.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        retries = 0
        for item in items:
            state = attempt(item, settings, key)
            if state["status"] == "provider_failed" and retries < 2:
                retries += 1
                state = attempt(item, settings, key, retry=True)
            print(json.dumps({k: state.get(k) for k in ("attempt_id", "status", "submit_to_completion_seconds",
                             "submit_to_download_seconds", "decode_verified")}), flush=True)


if __name__ == "__main__":
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    run(parser.parse_args().env_file)
