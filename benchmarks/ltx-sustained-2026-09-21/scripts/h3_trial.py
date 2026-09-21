"""Wait for our H100 service, submit one English-only P01 variant, download once."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from runpod_trial import save
from h3_adapters import ADAPTERS

ROOT = Path(__file__).resolve().parents[1]
LEASE = ROOT / "private" / "runpod-h100x4-p01-001"
OUTPUT = ROOT / "private" / "h100-p01-en"
RUN_ID = "P01_EN_RUNPOD_H100X4_5S_001"
BASE = "http://127.0.0.1:18421"
SOURCE_PROMPT_SHA256 = "493ef9be797d7fbf6407589f08a76830078ba2dfd0d8eaf990d2209852f0de6a"
ENGLISH = ("Any spoken words, dialogue, narration, or on-screen text must be in English only. "
           "Do not use Spanish, Russian, or other languages.")


def payload_from(original, recipe="base"):
    if hashlib.sha256(original.encode()).hexdigest() != SOURCE_PROMPT_SHA256:
        raise ValueError("Frozen source prompt mismatch")
    points = 50 if recipe == "base" else ADAPTERS[recipe]["sigma_points"]
    return {"model": "MiniMaxAI/MiniMax-H3", "prompt": original + "\n\n" + ENGLISH,
            "seconds": 5, "task": "t2va", "conditions": [],
            "target": {"short_edge": 768, "aspect_ratio": "16:9", "duration_seconds": 5.0},
            "quality": "lossless", "num_outputs_per_prompt": 1,
            "num_inference_steps": points, "flow_shift": 12.0, "audio_flow_shift": 3.0, "seed": 42}


def get_json(route, timeout=15):
    with urlopen(BASE + route, timeout=timeout) as response:
        return json.load(response)


def require_successful_warmup(log):
    """HTTP 200 health alone did not detect the observed failed warmup."""
    if "Synthetic server warmup failed" in log or re.search(r"server warmup req .*processing failed", log):
        raise RuntimeError("Startup warmup failed; refusing a user generation")
    if not re.search(r"server warmup req .*last=[0-9.]+s", log):
        raise RuntimeError("Successful warmup evidence missing; refusing a user generation")


def main():
    global LEASE, OUTPUT, RUN_ID
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recipe", choices=("base", *ADAPTERS), default="base")
    parser.add_argument("--attempt", type=int, choices=(1, 2), default=1,
                        help="Attempt 2 is the explicitly approved compatibility retry")
    parser.add_argument("--expected-pod-id", required=True)
    parser.add_argument("--ssh-host", required=True)
    parser.add_argument("--ssh-port", type=int, required=True)
    parser.add_argument("--service-pid", type=int)
    args = parser.parse_args()
    if args.recipe != "base":
        LEASE = ROOT / f"private/runpod-h100x4accel-p01-{args.attempt:03d}"
        suffix = "" if args.attempt == 1 else f"-{args.attempt:03d}"
        OUTPUT = ROOT / ("private/h100-" + args.recipe + "-p01-en" + suffix)
        RUN_ID = "P01_EN_RUNPOD_H100X4_" + args.recipe.upper() + f"_5S_{args.attempt:03d}"
    elif args.attempt != 1:
        parser.error("No new base-model attempt is authorized")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", args.ssh_host) or not 1 <= args.ssh_port <= 65535:
        parser.error("Invalid SSH address")
    if args.service_pid is not None and args.service_pid <= 1:
        parser.error("Invalid service PID")
    lease = json.loads((LEASE / "state.json").read_text())
    if lease.get("pod_id") != args.expected_pod_id or lease.get("status") != "created":
        raise RuntimeError("Expected allocated Pod required")
    expected_count = 1 if args.recipe == "light4" else 0
    if lease.get("generation_submissions") != expected_count:
        raise RuntimeError("A generation was already submitted or is uncertain; do not retry")
    if args.recipe == "light4" and lease.get("generation_run_id") != f"P01_EN_RUNPOD_H100X4_LARRY8_5S_{args.attempt:03d}":
        raise RuntimeError("The approved eight-step predecessor is missing")
    original = json.loads((ROOT / "private/fal-p01/payload.json").read_text())["prompt"]
    payload = payload_from(original, args.recipe)
    OUTPUT.mkdir(mode=0o700, exist_ok=False)
    save(OUTPUT / "payload.json", payload)
    state = {"run_id": RUN_ID, "lease_run_id": lease["run_id"], "status": "waiting_for_service",
             "source_prompt_sha256": SOURCE_PROMPT_SHA256,
             "prompt_sha256": hashlib.sha256(payload["prompt"].encode()).hexdigest(),
             "prompt_modified": True, "language_instruction": ENGLISH,
             "waiting_started_at": time.time(), "deadline": lease["deadline"]}
    state["recipe"] = args.recipe
    if args.recipe != "base":
        state["adapter"] = ADAPTERS[args.recipe]
    save(OUTPUT / "state.json", state)
    tunnel = subprocess.Popen(["ssh", "-N", "-L", "127.0.0.1:18421:127.0.0.1:30010",
        "-i", str(LEASE / "id_ed25519"), "-o", "IdentitiesOnly=yes",
        "-o", "StrictHostKeyChecking=accept-new", "-o", "UserKnownHostsFile=" + str(LEASE / "known_hosts"),
        "-o", "BatchMode=yes", "-o", "ExitOnForwardFailure=yes", "-o", "ServerAliveInterval=15",
        "-o", "ServerAliveCountMax=3", "-p", str(args.ssh_port), "root@" + args.ssh_host],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=open(OUTPUT / "tunnel.log", "ab"))
    try:
        while time.time() < lease["deadline"] - 300:
            if tunnel.poll() is not None:
                raise RuntimeError("SSH tunnel closed")
            try:
                with urlopen(BASE + "/health", timeout=5) as response:
                    ready = response.status == 200
                if ready:
                    break
            except (HTTPError, URLError, TimeoutError, ConnectionError):
                pass
            if args.service_pid is not None:
                probe = subprocess.run(["ssh", "-i", str(LEASE / "id_ed25519"),
                    "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", "-o", "StrictHostKeyChecking=accept-new",
                    "-o", "UserKnownHostsFile=" + str(LEASE / "known_hosts"),
                    "-p", str(args.ssh_port), "root@" + args.ssh_host,
                    "kill -0 " + str(args.service_pid)], capture_output=True, timeout=10)
                if probe.returncode == 1:
                    raise RuntimeError("Model service exited during startup; no generation submitted")
            print("Waiting for H3 readiness; no generation submitted", flush=True)
            time.sleep(10)
        else:
            raise TimeoutError("Setup consumed the rental window; no generation submitted")

        if args.recipe != "base":
            read_log = shlex.join(["python3", "-c", "from pathlib import Path;print(Path(" +
                repr("/root/benchmark/service-" + args.recipe + ".log") + ").read_text(errors='replace'))"])
            probe = subprocess.run(["ssh", "-i", str(LEASE / "id_ed25519"),
                "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", "-o", "StrictHostKeyChecking=accept-new",
                "-o", "UserKnownHostsFile=" + str(LEASE / "known_hosts"),
                "-p", str(args.ssh_port), "root@" + args.ssh_host, read_log],
                capture_output=True, text=True, timeout=20, check=True)
            require_successful_warmup(probe.stdout)

        # Durable write BEFORE POST: any uncertain transport outcome forbids resubmission.
        lease["generation_submissions"] = expected_count + 1
        lease["generation_run_id"] = RUN_ID
        save(LEASE / "state.json", lease)
        state.update(status="submission_uncertain", submitted_at=time.time())
        save(OUTPUT / "state.json", state)
        started = time.monotonic()
        request = Request(BASE + "/v1/videos", data=json.dumps(payload).encode(),
                          headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(request, timeout=60) as response:
            submitted = json.load(response)
        save(OUTPUT / "submission.json", submitted)
        job_id = submitted.get("id", "")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", job_id):
            raise RuntimeError("Unexpected job ID; do not resubmit")
        state.update(status="submitted", job_id=job_id,
                     submission_response_seconds=time.monotonic() - started)
        save(OUTPUT / "state.json", state)
        print(json.dumps({"status": "submitted", "job_id": job_id}), flush=True)
        while time.time() < lease["deadline"] - 60:
            result = get_json("/v1/videos/" + job_id)
            save(OUTPUT / "last-job.json", result)
            if result.get("status") == "failed":
                state.update(status="generation_failed", result=result)
                save(OUTPUT / "state.json", state)
                raise RuntimeError("Generation failed; response preserved")
            if result.get("status") == "completed":
                break
            time.sleep(1)
        else:
            raise TimeoutError("Generation did not complete before export cutoff")
        state["completion_observed_seconds"] = time.monotonic() - started
        with urlopen(BASE + "/v1/videos/" + job_id + "/content", timeout=45) as response:
            with open(OUTPUT / (RUN_ID + ".mp4"), "xb") as destination:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    destination.write(chunk)
        state.update(status="downloaded", end_to_end_seconds=time.monotonic() - started,
                     downloaded_at=time.time())
        save(OUTPUT / "state.json", state)
        print(json.dumps(state), flush=True)
    finally:
        tunnel.terminate()
        try:
            tunnel.wait(timeout=5)
        except subprocess.TimeoutExpired:
            tunnel.kill()
            tunnel.wait()


if __name__ == "__main__":
    main()
