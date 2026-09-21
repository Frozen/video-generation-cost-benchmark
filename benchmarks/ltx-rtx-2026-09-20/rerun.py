"""Run the unchanged original worker on an already prepared, guarded GPU host.

This adapter only renews run identity/deadlines and supplies the original start
trigger. It does not provision infrastructure, download weights or change model
settings. It was added for reproduction; original measurements predate it.
"""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "original-worker"))
from load_window import verify_guard
from ltx_gpu_price_worker import required_suite_seconds, validate_profile


def run(base):
    base = base.resolve()
    guard = json.loads((base / "guard-ready.json").read_text())
    verify_guard(base / "guard-ready.json", guard["deadline"])
    plan = json.loads((ROOT / "evidence/resident.json").read_text())
    plan["run_id"] = "LTX25_REPRO_" + uuid.uuid4().hex[:12]
    limits = plan["limits"]
    limits["shutdown_deadline_epoch"] = guard["deadline"]
    limits["admission_deadline_epoch"] = guard["deadline"] - limits["request_bound_seconds"] - limits["export_reserve_seconds"]
    validate_profile(plan)
    if time.time() + required_suite_seconds(plan) + 60 >= guard["deadline"]:
        raise RuntimeError("Not enough guarded lease time for both warmups, ten requests and export")
    manifest = base / (plan["run_id"] + ".json")
    with manifest.open("x") as target:
        json.dump(plan, target, indent=2)
        target.write("\n")
    manifest_hash = hashlib.sha256(manifest.read_bytes()).hexdigest()
    output = base / plan["run_id"]
    command = [str(base / "ltx-source/.venv/bin/python"),
               str(ROOT / "original-worker/ltx_gpu_price_worker.py"),
               "--manifest", str(manifest), "--base", str(base)]
    child = subprocess.Popen(command)
    triggered = False
    try:
        while child.poll() is None:
            if not triggered and (output / "events.jsonl").exists():
                lines = (output / "events.jsonl").read_text().splitlines(keepends=True)
                rows = [json.loads(line) for line in lines if line.endswith("\n")]
                if any(row["event"] == "ready" for row in rows):
                    temporary = output / "start.tmp"
                    temporary.write_text(json.dumps({"run_id": plan["run_id"], "manifest_sha256": manifest_hash}))
                    temporary.replace(output / "start.json")
                    triggered = True
            if time.time() >= guard["deadline"] - limits["export_reserve_seconds"]:
                raise TimeoutError("Reproduction exceeded its generation allowance")
            time.sleep(0.2)
        if child.returncode != 0:
            raise RuntimeError("Original worker failed; preserve logs and completed artifacts")
    finally:
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
    print("Completed output directory:", output)
    print("Copy and verify outputs before the independent lease deadline.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=Path("/root/benchmark"))
    run(parser.parse_args().base)
