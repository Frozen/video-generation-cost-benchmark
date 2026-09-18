"""One explicit bounded rental. No inference submission or automatic retry."""

import argparse
import base64
import json
import os
from pathlib import Path
import secrets
import shlex
import subprocess
import sys
import time

from budget import transact
from check_access import load_keys
from runpod_deadline import terminate

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "private" / "runpod-p01"
STATE = PRIVATE / "state.json"
RUN_ID = "P01_RUNPOD_B300_5S_001"
ATTEMPT = 1
HARDWARE = "b300"
REGION = "EUR-IS-1"
PROFILES = {
    "b300": {"gpu_id": "NVIDIA B300 SXM6 AC", "count": 1, "ram_per_gpu": 384,
             "seconds": 7200, "reservation": "18.00", "hourly": "7.89",
             "regions": ("EUR-IS-1",)},
    "h100x4": {"gpu_id": "NVIDIA H100 80GB HBM3", "count": 4, "ram_per_gpu": 96,
               "seconds": 3600, "reservation": "16.00", "hourly": "13.96",
               "regions": ("AP-IN-1", "EUR-IS-3", "CA-MTL-1")},
    "h100x4accel": {"gpu_id": "NVIDIA H100 80GB HBM3", "count": 4, "ram_per_gpu": 96,
                    "seconds": 1440, "reservation": "6.00", "hourly": "13.96",
                    "regions": ("AP-IN-1",)},
}
IMAGE = "lmsysorg/sglang@sha256:6bcaa47db52f78ce0d67863b8b2431221b79bc23204a80cad757fa819d00e921"
MODEL_REVISION = "42ed227ee7df40d41602854ae760620d6eb651fe"
SOURCE_REVISION = "408d2334c34d387a36a26398dff9a8f004328344"


def configure_attempt(attempt, hardware="b300", region="EUR-IS-1"):
    """Select an explicit journal; never erase or implicitly retry an attempt."""
    if type(attempt) is not int or not 1 <= attempt <= 999:
        raise ValueError("attempt must be an integer from 1 to 999")
    if hardware not in PROFILES or region not in PROFILES[hardware]["regions"]:
        raise ValueError("hardware/region is outside the reviewed profiles")
    global PRIVATE, STATE, RUN_ID, ATTEMPT, HARDWARE, REGION
    ATTEMPT = attempt
    HARDWARE, REGION = hardware, region
    suffix = "" if attempt == 1 else f"-{attempt:03d}"
    directory = "runpod-p01" + suffix if hardware == "b300" else f"runpod-{hardware}-p01-{attempt:03d}"
    PRIVATE = ROOT / "private" / directory
    STATE = PRIVATE / "state.json"
    RUN_ID = f"P01_RUNPOD_{hardware.upper()}_5S_{attempt:03d}"


def save(path, data):
    temporary = path.with_suffix(".tmp")
    with open(temporary, "w", encoding="utf-8") as out:
        json.dump(data, out, indent=2)
        out.write("\n")
        out.flush()
        os.fsync(out.fileno())
    temporary.chmod(0o600)
    os.replace(temporary, path)


def api(method, route, key, payload=None):
    config = "header = " + json.dumps("Authorization: Bearer " + key) + "\n"
    config += 'header = "Content-Type: application/json"\n'
    if payload is not None:
        config += "data = " + json.dumps(json.dumps(payload)) + "\n"
    proc = subprocess.run(["curl", "-q", "--config", "-", "--silent", "--show-error",
        "--proto", "=https", "--max-redirs", "0", "--connect-timeout", "15",
        "--max-time", "90", "--request", method, "--write-out", "\n%{http_code}",
        "https://api.runpod.io/v2/" + route], input=config, text=True,
        capture_output=True, timeout=95)
    if proc.returncode:
        raise RuntimeError("Runpod transport error; do not repeat create")
    body, code = proc.stdout.rsplit("\n", 1)
    return int(code), json.loads(body) if body.strip() else {}


def guard(env_file):
    key = load_keys(env_file)["runpod"]
    save(PRIVATE / "guard-ready.json", {"pid": os.getpid(), "armed_at": time.time()})
    while True:
        state = json.loads(STATE.read_text())
        if state["status"] in ("rejected", "terminated"):
            return
        if time.time() >= state["deadline"] or (PRIVATE / "terminate-now").exists():
            pod_id = state.get("pod_id")
            if pod_id:
                try:
                    if terminate(pod_id, state["name"], key):
                        save(PRIVATE / "termination.json", {"verified_absent_at": time.time(),
                                                              "source": "local_guard"})
                        return
                except Exception as exc:
                    print("Shutdown retry: " + type(exc).__name__, flush=True)
            elif state["status"] == "create_uncertain":
                print("Create outcome uncertain; requires reconciliation", flush=True)
        time.sleep(10)


def launch(env_file):
    key = load_keys(env_file)["runpod"]
    if not key:
        raise ValueError("Runpod credential missing")
    PRIVATE.mkdir(mode=0o700, exist_ok=False)
    # The reservation is an admission bound, never represented as actual spend.
    profile = PROFILES[HARDWARE]
    transact(ROOT / "private" / "ledger.json", "reserve", RUN_ID, profile["reservation"], "generation")
    now = time.time()
    state = {"run_id": RUN_ID, "name": "h3-" + HARDWARE + "-p01-" + secrets.token_hex(6),
             "status": "armed", "started_at": now, "deadline": now + profile["seconds"],
             "reservation_usd": profile["reservation"], "image": IMAGE,
             "model_revision": MODEL_REVISION, "source_revision": SOURCE_REVISION,
             "region": REGION, "hardware": HARDWARE,
             "catalog_compute_hourly_usd": profile["hourly"], "generation_submissions": 0}
    save(STATE, state)
    ssh_key = PRIVATE / "id_ed25519"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(ssh_key)], check=True)
    public_key = ssh_key.with_suffix(".pub").read_text().strip()
    with open(PRIVATE / "guard.log", "ab") as out:
        subprocess.Popen(["/usr/bin/caffeinate", "-ims", sys.executable, str(Path(__file__).resolve()),
                          "guard", "--env-file", str(env_file), "--attempt", str(ATTEMPT),
                          "--hardware", HARDWARE, "--region", REGION],
                         stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
                         start_new_session=True, close_fds=True)
    for _ in range(50):
        if (PRIVATE / "guard-ready.json").exists():
            break
        time.sleep(0.1)
    else:
        raise RuntimeError("Local shutdown guard did not arm; no create submitted")
    remote = base64.b64encode((ROOT / "scripts" / "runpod_deadline.py").read_bytes()).decode()
    code = "import base64;exec(compile(base64.b64decode(" + repr(remote) + "),'<benchmark-guard>','exec'))"
    payload = {"name": state["name"], "image": IMAGE,
        "args": "python3 -u -c " + shlex.quote(code),
        "disk": 300, "cloud": "SECURE", "dataCenterIds": [REGION],
        "gpu": {"id": profile["gpu_id"], "count": profile["count"],
                "minRamPerGpu": profile["ram_per_gpu"], "allowedCudaVersions": ["13.0"]},
        "ports": ["22/tcp"], "startSsh": False, "startJupyter": False,
        "env": {"PUBLIC_KEY": public_key, "BENCHMARK_DEADLINE": str(state["deadline"]),
                "BENCHMARK_NAME": state["name"]}}
    public_payload = dict(payload, env={k: ("[REDACTED]" if "KEY" in k else v)
                                       for k, v in payload["env"].items()})
    save(PRIVATE / "create-request-redacted.json", public_payload)
    state["status"] = "create_uncertain"
    save(STATE, state)
    code, reply = api("POST", "pods", key, payload)
    # Never persist a credential echoed by a provider response.
    reply = json.loads(json.dumps(reply).replace(key, "[REDACTED]"))
    save(PRIVATE / "create-response.json", {"http": code, "body": reply})
    if code not in (200, 201, 202):
        # A server-side failure may have allocated a resource: retain the guard.
        if 400 <= code < 500:
            state["status"] = "rejected"
            save(STATE, state)
        print(json.dumps({"status": state["status"], "http": code, "response": reply}))
        return 2
    if not isinstance(reply, dict) or not reply.get("id") or reply.get("name") != state["name"]:
        raise RuntimeError("Unexpected create response; reconcile before any retry")
    state.update(status="created", pod_id=reply["id"], created_response_at=time.time())
    save(STATE, state)
    print(json.dumps({"status": "created", "pod_id": state["pod_id"], "deadline": state["deadline"]}))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("launch", "guard", "status", "terminate"))
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--attempt", type=int, default=1,
                        help="Explicit authorized attempt number; existing journals are refused")
    parser.add_argument("--hardware", choices=tuple(PROFILES), default="b300")
    parser.add_argument("--region", default="EUR-IS-1")
    args = parser.parse_args()
    configure_attempt(args.attempt, args.hardware, args.region)
    if args.action == "launch":
        return launch(args.env_file)
    if args.action == "guard":
        return guard(args.env_file)
    state = json.loads(STATE.read_text())
    key = load_keys(args.env_file)["runpod"]
    if args.action == "terminate":
        if terminate(state["pod_id"], state["name"], key):
            state.update(status="terminated", verified_absent_at=time.time())
            save(STATE, state)
            print("Pod termination verified")
            return 0
        return 2
    code, pod = api("GET", "pods/" + state["pod_id"], key)
    pod = json.loads(json.dumps(pod).replace(key, "[REDACTED]"))
    if isinstance(pod, dict):
        pod.pop("env", None)
    save(PRIVATE / "last-pod.json", {"http": code, "body": pod, "at": time.time()})
    print(json.dumps({"http": code, "pod": pod}, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
