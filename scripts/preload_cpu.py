"""Preload and independently verify frozen H3 artifacts on a CPU-only Pod."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path("/root/benchmark")
VOLUME = Path("/workspace")


def verify_file(path, entry):
    if path.stat().st_size != entry["bytes"]:
        raise ValueError("Artifact size mismatch: " + str(path))
    digest = hashlib.sha256() if entry["hash_kind"] == "sha256" else hashlib.sha1()
    if entry["hash_kind"] == "git_blob_sha1":
        digest.update(("blob " + str(entry["bytes"]) + "\0").encode())
    elif entry["hash_kind"] != "sha256":
        raise ValueError("Unrecognized artifact hash")
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != entry["hash"]:
        raise ValueError("Artifact hash mismatch: " + str(path))


def main():
    guard = json.loads((ROOT / "guard-ready.json").read_text())
    if not guard.get("read_own_pod_verified") or not os.path.ismount(VOLUME):
        raise RuntimeError("Verified deadline and mounted network volume required")
    os.kill(guard["pid"], 0)
    manifest_path = ROOT / "preload-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    state = {"status": "starting", "started_at": time.time(), "verified_files": 0,
             "verified_bytes": 0, "gpu_used": False,
             "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest()}
    status_path = VOLUME / "preload-status.json"

    def save():
        state["updated_at"] = time.time()
        tmp = status_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2) + "\n")
        tmp.replace(status_path)

    env = dict(os.environ, HF_HOME=str(VOLUME / "hf"), HF_CLI_BIN_DIR=str(ROOT / "bin"),
               HF_CLI_PIP_ARGS="--constraint /root/benchmark/hf-constraints.txt",
               HF_HUB_DOWNLOAD_TIMEOUT="60")
    env.pop("RUNPOD_API_KEY", None)

    def run(command):
        remaining = guard["deadline"] - time.time() - 90
        if remaining < 1:
            raise TimeoutError("CPU preload deadline reached")
        return subprocess.run(command, env=env, check=True, timeout=remaining)

    try:
        save()
        installer = ROOT / "hf-install.sh"
        if hashlib.sha256(installer.read_bytes()).hexdigest() != manifest["installer_sha256"]:
            raise ValueError("HF installer checksum mismatch")
        (ROOT / "hf-constraints.txt").write_text("huggingface_hub==1.31.0\n")
        run(["bash", str(installer), "--no-modify-path", "--exclude-skill"])
        hf = str(ROOT / "bin/hf")
        run([hf, "version"])
        help_text = subprocess.check_output([hf, "download", "--help"], env=env, text=True, timeout=30)
        if not all(flag in help_text for flag in ("--cache-dir", "--include", "--revision")):
            raise RuntimeError("Installed HF download interface differs from the plan")
        cache = str(VOLUME / "hf/hub")
        state["status"] = "downloading_base"
        save()
        run([hf, "download", manifest["model_repo"], "--revision", manifest["revision"],
             "--include", "FL2VA/*", "--cache-dir", cache])
        for recipe, adapter in manifest["adapters"].items():
            state["status"] = "downloading_" + recipe
            save()
            run([hf, "download", adapter["repo"], adapter["filename"], "--revision", adapter["revision"],
                 "--cache-dir", cache])
        state["status"] = "verifying_checksums"
        save()
        entries = [(manifest["model_repo"], manifest["revision"], entry) for entry in manifest["files"]]
        entries += [(adapter["repo"], adapter["revision"], {"path": adapter["filename"],
                     "bytes": adapter["bytes"], "hash_kind": "sha256", "hash": adapter["sha256"]})
                    for adapter in manifest["adapters"].values()]
        for repo, revision, entry in entries:
            if time.time() >= guard["deadline"] - 60:
                raise TimeoutError("Verification exceeded its allowance")
            snapshot = VOLUME / "hf/hub" / ("models--" + repo.replace("/", "--")) / "snapshots" / revision
            verify_file(snapshot / entry["path"], entry)
            state["verified_files"] += 1
            state["verified_bytes"] += entry["bytes"]
            save()
        state.update(status="verified", completed_at=time.time(), cache_root=str(VOLUME / "hf/hub"))
        save()
    except Exception as exc:
        state.update(status="failed", error_type=type(exc).__name__)
        save()
        raise


if __name__ == "__main__":
    main()
