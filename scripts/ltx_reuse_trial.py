"""One bounded lease for a warm baseline/resident LTX comparison."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

import ltx_trial as base
from ltx_reuse_config import CASES, RUN_ID, output_id

ROOT = Path(__file__).resolve().parents[1]
LEASE = ROOT / "private/ltx-reuse-h100-p01-001"
base.RUN_ID, base.LEASE, base.STATE = RUN_ID, LEASE, LEASE / "state.json"


def arm(env_file):
    base.arm(env_file, guard_script=Path(__file__).resolve())


def wait_service(connection, phase, case, cutoff):
    previous = None
    while time.time() < cutoff:
        code = ("import json; from pathlib import Path; b=Path('/root/benchmark'); "
                "f=b/'reuse-failure.json'; s=b/'reuse-service-status.json'; "
                "d={'phase':'failed','failure':json.loads(f.read_text())} if f.exists() else "
                "(json.loads(s.read_text()) if s.exists() else {'phase':'starting'}); print(json.dumps(d))")
        status = json.loads(base.remote(connection, code))
        base.save(LEASE / "service-observation.json", status)
        if status["phase"] == "failed":
            raise RuntimeError("Reuse worker failed; retain original lease for bounded debugging")
        if status["phase"] == phase and status.get("case") == case:
            return status
        key = (status["phase"], status.get("case"))
        if key != previous:
            print(json.dumps(status), flush=True)
            previous = key
        time.sleep(1)
    raise TimeoutError("Original lease export cutoff reached; no resubmission")


def run(env_file):
    extra = [ROOT / "scripts" / name for name in ("ltx_reuse.py", "ltx_reuse_config.py", "ltx_reuse_worker.py")]
    connection, state = base.prepare_lease(env_file, extra)
    code = ("import subprocess; p=subprocess.Popen(['/root/benchmark/ltx-source/.venv/bin/python','-u',"
            "'/root/benchmark/ltx_reuse_worker.py'],stdin=subprocess.DEVNULL,"
            "stdout=open('/root/benchmark/reuse.log','ab'),stderr=subprocess.STDOUT,start_new_session=True); print(p.pid)")
    state["service_launch_claimed_at"] = time.time()
    base.save(base.STATE, state)
    state["service_pid"] = int(base.remote(connection, code).strip())
    state["cases"] = {}
    base.save(base.STATE, state)
    for case, mode, warmup in CASES:
        wait_service(connection, "ready", case, state["deadline"] - 240)
        state["generation_submissions"] += 1
        state["cases"][case] = {"mode": mode, "warmup": warmup, "submitted_at": time.time(), "status": "submission_claimed"}
        base.save(base.STATE, state)
        start = time.monotonic()
        code = ("import json; from pathlib import Path; p=Path('/root/benchmark')/" + repr(case + ".request.json") + "; "
                "f=p.open('x'); json.dump(" + repr({"run_id": RUN_ID, "case": case}) + ",f); f.close()")
        base.remote(connection, code)
        wait_service(connection, "completed", case, state["deadline"] - 180)
        base.transfer(connection, [output_id(case) + ".mp4", output_id(case) + ".json"], False)
        state["cases"][case].update(end_to_end_seconds=time.monotonic() - start, downloaded_at=time.time(), status="downloaded")
        base.save(base.STATE, state)
        path = LEASE / (output_id(case) + ".mp4")
        result = json.loads((LEASE / (output_id(case) + ".json")).read_text())
        if hashlib.sha256(path.read_bytes()).hexdigest() != result["output_sha256"]:
            raise ValueError("Video download hash mismatch")
        subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(path), "-f", "null", "-"], check=True, timeout=60)
        state["cases"][case]["decode_verified"] = True
        base.save(base.STATE, state)
        base.remote(connection, "from pathlib import Path; (Path('/root/benchmark')/" + repr(case + ".exported") + ").touch(exist_ok=False)")
        print(json.dumps({"case": case, "processing_seconds": result["processing_seconds"],
                          "end_to_end_seconds": state["cases"][case]["end_to_end_seconds"],
                          "transformer_build_count": result["transformer_build_count"]}), flush=True)
    base.transfer(connection, ["reuse.log", "gpu-samples.csv", "ltx-source/uv.lock"], False)
    state["decode_verified"] = True
    base.save(base.STATE, state)
    base.close(env_file)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("arm", "guard", "attach", "run", "close", "status"))
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--pod-id")
    args = parser.parse_args()
    if args.action == "attach":
        base.attach(args.env_file, args.pod_id)
    elif args.action in ("arm", "run"):
        globals()[args.action](args.env_file)
    elif args.action == "status":
        base.observe(args.env_file)
        print((LEASE / "allocation-observation.json").read_text())
    else:
        getattr(base, args.action)(args.env_file)
