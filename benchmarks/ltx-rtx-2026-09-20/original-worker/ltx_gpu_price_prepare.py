"""Install the frozen paired-GPU environment and verify six LTX weights."""

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import time
import traceback
import zipfile

from load_window import sha256, verify_checkout, verify_guard
from ltx_config import FILES, SOURCE
from ltx_worker import download_file, save

BASE = Path("/root/benchmark")


def prepare():
    if sys.version_info[:2] != (3, 12):
        raise ValueError("Pinned Python 3.12 image required")
    plan = json.loads((BASE / "ltx-cost-plan.json").read_text())
    lease = json.loads((BASE / "lease.json").read_text())
    verify_guard(BASE / "guard-ready.json", lease["deadline"])
    started = time.time()
    save("prepare-status.json", {"phase": "installing", "started_at": started})
    for name, expected in plan["preparation_files"].items():
        if sha256(BASE / name) != expected:
            raise ValueError("Preparation artifact mismatch: " + name)
    with tarfile.open(BASE / "ltx-audio-source.tar.gz") as archive:
        if any(m.name != "ltx-source" and not m.name.startswith("ltx-source/") for m in archive.getmembers()):
            raise ValueError("Unexpected source archive root")
        archive.extractall(BASE, filter="data")
    source = BASE / "ltx-source"
    verify_checkout(source, SOURCE)
    if sha256(source / "uv.lock") != plan["dependency_lock_sha256"]:
        raise ValueError("Dependency lock mismatch")
    with zipfile.ZipFile(BASE / "ltx-audio-uv-linux.whl") as wheel:
        data = wheel.read("uv-0.12.17.data/scripts/uv")
    uv = BASE / "uv-pinned"
    uv.write_bytes(data)
    uv.chmod(0o700)
    env = dict(os.environ, UV_CACHE_DIR=str(BASE / "uv-cache"), HF_HOME=str(BASE / "hf-cache"))
    env.pop("RUNPOD_API_KEY", None)
    subprocess.run([str(uv), "sync", "--frozen", "--no-dev", "--package", "ltx-pipelines",
                    "--python", sys.executable, "--no-python-downloads"],
                   cwd=source, env=env, check=True)
    binary = plan["natten"]
    wheel = BASE / binary["name"]
    subprocess.run(["curl", "-q", "--fail", "--silent", "--show-error", "--location",
                    "--proto", "=https", "--proto-redir", "=https", "--connect-timeout", "20",
                    "--max-time", "180", binary["browser_download_url"], "--output", str(wheel)], check=True)
    if wheel.stat().st_size != binary["size"] or "sha256:" + sha256(wheel) != binary["digest"]:
        raise ValueError("Official NATTEN wheel mismatch")
    python = source / ".venv/bin/python"
    subprocess.run([str(uv), "pip", "install", "--python", str(python), "--no-deps", str(wheel)], env=env, check=True)
    subprocess.run([str(python), "-c", "import torch,natten;from ltx_pipelines.distilled import DistilledPipeline;"
                    "assert torch.__version__=='2.13.0+cu132';assert torch.version.cuda=='13.2';"
                    "assert torch.cuda.device_count()==1;assert torch.cuda.get_device_name()==" + repr(plan["gpu_id"]) + ";"
                    "assert tuple(torch.cuda.get_device_capability())==" + repr(tuple(plan["compute_capability"])) + ";"
                    "assert natten.__version__.split('+')[0]=='0.21.7'"], env=env, check=True)
    # Exercise the installed native neighborhood-attention kernel before downloading weights.
    subprocess.run([str(python), "-c", "import torch,natten;"
                    "q=torch.randn(1,4,4,4,2,64,device='cuda',dtype=torch.bfloat16);"
                    "out=natten.na3d(q,q,q,kernel_size=(3,3,3));torch.cuda.synchronize();"
                    "assert out.shape==q.shape and torch.isfinite(out).all();"
                    "print('Native NATTEN GPU probe passed',torch.cuda.get_device_capability())"], env=env, check=True)
    with (BASE / "dependencies.txt").open("w") as target:
        subprocess.run([str(uv), "pip", "freeze", "--python", str(python)], stdout=target, check=True)
    save("prepare-status.json", {"phase": "downloading", "started_at": started})
    links_path = BASE / "download-links.json"
    links = json.loads(links_path.read_text())
    if set(links) != set(FILES):
        raise ValueError("Weight links differ from the pinned manifest")
    download_start = time.monotonic()
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(download_file, links.items()))
    finally:
        links_path.unlink()
    download_seconds = time.monotonic() - download_start
    del links
    save("prepare-status.json", {"phase": "verifying", "started_at": started})
    for name, (size, digest) in FILES.items():
        path = BASE / "models" / name
        if path.stat().st_size != size or sha256(path) != digest:
            raise ValueError("LTX weight integrity mismatch")
    verify_checkout(source, SOURCE)
    save("prepare-status.json", {"phase": "ready", "started_at": started, "ready_at": time.time(),
                                 "download_seconds": download_seconds, "verified_files": len(FILES),
                                 "dependency_lock_sha256": plan["dependency_lock_sha256"]})


if __name__ == "__main__":
    try:
        prepare()
    except Exception as exc:
        save("prepare-failure.json", {"phase": "failed", "error_type": type(exc).__name__, "at": time.time()})
        traceback.print_exc()
        raise SystemExit(1)
