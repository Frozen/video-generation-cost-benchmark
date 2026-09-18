"""Bound one LTX lease and request. MCP performs the sole create after arm."""

import argparse
import base64
import hashlib
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
from h3_trial import payload_from
from ltx_config import HF_ALIASES, HOURLY, IMAGE, MAX_LEASE_SECONDS, REGION, RESERVATION, RUN_ID, SOURCE, validate_prompt
from runpod_deadline import terminate
from runpod_trial import api, save

ROOT = Path(__file__).resolve().parents[1]
LEASE = ROOT / "private/ltx-h100-p01-001"
STATE = LEASE / "state.json"


def read_state():
    return json.loads(STATE.read_text())


def arm(env_file):
    if LEASE.exists():
        raise ValueError("Existing lease journal; no implicit retry")
    if not load_keys(env_file, HF_ALIASES)["hf"] or not load_keys(env_file)["runpod"]:
        raise ValueError("Required credentials missing")
    archive = ROOT / "private/ltx-source.tar.gz"
    if not archive.is_file():
        raise ValueError("Pinned source archive missing")
    original = json.loads((ROOT / "private/fal-p01/payload.json").read_text())["prompt"]
    prompt = validate_prompt(payload_from(original)["prompt"])
    LEASE.mkdir(mode=0o700)
    transact(ROOT / "private/ledger.json", "reserve", RUN_ID, RESERVATION, "generation")
    now = time.time()
    state = {"run_id": RUN_ID, "name": "ltx25-p01-" + secrets.token_hex(6), "status": "armed",
             "started_at": now, "deadline": now + MAX_LEASE_SECONDS, "generation_submissions": 0,
             "reservation_usd": RESERVATION, "image": IMAGE, "source_revision": SOURCE,
             "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest()}
    save(STATE, state)
    save(LEASE / "request.json", {"prompt": prompt, "seed": 42})
    ssh_key = LEASE / "id_ed25519"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(ssh_key)], check=True)
    with (LEASE / "guard.log").open("ab") as out:
        p = subprocess.Popen(["/usr/bin/caffeinate", "-ims", sys.executable, str(Path(__file__).resolve()),
                              "guard", "--env-file", str(env_file)], stdin=subprocess.DEVNULL,
                             stdout=out, stderr=subprocess.STDOUT, start_new_session=True)
    for _ in range(50):
        if (LEASE / "guard-ready.json").exists() and p.poll() is None:
            break
        time.sleep(0.1)
    else:
        raise RuntimeError("Local guard did not arm; do not create")
    remote = base64.b64encode((ROOT / "scripts/runpod_deadline.py").read_bytes()).decode()
    code = "import base64;exec(compile(base64.b64decode(" + repr(remote) + "),'<guard>','exec'))"
    payload = {"name": state["name"], "image": IMAGE, "args": "python3 -u -c " + shlex.quote(code),
        "disk": 200, "cloud": "SECURE", "dataCenterIds": [REGION],
        "gpu": {"id": "NVIDIA H100 80GB HBM3", "count": 1, "minRamPerGpu": 128, "minCudaVersion": "13.2"},
        "ports": ["22/tcp"], "startSsh": False, "startJupyter": False,
        "env": {"PUBLIC_KEY": ssh_key.with_suffix(".pub").read_text().strip(),
                "BENCHMARK_DEADLINE": str(state["deadline"]), "BENCHMARK_NAME": state["name"]}}
    save(LEASE / "create-request.json", payload)
    state["status"] = "create_uncertain"
    save(STATE, state)
    print(json.dumps(payload))


def guard(env_file):
    key = load_keys(env_file)["runpod"]
    save(LEASE / "guard-ready.json", {"pid": os.getpid(), "at": time.time()})
    while True:
        state = read_state()
        if state["status"] in ("terminated", "rejected"):
            return
        if time.time() >= state["deadline"] or (LEASE / "terminate-now").exists():
            try:
                pod_id = state.get("pod_id")
                if not pod_id:
                    code, data = api("GET", "pods", key)
                    if code != 200:
                        raise RuntimeError("Cannot reconcile uncertain allocation")
                    pods = data.get("pods", []) if isinstance(data, dict) else data
                    matches = [p for p in pods if p.get("name") == state["name"]]
                    if len(matches) == 1:
                        pod_id = matches[0]["id"]
                    else:
                        raise RuntimeError("Uncertain allocation requires manual reconciliation")
                if terminate(pod_id, state["name"], key):
                    save(LEASE / "guard-termination.json", {"pod_id": pod_id, "verified_absent_at": time.time()})
                    return
            except Exception as exc:
                print(type(exc).__name__, flush=True)
        time.sleep(10)


def ssh_args(connection):
    import re
    if not re.fullmatch(r"[A-Za-z0-9.-]+", connection["host"]) or not 1 <= int(connection["port"]) <= 65535:
        raise ValueError("Invalid SSH endpoint")
    return ["-i", str(LEASE / "id_ed25519"), "-o", "IdentitiesOnly=yes", "-o", "BatchMode=yes",
            "-o", "ConnectTimeout=10", "-o", "StrictHostKeyChecking=accept-new",
            "-o", "UserKnownHostsFile=" + str(LEASE / "known_hosts")]


def remote(connection, code, input_text=None, timeout=40):
    r = subprocess.run(["ssh", *ssh_args(connection), "-p", str(connection["port"]),
                        "root@" + connection["host"], shlex.join(["python3", "-c", code])],
                       input=input_text, capture_output=True, text=True, timeout=timeout)
    if r.returncode:
        raise RuntimeError("Remote command failed (details retained remotely)")
    return r.stdout


def transfer(connection, paths, upload):
    peer = "root@" + connection["host"] + ":/root/benchmark/"
    sources = [str(p) for p in paths] if upload else [peer + p for p in paths]
    subprocess.run(["scp", *ssh_args(connection), "-P", str(connection["port"]), *sources,
                    peer if upload else str(LEASE) + "/"], check=True, timeout=180, capture_output=True)


def attach(env_file, pod_id):
    state = read_state()
    if state.get("pod_id") and state["pod_id"] != pod_id:
        raise ValueError("Different Pod is not this lease")
    code, pod = api("GET", "pods/" + pod_id, load_keys(env_file)["runpod"])
    if code != 200 or pod.get("name") != state["name"]:
        raise ValueError("Pod ownership not verified")
    state.update(pod_id=pod_id, status="created", attached_at=time.time())
    save(STATE, state)
    observe(env_file)


def observe(env_file):
    state = read_state()
    code, pod = api("GET", "pods/" + state["pod_id"], load_keys(env_file)["runpod"])
    if code != 200 or pod.get("name") != state["name"]:
        raise RuntimeError("Owned live Pod is required")
    rate = float(pod.get("cost", 0))
    if rate <= 0 or rate > HOURLY + 0.05:
        raise RuntimeError("Hourly quote outside approved bound; terminate")
    observation = {k: pod.get(k) for k in ("id", "name", "status", "startedAt", "cost", "dataCenterId", "gpu", "ssh")}
    save(LEASE / "allocation-observation.json", observation)
    return pod


def spawn(connection, action):
    executable = "python3" if action == "prepare" else "/root/benchmark/ltx-source/.venv/bin/python"
    code = ("import subprocess,json;from pathlib import Path;"
        "p=subprocess.Popen(" + repr([executable, "-u", "/root/benchmark/ltx_worker.py", action]) + ","
        "stdin=subprocess.DEVNULL,stdout=open('/root/benchmark/" + action + ".log','ab'),"
        "stderr=subprocess.STDOUT,start_new_session=True);"
        "Path('/root/benchmark/" + action + ".pid').write_text(str(p.pid));print(p.pid)")
    return int(remote(connection, code).strip())


def wait_phase(connection, action, expected, cutoff):
    previous = None
    while time.time() < cutoff:
        code = ("import json,os;from pathlib import Path;"
                "b=Path('/root/benchmark');p=b/" + repr(action + "-failure.json") + ";"
                "s=b/" + repr("generation-status.json" if action == "generate" else "prepare-status.json") + ";"
                "d=json.loads(p.read_text()) if p.exists() else (json.loads(s.read_text()) if s.exists() else {'phase':'starting'});"
                "pid=int((b/" + repr(action + ".pid") + ").read_text());d['process_exists']=Path('/proc/'+str(pid)).exists();print(json.dumps(d))")
        result = json.loads(remote(connection, code))
        save(LEASE / (action + "-observation.json"), result)
        if result["phase"] == expected:
            return result
        if result["phase"] == "failed" or not result["process_exists"]:
            raise RuntimeError(action + " exited; retain Pod for an in-place fix within deadline")
        if result["phase"] != previous:
            print(json.dumps({"action": action, "phase": result["phase"]}), flush=True)
            previous = result["phase"]
        time.sleep(3)
    raise TimeoutError("Existing lease reached export cutoff; no resubmission")


def close(env_file):
    state = read_state()
    if terminate(state["pod_id"], state["name"], load_keys(env_file)["runpod"]):
        state.update(status="terminated", verified_absent_at=time.time())
        save(STATE, state)
        print("Pod deleted and absence verified", flush=True)
    else:
        raise RuntimeError("Deletion not yet verified; guard remains armed")


def run(env_file):
    state = read_state()
    if state.get("status") != "created" or state.get("prepare_started_at") or state["generation_submissions"]:
        raise ValueError("Fresh attached lease required; use existing handles after interruption")
    while time.time() < state["deadline"] - 1200:
        pod = observe(env_file)
        connection = (pod.get("ssh") or {}).get("direct")
        if connection:
            try:
                d = json.loads(remote(connection, "from pathlib import Path;print(Path('/root/benchmark/guard-ready.json').read_text())"))
                if d.get("read_own_pod_verified"):
                    break
            except (RuntimeError, ValueError, subprocess.TimeoutExpired):
                pass
        print("Waiting for SSH and remote deadline guard", flush=True)
        time.sleep(5)
    else:
        raise TimeoutError("Startup consumed setup allowance")
    save(LEASE / "connection.json", connection)
    transfer(connection, [ROOT / "scripts/ltx_config.py", ROOT / "scripts/ltx_worker.py",
                          ROOT / "private/ltx-source.tar.gz", LEASE / "request.json"], True)
    remote(connection, "import subprocess;subprocess.run(['tar','-xzf','/root/benchmark/ltx-source.tar.gz','-C','/root/benchmark'],check=True)")
    token = load_keys(env_file, HF_ALIASES)["hf"]
    remote(connection, "import sys,os;from pathlib import Path;p=Path('/root/benchmark/hf-token');"
           "fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.write(fd,sys.stdin.buffer.read());os.close(fd)", token)
    del token
    remote(connection, "import subprocess;subprocess.Popen(['nvidia-smi','--query-gpu=timestamp,index,name,memory.used,utilization.gpu,power.draw','--format=csv','--loop=1','--filename=/root/benchmark/gpu-samples.csv'],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)")
    state.update(prepare_started_at=time.time())
    save(STATE, state)
    state["prepare_pid"] = spawn(connection, "prepare")
    save(STATE, state)
    wait_phase(connection, "prepare", "ready", state["deadline"] - 900)
    transfer(connection, ["prepare-status.json", "dependencies.txt", "prepare.log"], False)
    # Durable client claim BEFORE spawning; a lost response never authorizes another request.
    state.update(generation_submissions=1, submitted_at=time.time())
    save(STATE, state)
    submitted = time.monotonic()
    state["generate_pid"] = spawn(connection, "generate")
    save(STATE, state)
    wait_phase(connection, "generate", "completed", state["deadline"] - 180)
    transfer(connection, [RUN_ID + ".mp4", "generation-status.json"], False)
    state.update(end_to_end_seconds=time.monotonic() - submitted, downloaded_at=time.time())
    save(STATE, state)
    transfer(connection, ["gpu-samples.csv", "generate.log"], False)
    path = LEASE / (RUN_ID + ".mp4")
    result = json.loads((LEASE / "generation-status.json").read_text())
    if hashlib.sha256(path.read_bytes()).hexdigest() != result["output_sha256"]:
        raise ValueError("Downloaded artifact hash mismatch")
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"], check=True, timeout=60)
    state.update(decode_verified=True)
    save(STATE, state)
    close(env_file)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("arm", "guard", "attach", "run", "close", "status"))
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--pod-id")
    args = parser.parse_args()
    if args.action == "attach":
        attach(args.env_file, args.pod_id)
    elif args.action == "status":
        observe(args.env_file)
        print((LEASE / "allocation-observation.json").read_text())
    else:
        globals()[args.action](args.env_file)
