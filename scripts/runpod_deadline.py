"""Single-Pod shutdown backstop; never accepts an arbitrary target for deletion."""

import json
import os
from pathlib import Path
import re
import subprocess
import time


def request(method, pod_id, key):
    if not re.fullmatch(r"[a-zA-Z0-9_-]{6,64}", pod_id):
        raise ValueError("Invalid Pod ID")
    config = "header = " + json.dumps("Authorization: Bearer " + key) + "\n"
    reply = subprocess.run(
        ["curl", "-q", "--config", "-", "--silent", "--show-error",
         "--proto", "=https", "--max-redirs", "0", "--max-time", "25",
         "--request", method, "--write-out", "\n%{http_code}",
         "https://api.runpod.io/v2/pods/" + pod_id],
        input=config, capture_output=True, text=True, timeout=30,
    )
    if reply.returncode:
        raise RuntimeError("Control-plane transport error")
    body, code = reply.stdout.rsplit("\n", 1)
    return int(code), json.loads(body) if body.strip() else {}


def owns(pod, pod_id, name):
    return isinstance(pod, dict) and pod.get("id") == pod_id and pod.get("name") == name


def terminate(pod_id, name, key):
    code, pod = request("GET", pod_id, key)
    if code == 404:
        return True
    if code != 200 or not owns(pod, pod_id, name):
        raise RuntimeError("Ownership verification failed; refusing deletion")
    code, _ = request("DELETE", pod_id, key)
    if code not in (200, 202, 204, 404):
        raise RuntimeError("Deletion not accepted")
    code, _ = request("GET", pod_id, key)
    return code == 404


def remote_main():
    # This program is embedded in our own Pod's startup arguments, not fetched
    # from a mutable URL. Use only Runpod's own automatically provisioned
    # Pod-scoped credential; never transmit the user's account control key.
    deadline = float(os.environ["BENCHMARK_DEADLINE"])
    name = os.environ["BENCHMARK_NAME"]
    pod_id = os.environ["RUNPOD_POD_ID"]
    key = os.environ.pop("RUNPOD_API_KEY", "")
    root = Path("/root/benchmark")
    root.mkdir(mode=0o700, exist_ok=True)
    try:
        ssh_dir = Path("/root/.ssh")
        ssh_dir.mkdir(mode=0o700, exist_ok=True)
        authorized = ssh_dir / "authorized_keys"
        authorized.write_text(os.environ["PUBLIC_KEY"].strip() + "\n")
        authorized.chmod(0o600)
        Path("/run/sshd").mkdir(exist_ok=True)
        subprocess.run(["ssh-keygen", "-A"], check=True, capture_output=True)
        subprocess.Popen(["/usr/sbin/sshd", "-D", "-e", "-o", "PasswordAuthentication=no",
                          "-o", "PermitRootLogin=prohibit-password",
                          "-o", "PermitEmptyPasswords=no"],
                         stdin=subprocess.DEVNULL,
                         stdout=open(root / "sshd.log", "a"), stderr=subprocess.STDOUT)
        if not key:
            raise RuntimeError("Automatically provisioned Pod key unavailable")
        code, pod = request("GET", pod_id, key)
        if code != 200 or not owns(pod, pod_id, name):
            raise RuntimeError("Remote control-plane check failed")
        (root / "guard-ready.json").write_text(json.dumps({"deadline": deadline,
            "read_own_pod_verified": True, "pid": os.getpid()}))
        print("Remote deadline armed; own-Pod read verified", flush=True)
    except Exception as exc:
        print("Bootstrap check failed: " + type(exc).__name__, flush=True)
        deadline = min(deadline, time.time() + 60)
    while True:
        if time.time() >= deadline:
            try:
                if terminate(pod_id, name, key):
                    return
            except Exception as exc:
                print("Shutdown retry: " + type(exc).__name__, flush=True)
        time.sleep(10)


if __name__ == "__main__":
    remote_main()
