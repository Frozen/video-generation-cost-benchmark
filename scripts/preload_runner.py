"""Drive the already-created CPU preload; delete CPU on every exit."""

import json
from pathlib import Path
import subprocess
import time

import h3_accel_runner as transport
from check_access import load_keys
from resource_watchdog import expire
from runpod_trial import api, save

ROOT = Path(__file__).resolve().parents[1]
LEASE = ROOT / "private/preload-eu-nl-001"
ENV_FILE = Path("/Users/frozen/projects/ai-video/.env.local")


def main():
    state = json.loads((LEASE / "state.json").read_text())
    volume, cpu = state["resources"]
    key = load_keys(ENV_FILE)["runpod"]
    transport.LEASE = LEASE
    connection = None
    succeeded = False
    try:
        while time.time() < min(state["created_at"] + 600, cpu["expires_at"] - 300):
            code, pod = api("GET", "pods/" + cpu["id"], key)
            if code != 200 or pod.get("name") != cpu["name"] or float(pod["cost"]) > 0.08:
                raise RuntimeError("CPU identity or price mismatch")
            if pod.get("gpu") or pod.get("cpu", {}).get("vcpuCount") != 2:
                raise RuntimeError("Expected two-vCPU, no-GPU allocation")
            if pod.get("mounts", {}).get("network") != [{"path": "/workspace", "volumeId": volume["id"]}]:
                raise RuntimeError("Volume mount mismatch")
            connection = (pod.get("ssh") or {}).get("direct")
            save(LEASE / "allocation-observation.json", {k: pod.get(k) for k in
                ("id", "name", "status", "cost", "startedAt", "ssh", "cpu", "mounts")})
            if connection:
                try:
                    ready = transport.remote(connection, "import json;from pathlib import Path;print(json.loads(Path('/root/benchmark/guard-ready.json').read_text())['read_own_pod_verified'])")
                    if ready.strip() == "True":
                        break
                except (RuntimeError, subprocess.TimeoutExpired):
                    pass
            print("Waiting for CPU SSH and deadline guard", flush=True)
            time.sleep(5)
        else:
            raise TimeoutError("CPU startup allowance exhausted")
        transport.transfer(connection, [ROOT / "scripts/preload_cpu.py", ROOT / "preload-manifest.json",
                                         ROOT / "private/hf-install.sh"], True)
        transport.remote(connection, "import subprocess;from pathlib import Path;assert not Path('/workspace/preload-status.json').exists();p=subprocess.Popen(['python3','-u','/root/benchmark/preload_cpu.py'],stdin=subprocess.DEVNULL,stdout=open('/root/benchmark/preload.log','ab'),stderr=subprocess.STDOUT,start_new_session=True);print(p.pid)")
        while time.time() < cpu["expires_at"] - 120:
            status = json.loads(transport.remote(connection, "from pathlib import Path;import json;p=Path('/workspace/preload-status.json');print(p.read_text() if p.exists() else json.dumps({'status':'starting'}))"))
            save(LEASE / "preload-observation.json", status)
            print(json.dumps(status), flush=True)
            if status["status"] == "verified":
                succeeded = True
                break
            if status["status"] == "failed":
                raise RuntimeError("CPU preload failed")
            time.sleep(15)
        else:
            raise TimeoutError("CPU preload allowance exhausted")
    finally:
        if connection:
            try:
                transport.transfer(connection, ["preload.log"], False)
            except Exception:
                pass
        if not expire(cpu, key):
            raise RuntimeError("CPU deletion not verified; watchdog remains armed")
        state["cpu_verified_absent_at"] = time.time()
        state["preload_verified"] = succeeded
        if not succeeded:
            if not expire(volume, key):
                raise RuntimeError("Failed-preload volume deletion not verified")
            state.update(closed=True, volume_verified_absent_at=time.time())
        state["status"] = "preloaded_cpu_deleted" if succeeded else "failed_resources_deleted"
        save(LEASE / "state.json", state)
        print(json.dumps({"status": state["status"], "cpu_deleted": True,
                          "network_volume_retained": succeeded}), flush=True)


if __name__ == "__main__":
    main()
