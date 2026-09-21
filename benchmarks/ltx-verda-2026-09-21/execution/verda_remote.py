"""One-shot Verda adapter; frozen reproduction code is never rewritten.

Run prepare, then run, in the pinned Python 3.12 container with /root/benchmark
bound from the host. The controller must atomically refresh guard-heartbeat.json.
Neither this program nor the VM receives provider/HF account credentials.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import signal
import subprocess
import sys
import tarfile
import threading
import time
import traceback
from urllib.parse import parse_qs, urlparse
import uuid
import zipfile


BASE = Path("/root/benchmark")
REPRODUCTION = BASE / "reproduction"
SOURCE = BASE / "ltx-source"
PYTHON = SOURCE / ".venv/bin/python"
MANIFEST = BASE / "workload-manifest.json"
LOCK_SHA256 = "dd5d9b68281ab8536e245cffe236388f4ed73c872442705718e3f3baf3a46bf1"
PLAN_SHA256 = "5000869fe6c74a605727caf5c4276c248d7dcf84f4096dfb1b60eb27dd92bcbd"
RESIDENT_SHA256 = "a55d318419c1617c380074fc77f5f7c6b8f2b19f1a29586bcb813fb47ab28c25"
GPU_NAME = "NVIDIA RTX PRO 6000 Blackwell Server Edition"
SUITE_SECONDS = 1230
PREPARATION_MARGIN = 60
HEARTBEAT_SECONDS = 60


class AdapterError(RuntimeError):
    """Only fixed, non-sensitive reason codes belong in this exception."""


def require(condition, reason):
    if not condition:
        raise AdapterError(reason)


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def load(path):
    return json.loads(Path(path).read_bytes())


def save(name, data):
    path = BASE / name
    temporary = path.with_name(path.name + ".tmp-" + str(os.getpid()))
    with temporary.open("w", encoding="utf-8") as target:
        os.chmod(temporary, 0o600)
        json.dump(data, target, indent=2, allow_nan=False)
        target.write("\n")
        target.flush()
        os.fsync(target.fileno())
    os.replace(temporary, path)


def exclusive_json(path, data):
    """Publish complete JSON atomically without replacing an existing claim."""
    temporary = path.with_name(path.name + ".tmp-" + str(os.getpid()))
    try:
        with temporary.open("x", encoding="utf-8") as target:
            os.chmod(temporary, 0o600)
            json.dump(data, target, allow_nan=False)
            target.write("\n")
            target.flush()
            os.fsync(target.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def failure(name, exc):
    # Never serialize exception messages, locals, commands, source lines or URLs.
    data = {"phase": "failed", "at": time.time(), "error_type": type(exc).__name__,
            "reason": str(exc) if isinstance(exc, AdapterError) else "operation_failed",
            "frames": [{"file": Path(frame.filename).name, "line": frame.lineno,
                        "function": frame.name} for frame in traceback.extract_tb(exc.__traceback__)]}
    save(name, data)
    return data


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def instance_uuid(value):
    parsed = uuid.UUID(value)
    require(str(parsed) == value and parsed.int != 0, "invalid_instance_uuid")
    return value


class Lease:
    def __init__(self, args, cutoff):
        self.hostname = args.hostname
        self.instance_id = instance_uuid(args.instance_id)
        self.deadline = args.deadline
        require(finite(self.deadline) and self.deadline > 0, "invalid_deadline")
        self.cutoff = cutoff
        self.monotonic_cutoff = time.monotonic() + cutoff - time.time()
        self.last_receipt_epoch = None
        self.last_receipt_monotonic = None
        self.lock = threading.Lock()

    def check(self):
        with self.lock:
            return self._check()

    def _check(self):
        now, monotonic = time.time(), time.monotonic()
        require(now < self.cutoff and monotonic < self.monotonic_cutoff,
                "phase_time_bound_reached")
        receipt = load(BASE / "guard-heartbeat.json")
        epoch = receipt.get("heartbeat_epoch")
        require(receipt.get("provider") == "verda"
                and receipt.get("instance_id") == self.instance_id
                and receipt.get("hostname") == self.hostname
                and receipt.get("deadline") == self.deadline
                and receipt.get("read_own_instance_verified") is True
                and receipt.get("status") == "watching"
                and type(receipt.get("guard_pid")) is int and receipt["guard_pid"] > 0,
                "external_guard_identity_or_state_invalid")
        require(finite(epoch) and -5 <= now - epoch <= HEARTBEAT_SECONDS,
                "external_guard_heartbeat_stale")
        if self.last_receipt_epoch is None or epoch > self.last_receipt_epoch:
            self.last_receipt_epoch = epoch
            self.last_receipt_monotonic = monotonic - max(0, now - epoch)
        else:
            require(epoch == self.last_receipt_epoch, "external_guard_heartbeat_regressed")
        require(monotonic - self.last_receipt_monotonic <= HEARTBEAT_SECONDS,
                "external_guard_heartbeat_stale")
        # guard_pid is on the controller's Mac, not in this container's PID namespace.
        return receipt


def frozen_inputs(args):
    original_path = REPRODUCTION / "evidence/original-plan.json"
    resident_path = REPRODUCTION / "evidence/resident.json"
    require(digest(original_path) == PLAN_SHA256 and digest(resident_path) == RESIDENT_SHA256,
            "baseline_evidence_hash_mismatch")
    original, baseline = load(original_path), load(resident_path)
    for name, expected in original["worker_sha256"].items():
        require(digest(REPRODUCTION / "original-worker" / name) == expected,
                "frozen_worker_hash_mismatch")
    plan = load(MANIFEST)
    require(isinstance(plan.get("run_id"), str)
            and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", plan["run_id"])
            and plan["run_id"] != baseline["run_id"], "fresh_run_identity_required")
    expected = json.loads(json.dumps(baseline))
    expected["run_id"] = plan["run_id"]
    expected["limits"]["shutdown_deadline_epoch"] = args.deadline
    expected["limits"]["admission_deadline_epoch"] = (
        args.deadline - baseline["limits"]["request_bound_seconds"]
        - baseline["limits"]["export_reserve_seconds"])
    require(plan == expected, "workload_differs_from_frozen_baseline")
    require(2 * plan["limits"]["warmup_bound_seconds"]
            + len(plan["requests"]) * plan["limits"]["request_bound_seconds"]
            + plan["limits"]["export_reserve_seconds"] == SUITE_SECONDS,
            "frozen_suite_bound_mismatch")
    require(plan["profile"]["gpu_name"] == GPU_NAME, "frozen_gpu_mismatch")
    return original, plan, digest(MANIFEST)


def verify_transport(original, preparing):
    transport = load(BASE / "transport-manifest.json")
    require(isinstance(transport, dict) and set(transport) == {"files"}
            and isinstance(transport["files"], dict), "invalid_transport_manifest")
    files = transport["files"]
    required = {"verda_remote.py", "ltx-source.tar.gz", "uv-linux.whl",
                original["natten"]["name"], "workload-manifest.json", "download-links.json",
                "reproduction/evidence/original-plan.json", "reproduction/evidence/resident.json",
                "reproduction/evidence/uv.lock"}
    required.update("reproduction/original-worker/" + name for name in original["worker_sha256"])
    require(required <= set(files), "transport_missing_required_artifacts")
    for name, expected in files.items():
        relative = PurePosixPath(name)
        require(not relative.is_absolute() and ".." not in relative.parts
                and relative.as_posix() == name and name not in ("", ".")
                and isinstance(expected, str) and re.fullmatch(r"[0-9a-f]{64}", expected),
                "invalid_transport_entry")
        path = BASE / name
        require(path.resolve().is_relative_to(BASE)
                and not any((BASE.joinpath(*relative.parts[:index])).is_symlink()
                            for index in range(1, len(relative.parts) + 1)),
                "transport_symlink_or_escape")
        if not preparing and name == "download-links.json":
            require(not path.exists(), "signed_links_not_removed")
            continue
        require(path.is_file() and digest(path) == expected, "transport_hash_mismatch")
    require(digest(REPRODUCTION / "evidence/uv.lock") == LOCK_SHA256,
            "evidence_dependency_lock_mismatch")
    require(digest(BASE / "uv-linux.whl") == original["preparation_files"]["ltx-audio-uv-linux.whl"],
            "uv_wheel_hash_mismatch")
    wheel = BASE / original["natten"]["name"]
    require(wheel.stat().st_size == original["natten"]["size"]
            and "sha256:" + digest(wheel) == original["natten"]["digest"],
            "natten_wheel_hash_mismatch")
    return digest(BASE / "transport-manifest.json")


def clean_environment():
    allowed = ("PATH", "HOME", "LANG", "LC_ALL", "LD_LIBRARY_PATH", "CUDA_HOME", "CUDA_PATH",
               "CUDA_VISIBLE_DEVICES", "NVIDIA_VISIBLE_DEVICES", "NVIDIA_DRIVER_CAPABILITIES")
    environment = {key: os.environ[key] for key in allowed if key in os.environ}
    environment.update(PYTHONUNBUFFERED="1", PYTHONDONTWRITEBYTECODE="1",
                       UV_CACHE_DIR=str(BASE / "uv-cache"), HF_HOME=str(BASE / "hf-cache"))
    return environment


def command(argv, lease, *, cwd=None, stdout=None):
    lease.check()
    subprocess.run([str(part) for part in argv], cwd=cwd, env=clean_environment(),
                   stdin=subprocess.DEVNULL, stdout=stdout, check=True)
    lease.check()


def child_watchdog(lease, parent_pid, phase):
    require(os.getpgrp() == os.getpid() and os.getppid() == parent_pid,
            "guarded_child_supervisor_required")

    def watch():
        while True:
            try:
                require(os.getppid() == parent_pid, "supervisor_disappeared")
                lease.check()
            except BaseException as exc:
                try:
                    failure(phase + "-watchdog-failure.json", exc)
                    if phase == "prepare":
                        (BASE / "download-links.json").unlink(missing_ok=True)
                finally:
                    os.killpg(os.getpgrp(), signal.SIGKILL)
            time.sleep(1)

    threading.Thread(target=watch, name="external-guard-watchdog", daemon=True).start()


def prepare_child(args, lease):
    started = time.time()
    save("prepare-status.json", {"phase": "verifying_transport", "started_at": started})
    original, plan, manifest_digest = frozen_inputs(args)
    transport_digest = verify_transport(original, True)
    save("transport-verification.json", {"transport_sha256": transport_digest,
                                         "verified_at": time.time(), "all_uploaded_files_verified": True})
    require(not SOURCE.exists(), "source_already_exists_no_prepare_retry")
    with tarfile.open(BASE / "ltx-source.tar.gz") as archive:
        members = archive.getmembers()
        require(all(PurePosixPath(member.name).parts
                    and PurePosixPath(member.name).parts[0] == "ltx-source"
                    and ".." not in PurePosixPath(member.name).parts
                    and not PurePosixPath(member.name).is_absolute() for member in members),
                "invalid_source_archive_root")
        archive.extractall(BASE, filter="data")
    require((SOURCE / ".git").is_dir() and not (SOURCE / ".git").is_symlink(),
            "source_git_metadata_required")
    sys.path.insert(0, str(REPRODUCTION / "original-worker"))
    from load_window import verify_checkout
    from ltx_config import FILES, SOURCE as SOURCE_REVISION
    from ltx_worker import download_file

    require(SOURCE_REVISION == original["source_revision"], "source_revision_contract_mismatch")
    verify_checkout(SOURCE, SOURCE_REVISION)
    require(digest(SOURCE / "uv.lock") == LOCK_SHA256, "source_dependency_lock_mismatch")
    with zipfile.ZipFile(BASE / "uv-linux.whl") as wheel:
        executable = wheel.read("uv-0.12.17.data/scripts/uv")
    uv = BASE / "uv-pinned"
    with uv.open("xb") as target:
        target.write(executable)
    uv.chmod(0o700)
    lease.check()
    version = subprocess.check_output([str(uv), "--version"], env=clean_environment(), text=True)
    require(version.strip().split()[:2] == ["uv", "0.12.17"], "uv_version_mismatch")
    save("prepare-status.json", {"phase": "installing", "started_at": started})
    command([uv, "sync", "--frozen", "--no-dev", "--package", "ltx-pipelines",
             "--python", "python3.12", "--no-python-downloads"], lease, cwd=SOURCE)
    command([uv, "pip", "install", "--python", PYTHON, "--no-deps",
             BASE / original["natten"]["name"]], lease)
    # This is the original real native NATTEN probe, before any model download.
    probe = (
        "import json,sys,torch,natten;from ltx_pipelines.distilled import DistilledPipeline;"
        "assert sys.version_info[:2]==(3,12);"
        "assert torch.__version__=='2.13.0+cu132';assert torch.version.cuda=='13.2';"
        "assert torch.cuda.device_count()==1;"
        "assert torch.cuda.get_device_name()==" + repr(GPU_NAME) + ";"
        "assert tuple(torch.cuda.get_device_capability())==(12,0);"
        "assert natten.__version__.split('+')[0]=='0.21.7';"
        "q=torch.randn(1,4,4,4,2,64,device='cuda',dtype=torch.bfloat16);"
        "out=natten.na3d(q,q,q,kernel_size=(3,3,3));torch.cuda.synchronize();"
        "assert out.shape==q.shape and torch.isfinite(out).all();"
        "print(json.dumps({'python':sys.version.split()[0],'torch':torch.__version__,"
        "'cuda':torch.version.cuda,'natten':natten.__version__,"
        "'gpu_name':torch.cuda.get_device_name(),'capability':torch.cuda.get_device_capability(),"
        "'gpu_total_memory_bytes':torch.cuda.get_device_properties(0).total_memory,"
        "'native_natten_gpu_probe_passed':True}))"
    )
    with (BASE / "runtime-probe.json").open("x") as target:
        command([PYTHON, "-c", probe], lease, stdout=target)
    with (BASE / "dependencies.txt").open("x") as target:
        command([uv, "pip", "freeze", "--python", PYTHON], lease, stdout=target)
    save("prepare-status.json", {"phase": "downloading", "started_at": started})
    links_path = BASE / "download-links.json"
    links = load(links_path)
    require(set(links) == set(FILES), "signed_link_manifest_mismatch")
    for link in links.values():
        parsed = urlparse(link)
        query = parse_qs(parsed.query)
        require(parsed.scheme == "https" and parsed.hostname == "us.aws.cdn.hf.co"
                and not parsed.username and not parsed.password and query.get("Signature")
                and int(query.get("Expires", [0])[0]) > time.time() + 900,
                "signed_link_invalid_or_expiring")
    download_start = time.monotonic()
    try:
        lease.check()
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(download_file, links.items()))
    finally:
        links_path.unlink(missing_ok=True)
    del links
    download_seconds = time.monotonic() - download_start
    save("prepare-status.json", {"phase": "verifying", "started_at": started})
    for name, (size, expected_hash) in FILES.items():
        lease.check()
        path = BASE / "models" / name
        require(path.stat().st_size == size and digest(path) == expected_hash,
                "model_weight_integrity_mismatch")
    verify_checkout(SOURCE, SOURCE_REVISION)
    require(digest(SOURCE / "uv.lock") == LOCK_SHA256, "source_dependency_lock_changed")
    lease.check()
    save("prepare-status.json", {"phase": "ready", "started_at": started, "ready_at": time.time(),
                                 "download_seconds": download_seconds, "verified_files": len(FILES),
                                 "dependency_lock_sha256": LOCK_SHA256,
                                 "transport_sha256": transport_digest, "manifest_sha256": manifest_digest,
                                 "source_revision": SOURCE_REVISION,
                                 "required_suite_seconds": SUITE_SECONDS,
                                 "preparation_margin_seconds": PREPARATION_MARGIN,
                                 "host_ram_fit": "unproven_until_full_frozen_workload"})


def serve_child(args, lease):
    original, plan, manifest_digest = frozen_inputs(args)
    transport_digest = verify_transport(original, False)
    prepared = load(BASE / "prepare-status.json")
    require(prepared.get("phase") == "ready" and prepared.get("manifest_sha256") == manifest_digest
            and prepared.get("transport_sha256") == transport_digest, "matching_preparation_required")
    require(digest(SOURCE / "uv.lock") == LOCK_SHA256, "source_dependency_lock_changed")
    sys.path.insert(0, str(REPRODUCTION / "original-worker"))
    import load_window

    def verify_external_guard(path, deadline):
        require(Path(path) == BASE / "guard-ready.json" and deadline == args.deadline,
                "worker_guard_deadline_mismatch")
        return lease.check()

    # Both the worker's imported reference and wait_for_start's module global now
    # use the truthful external receipt. No guard-ready.json or pod proof is created.
    load_window.verify_guard = verify_external_guard
    import ltx_gpu_price_worker

    require(ltx_gpu_price_worker.required_suite_seconds(plan) == SUITE_SECONDS,
            "worker_suite_bound_mismatch")
    lease.check()
    ltx_gpu_price_worker.serve(MANIFEST, BASE)


class QueueObserver:
    def __init__(self, plan, manifest_digest, lease):
        self.plan, self.manifest_digest, self.lease = plan, manifest_digest, lease
        self.output = BASE / plan["run_id"]
        self.offset = 0
        self.active = None
        self.warmups = []
        self.artifacts = []
        self.started = False
        self.window = None
        self.next_sequence = 0

    def check_active(self):
        if self.active:
            require(time.time() < self.active["wall_cutoff"]
                    and time.monotonic() < self.active["monotonic_cutoff"],
                    self.active["kind"] + "_bound_exceeded")

    def consume(self, record):
        require(record.get("run_id") == self.plan["run_id"]
                and record.get("sequence") == self.next_sequence,
                "unexpected_worker_journal_sequence")
        self.next_sequence += 1
        event = record["event"]
        if event in ("warmup_started", "request_started"):
            require(self.active is None, "overlapping_worker_requests")
            warmup = event == "warmup_started"
            ordinal = len(self.warmups) if warmup else len(self.artifacts)
            if warmup:
                require(record["ordinal"] == ordinal + 1
                        and record["seed"] == self.plan["technical_warmup_seeds"][ordinal],
                        "unexpected_warmup")
            bound = self.plan["limits"]["warmup_bound_seconds" if warmup else "request_bound_seconds"]
            cutoff = record["epoch"] + bound
            self.active = {"kind": "warmup" if warmup else "request", "wall_cutoff": cutoff,
                           "monotonic_cutoff": time.monotonic() + cutoff - time.time(),
                           "identity": record["ordinal"] if warmup else record["request_id"]}
        elif event in ("warmup_finished", "artifact_ready", "request_failed", "request_unresolved"):
            warmup = event == "warmup_finished"
            require(self.active is not None
                    and self.active["kind"] == ("warmup" if warmup else "request")
                    and self.active["identity"] == (record["ordinal"] if warmup else record["request_id"]),
                    "unexpected_worker_completion")
            require(record["epoch"] <= self.active["wall_cutoff"],
                    self.active["kind"] + "_bound_exceeded")
            self.active = None
            if warmup:
                self.warmups.append(record["ordinal"])
            elif event == "artifact_ready":
                self.artifacts.append(record["request_id"])
        elif event == "ready":
            require(not self.started and self.warmups == [1, 2] and self.active is None,
                    "ready_without_both_full_warmups")
            self.lease.check()
            remaining = (len(self.plan["requests"]) * self.plan["limits"]["request_bound_seconds"]
                         + self.plan["limits"]["export_reserve_seconds"])
            require(time.time() + remaining < self.lease.deadline,
                    "insufficient_complete_queue_allowance")
            require(digest(MANIFEST) == self.manifest_digest, "workload_changed_before_start")
            exclusive_json(self.output / "start.json", {"run_id": self.plan["run_id"],
                                                        "manifest_sha256": self.manifest_digest})
            self.started = True
        elif event == "window_finished":
            self.window = record

    def poll(self):
        path = self.output / "events.jsonl"
        if path.exists():
            with path.open("rb") as journal:
                journal.seek(self.offset)
                while True:
                    line = journal.readline()
                    if not line.endswith(b"\n"):
                        break
                    self.consume(json.loads(line))
                    self.offset = journal.tell()
        self.check_active()

    def complete(self):
        self.poll()
        require(self.started and self.active is None and self.warmups == [1, 2]
                and self.artifacts == [item["request_id"] for item in self.plan["requests"]]
                and self.window and self.window["submitted"] == 10
                and self.window["not_submitted"] == 0 and self.window["stop_reason"] == "request_limit",
                "incomplete_ten_artifact_comparison")


def kill_group(child):
    if child is not None:
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        child.wait(timeout=10)


def supervise(args):
    preparing = args.mode == "prepare"
    phase = args.mode
    cutoff = args.deadline - (SUITE_SECONDS + PREPARATION_MARGIN if preparing else 180)
    lease = Lease(args, cutoff)
    lease.check()
    original, plan, manifest_digest = frozen_inputs(args)
    require(time.time() + SUITE_SECONDS + PREPARATION_MARGIN < args.deadline,
            "insufficient_preparation_or_suite_allowance")
    if not preparing:
        require(not (BASE / plan["run_id"]).exists(), "run_already_claimed_no_retry")
        require(load(BASE / "prepare-status.json").get("phase") == "ready", "preparation_not_ready")
    exclusive_json(BASE / (phase + "-claim.json"), {
        "phase": phase, "at": time.time(), "pid": os.getpid(), "provider": "verda",
        "instance_id": args.instance_id, "hostname": args.hostname, "deadline": args.deadline,
        "manifest_sha256": manifest_digest, "run_id": plan["run_id"]})
    args.owns_claim = True
    if preparing:
        save("prepare-status.json", {"phase": "starting", "started_at": time.time(),
                                     "manifest_sha256": manifest_digest})
    child = None
    observer = None if preparing else QueueObserver(plan, manifest_digest, lease)
    try:
        executable = sys.executable if preparing else str(PYTHON)
        child_args = [executable, str(BASE / "verda_remote.py"), "_prepare" if preparing else "_serve",
                      "--hostname", args.hostname, "--instance-id", args.instance_id,
                      "--deadline", str(args.deadline), "--supervisor-pid", str(os.getpid())]
        with (BASE / (phase + ".log")).open("x") as log:
            child = subprocess.Popen(child_args, stdin=subprocess.DEVNULL, stdout=log,
                                     stderr=subprocess.STDOUT, cwd=BASE, env=clean_environment(),
                                     start_new_session=True)
            if not preparing:
                save("run-status.json", {"phase": "running", "started_at": time.time(),
                                         "child_pid": child.pid, "run_id": plan["run_id"],
                                         "manifest_sha256": manifest_digest})
            while True:
                lease.check()
                if observer:
                    observer.poll()
                returncode = child.poll()
                if returncode is not None:
                    require(returncode == 0, "guarded_child_failed")
                    break
                time.sleep(0.25 if observer else 1)
        if preparing:
            require(load(BASE / "prepare-status.json").get("phase") == "ready", "preparation_not_ready")
        else:
            observer.complete()
            save("run-status.json", {"phase": "completed", "completed_at": time.time(),
                                     "run_id": plan["run_id"], "manifest_sha256": manifest_digest,
                                     "warmups_completed": 2, "artifacts_completed": len(observer.artifacts),
                                     "delivery_or_quality_verified": False})
    except BaseException as exc:
        # Kill model/setup subprocesses first; no timeout or uncertain work is retried.
        kill_group(child)
        child = None
        data = failure(phase + "-failure.json", exc)
        save(phase + "-status.json", data)
        raise
    finally:
        kill_group(child)
        if preparing:
            (BASE / "download-links.json").unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "run", "_prepare", "_serve"))
    parser.add_argument("--hostname", required=True)
    parser.add_argument("--instance-id", required=True, type=instance_uuid)
    parser.add_argument("--deadline", required=True, type=float)
    parser.add_argument("--supervisor-pid", type=int)
    args = parser.parse_args()
    os.umask(0o077)
    sys.dont_write_bytecode = True

    def interrupted(signum, frame):
        raise AdapterError("supervisor_interrupted")

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    child = args.mode.startswith("_")
    phase = "prepare" if args.mode in ("prepare", "_prepare") else "run"
    args.owns_claim = False
    try:
        require(sys.version_info[:2] == (3, 12), "pinned_python_312_required")
        if child:
            cutoff = args.deadline - (SUITE_SECONDS + PREPARATION_MARGIN if phase == "prepare" else 180)
            lease = Lease(args, cutoff)
            lease.check()
            child_watchdog(lease, args.supervisor_pid, phase)
            (prepare_child if phase == "prepare" else serve_child)(args, lease)
        else:
            supervise(args)
    except BaseException as exc:
        data = failure(phase + ("-child-failure.json" if child else "-adapter-failure.json"), exc)
        claim_exists = (BASE / (phase + "-claim.json")).exists()
        if not child and not claim_exists:
            save(phase + "-status.json", data)
        if phase == "prepare" and (child or args.owns_claim or not claim_exists):
            (BASE / "download-links.json").unlink(missing_ok=True)
        print(json.dumps({"phase": "failed", "error_type": type(exc).__name__}), flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
