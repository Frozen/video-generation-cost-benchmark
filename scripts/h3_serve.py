"""Start the pinned native H3 service on our explicitly allocated H100 Pod.

Run remotely with /opt/sglang/bin/python. Does not submit a generation request.
"""

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from h3_adapters import ADAPTERS

SOURCE = "408d2334c34d387a36a26398dff9a8f004328344"
REVISION = "42ed227ee7df40d41602854ae760620d6eb651fe"
ROOT = Path("/root/benchmark")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recipe", choices=("base", *ADAPTERS), default="base")
    args = parser.parse_args()
    guard = json.loads((ROOT / "guard-ready.json").read_text())
    minimum_remaining = 600 if args.recipe == "base" else 240
    if not guard.get("read_own_pod_verified") or guard["deadline"] - time.time() < minimum_remaining:
        raise RuntimeError("Verified guard and sufficient rental time required")
    os.kill(guard["pid"], 0)
    actual = subprocess.check_output(
        ["git", "-C", "/sgl-workspace/sglang", "rev-parse", "HEAD"], text=True).strip()
    if actual != SOURCE:
        raise RuntimeError("Runtime source pin mismatch")
    import torch
    import diffusers
    import av

    if not torch.cuda.is_available() or torch.cuda.device_count() != 4:
        raise RuntimeError("Four CUDA devices required")
    versions = {name: importlib.metadata.version(name)
                for name in ("torch", "sglang", "transformers", "diffusers", "av", "huggingface_hub")}
    record = {"source_revision": actual, "model_revision": REVISION, "versions": versions,
              "service_launch_at": time.time(), "python": sys.executable,
              "guard_deadline": guard["deadline"]}
    command = ["/opt/sglang/bin/sglang", "serve", "--model-path", "MiniMaxAI/MiniMax-H3",
               "--revision", REVISION, "--model-variant", "fl2va", "--num-gpus", "4",
               "--tp-size", "2", "--ulysses-degree", "2", "--encoder-parallel", "auto",
               "--performance-mode", "speed", "--enable-torch-compile", "false",
               "--host", "127.0.0.1", "--port", "30010"]
    if args.recipe != "base":
        from huggingface_hub import hf_hub_download
        adapter = ADAPTERS[args.recipe]
        downloaded = Path(hf_hub_download(adapter["repo"], adapter["filename"],
                          revision=adapter["revision"], cache_dir=str(ROOT / "hf/hub")))
        digest = hashlib.sha256()
        with downloaded.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        if downloaded.stat().st_size != adapter["bytes"] or digest.hexdigest() != adapter["sha256"]:
            raise RuntimeError("Adapter checksum or size mismatch")
        command += ["--lora-path", str(downloaded.parent), "--lora-weight-name", adapter["filename"],
                    "--lora-nickname", args.recipe, "--lora-scale", "1.0", "--lora-merge-mode", "auto"]
        if adapter["alpha"] is not None:
            command += ["--lora-alpha", str(adapter["alpha"])]
        record.update(recipe=args.recipe, adapter=adapter, adapter_checksum_verified=True)
    record["command"] = command
    runtime_name = "runtime.json" if args.recipe == "base" else f"runtime-{args.recipe}.json"
    (ROOT / runtime_name).write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record), flush=True)
    env = dict(os.environ, PATH="/opt/sglang/bin:/usr/local/cuda/bin:/usr/local/bin:/usr/bin:/bin",
               HF_HOME=str(ROOT / "hf"), HF_HUB_DOWNLOAD_TIMEOUT="60")
    # The service needs public model access, not a cloud account or Pod control key.
    env.pop("RUNPOD_API_KEY", None)
    os.execve(command[0], command, env)


if __name__ == "__main__":
    main()
