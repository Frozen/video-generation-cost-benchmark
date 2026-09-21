"""Guarded one-hour LTX workload experiment. Allocation remains a separate MCP action."""

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
from sustained_collect import collect
from load_window import sha256, validate_manifest
from ltx_sustained_worker import profile, validate_profile, required_suite_seconds
from runpod_trial import save
from wan_smoke import wait_phase

ROOT = Path(__file__).resolve().parents[1]
PLAN = None
RUN_ID = None
DIRECTORY = None
PROPOSAL = ROOT / "ltx-sustained-proposal.json"


def configure_lease(path):
    global PLAN, RUN_ID, DIRECTORY
    PLAN = Path(path).resolve()
    plan = validate_plan(json.loads(PLAN.read_text()))
    RUN_ID = plan["run_id"]
    DIRECTORY = ROOT / "private" / "ltx-sustained-rtx6000-001"
    lease.ROOT, lease.LEASE, lease.STATE = ROOT, DIRECTORY, DIRECTORY / "state.json"
    lease.RUN_ID, lease.HOURLY = RUN_ID, float(plan["compute_hourly_usd"])


def validate_plan(plan):
    proposal = json.loads(PROPOSAL.read_text())
    if plan["run_id"] != "LTX25_SUSTAINED_RTX6000_001" or plan["candidate_id"] != "RTX6000":
        raise ValueError("Unexpected registered run")
    if plan["requests"] != proposal["requests"] or plan["retry_requests"] != proposal["retry_requests"]:
        raise ValueError("Frozen inputs changed")
    for field, expected in {"gpu_id":"NVIDIA RTX PRO 6000 Blackwell Server Edition",
            "gpu_count":1,"compute_hourly_usd":"2.09","reservation_usd":"3.25",
            "max_lease_seconds":5400,"min_cuda_version":"13.2","disk_gb":200,
            "disk_monthly_usd_per_gb":"0.10","requests_per_window":500,
            "target_queue_seconds":3600,"window_order":["resident"],"compute_capability":[12,0]}.items():
        if plan.get(field) != expected:
            raise ValueError("Changed registered field: " + field)
    rate = Decimal(plan["compute_hourly_usd"])/3600 + Decimal(plan["disk_gb"])*Decimal(plan["disk_monthly_usd_per_gb"])/(30*86400)
    if rate*(plan["max_lease_seconds"]+120)>Decimal(plan["reservation_usd"]):
        raise ValueError("Reservation does not cover the lease and shutdown allowance")
    needed=2*plan["warmup_bound_seconds"]+3600+plan["request_bound_seconds"]+plan["export_reserve_seconds"]
    if not needed+60 <= plan["minimum_after_prepare_seconds"] <= plan["max_lease_seconds"]-600:
        raise ValueError("Incomplete warmup/measurement/export allowance")
    return plan


def require_budget_authorization():
    proposal = json.loads(PROPOSAL.read_text())
    authorization = proposal.get("new_budget_authorization")
    if not isinstance(authorization, dict) or not authorization.get("user_instruction"):
        raise ValueError("Additional experiment budget is not authorized")
    from budget import validate as validate_budget
    ledger = json.loads((ROOT / "private/ledger.json").read_text())
    validate_budget(ledger)
    if Decimal(str(authorization.get("cap_usd", "0"))) * 100 != ledger["cap_cents"]:
        raise ValueError("Authorized total does not match the existing budget ledger")


def manifests(plan, scenes, criteria_sha256, deadline):
    if len(scenes) != 20 or criteria_sha256 != plan["quality_criteria_sha256"]:
        raise ValueError("Changed scene set or quality contract")
    by_id = {s["scene_id"]:s for s in scenes}
    for request in plan["requests"]:
        if any(request[k] != by_id[request["scene_id"]][k] for k in ("scene_id","source_url","prompt","prompt_sha256")):
            raise ValueError("Frozen prompt differs")
    manifest={"version":1,"run_id":plan["run_id"]+"_RESIDENT","profile":profile(plan["gpu_id"]),
              "batch_size":1,"concurrency":1,
              "quality_contract":{"audio_required":True,"criteria_sha256":criteria_sha256},
              "limits":{"max_requests":500,"target_queue_seconds":3600,
              "warmup_bound_seconds":plan["warmup_bound_seconds"],"request_bound_seconds":plan["request_bound_seconds"],
              "export_reserve_seconds":plan["export_reserve_seconds"],"shutdown_deadline_epoch":deadline,
              "admission_deadline_epoch":deadline-plan["request_bound_seconds"]-plan["export_reserve_seconds"]},
              "requests":plan["requests"],"retry_requests":plan["retry_requests"],
              "technical_warmup_seeds":plan["technical_warmup_seeds"]}
    validate_profile(manifest)
    return {"resident":manifest}


def verify_runner_sources(plan):
    for name, expected in plan["local_runner_sha256"].items():
        if sha256(ROOT / "scripts" / name) != expected:
            raise ValueError("Local controller dependency changed after freezing: " + name)


def require_all_deliveries(delivery):
    receipts=delivery["receipts"]
    if not delivery["controller_complete"] or not all(r["decode_verified"] and r["output_contract_pass"] for r in receipts):
        raise RuntimeError("Export and verify all generated outputs before successful teardown")


def hour_complete(events):
    windows = [e for e in events if e["event"] == "window_finished"]
    return (len(windows) == 1 and windows[0]["worker_window_seconds"] >= 3600
            and windows[0]["stop_reason"] == "target_duration_reached"
            and not any(e["event"] == "worker_failed" for e in events))


def arm(env_file):
    require_budget_authorization()
    plan = validate_plan(json.loads(PLAN.read_text()))
    verify_runner_sources(plan)
    for name, digest in plan["preparation_files"].items():
        if sha256(ROOT / "private" / name) != digest:
            raise ValueError("Prepared artifact mismatch")
    for name, digest in plan["worker_sha256"].items():
        if sha256(ROOT / "scripts" / name) != digest:
            raise ValueError("Worker changed after freezing the plan")
    scenes = json.loads((ROOT / "ltx-sustained-scenes.json").read_text())
    criteria = ROOT / "ltx-sustained-criteria.json"
    if sha256(criteria) != plan["quality_criteria_sha256"]:
        raise ValueError("Quality criteria changed")
    if [s["prompt_sha256"] for s in scenes] != plan["scene_prompt_sha256"]:
        raise ValueError("Frozen scene set changed")
    keys = lease.load_keys(env_file, {"hf": ("HF_TOKEN", "HUGGINGFACE_HUB_TOKEN", "HUGGINGFACE_TOKEN", "FACE_API"),
                                      "runpod": ("RUNPOD_API_KEY", "RUNPOD_API")})
    if not keys["runpod"] or not keys["hf"]:
        raise ValueError("Local Runpod and HF access required")
    if DIRECTORY.exists():
        raise ValueError("Existing run journal must not be replayed")
    now = time.time()
    frozen = manifests(plan, scenes, sha256(criteria), now + plan["max_lease_seconds"])
    DIRECTORY.mkdir(mode=0o700)
    transact(ROOT / "private/ledger.json", "reserve", RUN_ID, plan["reservation_usd"], "generation")
    state = {"run_id": RUN_ID, "name": "ltx-price-" + secrets.token_hex(6), "status": "armed",
             "started_at": now, "deadline": now + plan["max_lease_seconds"], "plan_sha256": sha256(PLAN),
             "reservation_usd": plan["reservation_usd"], "generation_submissions": 0, "windows": {}}
    save(lease.STATE, state)
    save(DIRECTORY / "ltx-cost-plan.json", plan)
    save(DIRECTORY / "lease.json", {"run_id": RUN_ID, "deadline": state["deadline"]})
    for mode, manifest in frozen.items():
        save(DIRECTORY / (mode + ".json"), manifest)
    key = DIRECTORY / "id_ed25519"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True)
    with (DIRECTORY / "guard.log").open("ab") as output:
        process = subprocess.Popen(["/usr/bin/caffeinate", "-ims", sys.executable, str(Path(__file__).resolve()),
                                    "guard", "--plan", str(PLAN), "--env-file", str(env_file)], stdin=subprocess.DEVNULL,
                                   stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
    for _ in range(50):
        if (DIRECTORY / "guard-ready.json").exists() and process.poll() is None:
            break
        time.sleep(.1)
    else:
        raise RuntimeError("Deadline guard not ready; do not allocate")
    code = "import base64;exec(compile(base64.b64decode(" + repr(base64.b64encode((ROOT / "scripts/runpod_deadline.py").read_bytes()).decode()) + "),'<guard>','exec'))"
    payload = {"name": state["name"], "image": plan["image"], "args": "python3 -u -c " + shlex.quote(code),
               "disk": plan["disk_gb"], "cloud": plan["cloud"], "dataCenterIds": [plan["region"]],
               "gpu": {"id": plan["gpu_id"], "count": 1, "minRamPerGpu": plan["min_ram_per_gpu_gb"],
                       "minCudaVersion": plan["min_cuda_version"]}, "ports": ["22/tcp"],
               "startSsh": False, "startJupyter": False, "env": {"PUBLIC_KEY": key.with_suffix(".pub").read_text().strip(),
               "BENCHMARK_DEADLINE": str(state["deadline"]), "BENCHMARK_NAME": state["name"]}}
    if plan["region"] is None:
        payload.pop("dataCenterIds")
    save(DIRECTORY / "create-request.json", payload)
    state["status"] = "create_uncertain"
    save(lease.STATE, state)
    print(json.dumps({"run_id": RUN_ID, "deadline": state["deadline"], "reservation_usd": plan["reservation_usd"]}))


def spawn(connection, command, name):
    code = ("import subprocess;from pathlib import Path;p=subprocess.Popen(" + repr(command)
            + ",stdin=subprocess.DEVNULL,stdout=open('/root/benchmark/" + name
            + ".log','ab'),stderr=subprocess.STDOUT,start_new_session=True);"
            + "Path('/root/benchmark/" + name + ".pid').write_text(str(p.pid));print(p.pid)")
    return int(lease.remote(connection, code).strip())


def wait_exit(connection, pid, cutoff):
    while time.time() < cutoff:
        code = "from pathlib import Path;p=Path('/proc/" + str(pid) + "/stat');print('gone' if not p.exists() else p.read_text().split()[2])"
        try:
            if lease.remote(connection, code).strip() in ("gone", "Z"):
                return
        except (RuntimeError, subprocess.TimeoutExpired):
            pass
        time.sleep(2)
    raise TimeoutError("Original worker still unconfirmed; do not start another")


def run(env_file, *, resume_preparation=False):
    plan = validate_plan(json.loads(PLAN.read_text()))
    state = lease.read_state()
    verify_runner_sources(plan)
    original_ssh_args = lease.ssh_args
    lease.ssh_args = lambda c: original_ssh_args(c) + ["-o", "ControlMaster=auto", "-o", "ControlPersist=120",
                                                       "-o", "ControlPath=/private/tmp/ltx-price-%C"]
    if state["status"] != "created" or (state.get("prepare_claimed_at") and not resume_preparation) or sha256(PLAN) != state["plan_sha256"]:
        raise ValueError("Fresh attached frozen lease required; never replay an uncertain run")
    cutoff = state["deadline"] - plan["minimum_after_prepare_seconds"]
    if resume_preparation:
        if (not state.get("prepare_pid") or state["windows"] or state["generation_submissions"]
                or state.get("worker_spawn_claimed_at")):
            raise ValueError("Only an existing preparation worker may be resumed")
        connection = json.loads((DIRECTORY / "connection.json").read_text())
        lease.remote(connection, "from pathlib import Path;assert not Path('/root/benchmark/" + RUN_ID + "_RESIDENT').exists()")
    else:
        connection = None
        while time.time() < cutoff:
            pod = lease.observe(env_file)
            if Decimal(str(pod["cost"])) > Decimal(plan["compute_hourly_usd"]):
                raise ValueError("Rental price exceeds the frozen quote")
            candidate = (pod.get("ssh") or {}).get("direct")
            if candidate:
                try:
                    guard = json.loads(lease.remote(candidate, "from pathlib import Path;print(Path('/root/benchmark/guard-ready.json').read_text())"))
                    if guard.get("read_own_pod_verified") and guard["deadline"] == state["deadline"]:
                        connection = candidate
                        break
                except (RuntimeError, ValueError, subprocess.TimeoutExpired):
                    pass
            time.sleep(5)
        if connection is None:
            raise TimeoutError("Startup consumed preparation allowance")
        collector_connection = dict(connection, identity_file=str(DIRECTORY / "id_ed25519"),
                                   known_hosts_file=str(DIRECTORY / "known_hosts"))
        save(DIRECTORY / "connection.json", collector_connection)
        uploads = [DIRECTORY / "ltx-cost-plan.json", DIRECTORY / "lease.json", *(ROOT / "private" / n for n in plan["preparation_files"] if n != "ltx-audio-uv-linux.whl"),
                   *(ROOT / "scripts" / n for n in plan["worker_sha256"]),
                   *(DIRECTORY / (m + ".json") for m in plan["window_order"])]
        for name, digest in plan["worker_sha256"].items():
            if sha256(ROOT / "scripts" / name) != digest:
                raise ValueError("Worker changed after arming")
        lease.transfer(connection, uploads, True)
        # Fetch the same hash-pinned public wheel directly; avoid slow client upload.
        wheel_url = "https://files.pythonhosted.org/packages/0d/8d/e45565a046bd2592b75cb96fded9a7ab0cd6d470152fec713c82ee83ddbb/uv-0.12.17-py3-none-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"
        expected = plan["preparation_files"]["ltx-audio-uv-linux.whl"]
        code = ("import subprocess,hashlib,os;from pathlib import Path;"
                "p=Path('/root/benchmark/ltx-audio-uv-linux.whl');q=p.with_suffix('.download');"
                "subprocess.run(['curl','-q','--fail','--silent','--show-error','--location',"
                "'--proto','=https','--proto-redir','=https','--max-time','45'," + repr(wheel_url) +
                ",'--output',str(q)],check=True);"
                "assert hashlib.sha256(q.read_bytes()).hexdigest()==" + repr(expected) + ";os.replace(q,p)")
        lease.remote(connection, code, timeout=50)
        links = lease.download_links(env_file)
        lease.remote(connection, "import sys,os;fd=os.open('/root/benchmark/download-links.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.write(fd,sys.stdin.buffer.read());os.close(fd)", json.dumps(links))
        del links
        lease.remote(connection, "import subprocess;subprocess.Popen(['nvidia-smi','--query-gpu=timestamp,index,name,memory.used,utilization.gpu,power.draw','--format=csv','--loop=1','--filename=/root/benchmark/gpu-samples.csv'],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)")
        state["prepare_claimed_at"] = time.time()
        save(lease.STATE, state)
        state["prepare_pid"] = spawn(connection, ["python3", "-u", "/root/benchmark/ltx_gpu_price_prepare.py"], "prepare")
        save(lease.STATE, state)
    wait_phase(connection, "prepare", "ready", cutoff)
    lease.transfer(connection, ["prepare-status.json", "dependencies.txt", "prepare.log"], False)
    state["worker_spawn_claimed_at"] = time.time()
    save(lease.STATE, state)
    pid = spawn(connection, ["/root/benchmark/ltx-source/.venv/bin/python", "-u",
        "/root/benchmark/ltx_sustained_worker.py", "--manifest",
        "/root/benchmark/resident.json"], "duration")
    state["worker_pid"] = pid
    save(lease.STATE, state)
    for mode in plan["window_order"]:
        state["windows"][mode] = {"pid": pid}
        save(lease.STATE, state)
        delivery = collect(DIRECTORY / (mode + ".json"), DIRECTORY / "connection.json", ROOT / "private/ledger.json",
                          RUN_ID, plan["reservation_usd"], DIRECTORY / (mode + "-delivery"))
        expected = len(delivery["receipts"])
        require_all_deliveries(delivery)
        events = [json.loads(line) for line in (DIRECTORY / (mode + "-delivery/events.jsonl")).read_text().splitlines()]
        state["windows"][mode]["requests_started"] = sum(e["event"] == "request_started" for e in events)
        state["generation_submissions"] = sum(w.get("requests_started", 0) for w in state["windows"].values())
        state["windows"][mode].update(collection_complete=True, hour_complete=hour_complete(events), closed_at=time.time())
        save(lease.STATE, state)
        print(json.dumps({"mode": mode, "delivered": expected, "window_seconds": delivery["window_seconds"]}), flush=True)
    wait_exit(connection, pid, min(time.time() + 30, state["deadline"] - 30))
    lease.transfer(connection, ["duration.log", "gpu-samples.csv", "ltx-source/uv.lock"], False)
    lease.close(env_file)
    if not all(w.get("hour_complete") for w in state["windows"].values()):
        raise RuntimeError("Artifacts exported and lease closed, but the full hour did not complete")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "arm", "guard", "attach", "run", "close", "status", "resume-preparation"))
    parser.add_argument("--env-file", type=Path, default=Path("/Users/frozen/projects/ai-video/.env.local"))
    parser.add_argument("--pod-id")
    parser.add_argument("--plan", type=Path, required=True)
    args = parser.parse_args()
    configure_lease(args.plan)
    if args.action == "check":
        validate_plan(json.loads(PLAN.read_text()))
        print("Registered sustained plan validated; no allocation performed.")
    elif args.action == "attach":
        lease.attach(args.env_file, args.pod_id)
    elif args.action in ("guard", "close"):
        getattr(lease, args.action)(args.env_file)
    elif args.action == "resume-preparation":
        run(args.env_file, resume_preparation=True)
    elif args.action == "status":
        print(json.dumps(lease.observe(args.env_file)))
    else:
        globals()[args.action](args.env_file)
