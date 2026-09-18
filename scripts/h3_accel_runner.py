"""Run exactly two approved adapters on one existing, bounded H100 rental.

No cloud creation. Failures can retain this Pod until its existing deadline.
"""

import argparse
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time

from check_access import load_keys
from runpod_deadline import terminate
from runpod_trial import api, save

ROOT = Path(__file__).resolve().parents[1]
LEASE = ROOT / "private/runpod-h100x4accel-p01-001"


def ssh_args(connection):
    host, port = connection["host"], connection["port"]
    if not re.fullmatch(r"[A-Za-z0-9.-]+", host) or type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("Invalid direct SSH endpoint")
    return ["-i", str(LEASE / "id_ed25519"), "-o", "IdentitiesOnly=yes",
            "-o", "StrictHostKeyChecking=accept-new", "-o", "UserKnownHostsFile=" + str(LEASE / "known_hosts"),
            "-o", "BatchMode=yes", "-o", "ConnectTimeout=10"]


def remote(connection, code, timeout=45):
    command = shlex.join(["python3", "-c", code])
    result = subprocess.run(["ssh", *ssh_args(connection), "-p", str(connection["port"]),
                             "root@" + connection["host"], command], capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError("Remote command failed: " + result.stderr[-1200:])
    return result.stdout


def transfer(connection, paths, upload):
    peer = "root@" + connection["host"] + ":/root/benchmark/"
    sources = [str(p) for p in paths] if upload else [peer + name for name in paths]
    target = peer if upload else str(LEASE) + "/"
    subprocess.run(["scp", *ssh_args(connection), "-P", str(connection["port"]),
                    *sources, target], check=True, timeout=90, capture_output=True)


def main():
    global LEASE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--attempt", type=int, choices=(1, 2), default=1)
    parser.add_argument("--keep-on-error", action="store_true",
                        help="Retain this Pod for explicitly requested debugging until its existing deadline")
    args = parser.parse_args()
    LEASE = ROOT / f"private/runpod-h100x4accel-p01-{args.attempt:03d}"
    state = json.loads((LEASE / "state.json").read_text())
    if state.get("status") != "created" or state.get("hardware") != "h100x4accel" or state.get("generation_submissions") != 0:
        raise RuntimeError("A fresh approved acceleration lease is required")
    key = load_keys(args.env_file)["runpod"]
    connection = None
    trial_ok = False
    try:
        while time.time() < state["deadline"] - 600:
            code, pod = api("GET", "pods/" + state["pod_id"], key)
            if code != 200 or pod.get("name") != state["name"]:
                raise RuntimeError("Pod identity check failed")
            if float(pod.get("cost", 0)) > 14.05:
                raise RuntimeError("Returned hourly rate exceeds the approved profile")
            save(LEASE / "allocation-observation.json", {k: pod.get(k) for k in
                 ("id", "name", "status", "startedAt", "cost", "dataCenterId", "gpu", "ssh")})
            connection = (pod.get("ssh") or {}).get("direct")
            if connection:
                try:
                    ready = remote(connection, "import json;from pathlib import Path;print(json.dumps(json.loads(Path('/root/benchmark/guard-ready.json').read_text())))")
                    if json.loads(ready).get("read_own_pod_verified"):
                        break
                except (RuntimeError, subprocess.TimeoutExpired, ValueError):
                    pass
            print("Waiting for SSH and the independent deadline guard; no generation submitted", flush=True)
            time.sleep(5)
        else:
            raise TimeoutError("Pod startup exceeded the setup allowance")
        transfer(connection, [ROOT / "scripts/h3_serve.py", ROOT / "scripts/h3_adapters.py",
                              ROOT / "scripts/h3_lora_compat.py"], True)
        preflight = remote(connection, "import subprocess;from pathlib import Path; r=subprocess.run(['/opt/sglang/bin/python','-c','import torch,diffusers,av;assert torch.cuda.device_count()==4;print(torch.__version__)'],capture_output=True,text=True);print(r.stdout);print(r.stderr);assert r.returncode==0; print(subprocess.check_output(['nvidia-smi','topo','-m'],text=True))")
        (LEASE / "hardware-preflight.txt").write_text(preflight)
        print("Pinned environment and four GPUs verified", flush=True)
        remote(connection, "import subprocess;subprocess.Popen(['nvidia-smi','--query-gpu=timestamp,index,name,memory.used,utilization.gpu,power.draw','--format=csv','--loop=1','--filename=/root/benchmark/gpu-samples.csv'],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)")
        for recipe in ("larry8", "light4"):
            if time.time() >= state["deadline"] - 420:
                raise TimeoutError("Insufficient time for the next adapter and safe export")
            command = ["/opt/sglang/bin/python", "/root/benchmark/h3_serve.py", "--recipe", recipe]
            if args.attempt == 2:
                command.append("--lora-compat-fix")
            launch_code = ("import subprocess;from pathlib import Path;"
                "p=subprocess.Popen(" + repr(command) + ","
                "stdin=subprocess.DEVNULL,stdout=open('/root/benchmark/service-" + recipe + ".log','ab'),stderr=subprocess.STDOUT,start_new_session=True);"
                "Path('/root/benchmark/service-" + recipe + ".pid').write_text(str(p.pid));print(p.pid)")
            pid = int(remote(connection, launch_code).strip())
            print(json.dumps({"recipe": recipe, "service_pid": pid, "phase": "loading_and_warmup"}), flush=True)
            result = subprocess.run([sys.executable, str(ROOT / "scripts/h3_trial.py"), "--recipe", recipe,
                "--attempt", str(args.attempt),
                "--expected-pod-id", state["pod_id"], "--ssh-host", connection["host"], "--ssh-port", str(connection["port"]),
                "--service-pid", str(pid)],
                timeout=max(1, state["deadline"] - time.time() - 150))
            transfer(connection, ["service-" + recipe + ".log"], False)
            if result.returncode:
                raise RuntimeError("Adapter request failed; no automatic retry")
            transfer(connection, ["runtime-" + recipe + ".json"], False)
            remote(connection, "import os,signal,time;from pathlib import Path;pid=" + str(pid) + ";"
                "cmd=Path(f'/proc/{pid}/cmdline').read_bytes();assert b'sglang' in cmd;"
                "assert os.getpgid(pid)==pid;os.killpg(pid,signal.SIGTERM);time.sleep(3)")
            print(json.dumps({"recipe": recipe, "phase": "downloaded_and_service_stopped"}), flush=True)
        trial_ok = True
    finally:
        if connection:
            try:
                transfer(connection, ["gpu-samples.csv"], False)
            except Exception:
                print("GPU sample export unavailable; applying the selected retention policy", flush=True)
        if not trial_ok and args.keep_on_error:
            current = json.loads((LEASE / "state.json").read_text())
            current.update(retained_for_debugging=True, last_runner_failure_at=time.time())
            save(LEASE / "state.json", current)
            print("Pod retained for debugging; original deadline remains armed", flush=True)
        else:
            for _ in range(3):
                try:
                    if terminate(state["pod_id"], state["name"], key):
                        current = json.loads((LEASE / "state.json").read_text())
                        current.update(status="terminated", terminated_at=time.time(), both_adapters_downloaded=trial_ok)
                        save(LEASE / "state.json", current)
                        print("Pod deleted and absence verified", flush=True)
                        break
                except Exception:
                    pass
                time.sleep(2)
            else:
                raise RuntimeError("Deletion not verified; independent deadline guard remains armed")


if __name__ == "__main__":
    main()
