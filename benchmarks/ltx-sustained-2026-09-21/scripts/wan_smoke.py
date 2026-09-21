"""Bound one native Wan diagnostic lease; MCP performs its only allocation."""

import argparse
import base64
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import secrets
import shlex
import subprocess
import sys
import time

import ltx_trial as lease
from budget import transact
from load_window import sha256
from runpod_trial import save

ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "wan-smoke-plan.json"
RUN_ID = "P01_EN_RUNPOD_H100_WAN22_5S_001"
DIRECTORY = ROOT / "private/wan-h100-p01-001"


def configure_lease():
    lease.ROOT, lease.LEASE, lease.STATE = ROOT, DIRECTORY, DIRECTORY / "state.json"
    lease.RUN_ID, lease.HOURLY = RUN_ID, 3.49


def validate_plan(plan):
    if plan["run_id"] != RUN_ID or plan["request"]["audio_required"] is not False:
        raise ValueError("This controller only runs the named video-only diagnostic")
    if (plan["gpu_count"], plan["gpu_id"], plan["max_lease_seconds"], plan["reservation_usd"]) != (
            1, "NVIDIA H100 80GB HBM3", 1800, "2.00"):
        raise ValueError("Unexpected hardware or spending bound")
    r = plan["request"]
    if (r["width"], r["height"], r["frames"], r["fps"], r["sampling_steps"], r["seed"]) != (
            1280, 720, 81, 16, 40, 42):
        raise ValueError("Unexpected native generation profile")
    if plan["technical_warmup"]["seed"] == r["seed"]:
        raise ValueError("Technical warmup must not reuse measured generation inputs")
    # Include two minutes beyond the nominal deadline for shutdown controls.
    seconds = Decimal(plan["max_lease_seconds"] + 120)
    upper = seconds * (Decimal(plan["compute_hourly_usd"]) / 3600
                       + Decimal(plan["disk_gb"]) * Decimal(plan["disk_monthly_usd_per_gb"]) / (30 * 86400))
    if upper > Decimal(plan["reservation_usd"]):
        raise ValueError("Reserved amount does not cover the declared lease and shutdown allowance")
    return plan


def arm(env_file):
    plan = validate_plan(json.loads(PLAN_PATH.read_text()))
    archive = ROOT / "private/wan-pinned-source.tar.gz"
    if sha256(archive) != plan["source_archive_sha256"]:
        raise ValueError("Pinned source archive mismatch")
    if sha256(ROOT / "wan-runtime-requirements.txt") != plan["runtime"]["requirements_sha256"]:
        raise ValueError("Runtime lock mismatch")
    request = json.loads((ROOT / "private/sustained-preparation/p01-en.json").read_text())
    if hashlib.sha256(request["prompt"].encode()).hexdigest() != plan["request"]["prompt_sha256"]:
        raise ValueError("Frozen prompt mismatch")
    if not lease.load_keys(env_file)["runpod"]:
        raise ValueError("Runpod key required by the independent local guard")
    DIRECTORY.mkdir(mode=0o700)
    transact(ROOT / "private/ledger.json", "reserve", RUN_ID, plan["reservation_usd"], "generation")
    now = time.time()
    state = {"run_id": RUN_ID, "name": "wan22-p01-" + secrets.token_hex(6), "status": "armed",
             "started_at": now, "deadline": now + plan["max_lease_seconds"],
             "generation_submissions": 0, "plan_sha256": sha256(PLAN_PATH),
             "reservation_usd": plan["reservation_usd"], "image": plan["image"]}
    save(lease.STATE, state)
    save(DIRECTORY / "request.json", {"prompt": request["prompt"], "seed": plan["request"]["seed"]})
    save(DIRECTORY / "lease.json", {"run_id": RUN_ID, "deadline": state["deadline"], "plan_sha256": state["plan_sha256"]})
    key = DIRECTORY / "id_ed25519"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True)
    with (DIRECTORY / "guard.log").open("ab") as output:
        process = subprocess.Popen(["/usr/bin/caffeinate", "-ims", sys.executable, str(Path(__file__).resolve()),
                                    "guard", "--env-file", str(env_file)], stdin=subprocess.DEVNULL,
                                   stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
    for _ in range(50):
        if (DIRECTORY / "guard-ready.json").exists() and process.poll() is None:
            break
        time.sleep(0.1)
    else:
        raise RuntimeError("Local deadline guard not ready; do not allocate")
    remote = base64.b64encode((ROOT / "scripts/runpod_deadline.py").read_bytes()).decode()
    code = "import base64;exec(compile(base64.b64decode(" + repr(remote) + "),'<guard>','exec'))"
    payload = {"name": state["name"], "image": plan["image"], "args": "python3 -u -c " + shlex.quote(code),
               "disk": plan["disk_gb"], "cloud": "SECURE", "dataCenterIds": [plan["region"]],
               "gpu": {"id": plan["gpu_id"], "count": 1, "minRamPerGpu": plan["min_ram_per_gpu_gb"],
                       "minCudaVersion": plan["min_cuda_version"]}, "ports": ["22/tcp"],
               "startSsh": False, "startJupyter": False,
               "env": {"PUBLIC_KEY": key.with_suffix(".pub").read_text().strip(),
                       "BENCHMARK_DEADLINE": str(state["deadline"]), "BENCHMARK_NAME": state["name"]}}
    save(DIRECTORY / "create-request.json", payload)
    state["status"] = "create_uncertain"
    save(lease.STATE, state)
    print(json.dumps({"run_id": RUN_ID, "request_file": str(DIRECTORY / "create-request.json"),
                      "deadline": state["deadline"], "reservation_usd": plan["reservation_usd"]}))


def spawn(connection, action):
    python = "python3" if action == "prepare" else "/root/benchmark/wan-env/bin/python"
    command = [python, "-u", "/root/benchmark/wan_smoke_worker.py", action]
    code = ("import subprocess;from pathlib import Path;"
            "p=subprocess.Popen(" + repr(command) + ",stdin=subprocess.DEVNULL,"
            "stdout=open('/root/benchmark/" + action + ".log','ab'),stderr=subprocess.STDOUT,start_new_session=True);"
            "Path('/root/benchmark/" + action + ".pid').write_text(str(p.pid));print(p.pid)")
    return int(lease.remote(connection, code).strip())


def wait_phase(connection, action, expected, cutoff):
    # Keep observing the original PID after a transient SSH/polling failure.
    while time.time() < cutoff:
        try:
            return lease.wait_phase(connection, action, expected, cutoff)
        except subprocess.TimeoutExpired:
            time.sleep(2)
        except RuntimeError as exc:
            if str(exc).startswith("Remote command failed"):
                time.sleep(2)
            else:
                raise
    raise TimeoutError("Original worker did not reach its phase before the cutoff")


def run(env_file):
    plan = validate_plan(json.loads(PLAN_PATH.read_text()))
    state = lease.read_state()
    if state["status"] != "created" or state.get("prepare_started_at"):
        raise ValueError("Use the existing process/journal after any interruption")
    if state["plan_sha256"] != sha256(PLAN_PATH):
        raise ValueError("Plan changed after the lease was armed")
    connection = None
    while time.time() < state["deadline"] - plan["minimum_after_prepare_seconds"]:
        pod = lease.observe(env_file)
        if Decimal(str(pod["cost"])) > Decimal(plan["max_observed_compute_hourly_usd"]):
            raise ValueError("Actual rental quote exceeds the declared Wan limit")
        candidate = (pod.get("ssh") or {}).get("direct")
        if candidate:
            try:
                guard = json.loads(lease.remote(candidate, "from pathlib import Path;print(Path('/root/benchmark/guard-ready.json').read_text())"))
                if guard.get("read_own_pod_verified") and guard["deadline"] == state["deadline"]:
                    connection = candidate
                    break
            except (RuntimeError, ValueError, subprocess.TimeoutExpired):
                pass
        print("Waiting for SSH and the verified remote deadline", flush=True)
        time.sleep(5)
    if connection is None:
        raise TimeoutError("Startup consumed the bounded preparation allowance")
    save(DIRECTORY / "connection.json", connection)
    lease.transfer(connection, [PLAN_PATH, ROOT / "wan-baseline-candidate.json", ROOT / "wan-runtime-requirements.txt",
        ROOT / "private/wan-pinned-source.tar.gz", ROOT / "scripts/wan_smoke_worker.py", ROOT / "scripts/load_window.py",
        DIRECTORY / "request.json", DIRECTORY / "lease.json"], True)
    lease.remote(connection, "import subprocess;subprocess.Popen(['nvidia-smi','--query-gpu=timestamp,index,name,memory.used,utilization.gpu,power.draw','--format=csv','--loop=1','--filename=/root/benchmark/gpu-samples.csv'],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)")
    state["prepare_started_at"] = time.time()
    save(lease.STATE, state)
    state["prepare_pid"] = spawn(connection, "prepare")
    save(lease.STATE, state)
    wait_phase(connection, "prepare", "ready", state["deadline"] - plan["minimum_after_prepare_seconds"])
    lease.transfer(connection, ["prepare-status.json", "dependencies.txt", "weights.json"], False)
    state["generate_spawn_claimed_at"] = time.time()
    save(lease.STATE, state)
    state["generate_pid"] = spawn(connection, "generate")
    save(lease.STATE, state)
    cutoff = state["deadline"] - plan["request_bound_seconds"] - plan["export_reserve_seconds"]
    wait_phase(connection, "generate", "ready", cutoff)
    state.update(generation_submissions=1, submitted_at=time.time())
    save(lease.STATE, state)
    submitted = time.monotonic()
    trigger = json.dumps({"run_id": RUN_ID, "plan_sha256": state["plan_sha256"]})
    code = ("import os,sys;from pathlib import Path;b=Path('/root/benchmark');p=b/'start.pending';"
            "f=p.open('x');f.write(sys.stdin.read());f.flush();os.fsync(f.fileno());f.close();os.link(p,b/'start.json')")
    try:
        lease.remote(connection, code, trigger)
    except (RuntimeError, subprocess.TimeoutExpired):
        print("Start response uncertain; observing the original claim without resubmission", flush=True)
    wait_phase(connection, "generate", "completed", state["deadline"] - plan["export_reserve_seconds"])
    lease.transfer(connection, [RUN_ID + ".mp4", "generation-status.json"], False)
    state.update(end_to_end_seconds=time.monotonic() - submitted, downloaded_at=time.time())
    save(lease.STATE, state)
    lease.transfer(connection, ["warmup.json", "technical-warmup.mp4", "gpu-samples.csv", "prepare.log", "generate.log"], False)
    video = DIRECTORY / (RUN_ID + ".mp4")
    result = json.loads((DIRECTORY / "generation-status.json").read_text())
    if sha256(video) != result["output_sha256"]:
        raise ValueError("Export hash mismatch")
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-f", "null", "-"], check=True, timeout=60)
    state["decode_verified"] = True
    save(lease.STATE, state)
    lease.close(env_file)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "arm", "guard", "attach", "run", "close", "status"))
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--pod-id")
    args = parser.parse_args()
    configure_lease()
    if args.action == "check":
        validate_plan(json.loads(PLAN_PATH.read_text()))
        print("Wan request and lease bound validated; no allocation or generation performed")
    elif args.action == "attach":
        lease.attach(args.env_file, args.pod_id)
    elif args.action in ("guard", "close"):
        getattr(lease, args.action)(args.env_file)
    elif args.action == "status":
        print(json.dumps(lease.observe(args.env_file)))
    else:
        globals()[args.action](args.env_file)
