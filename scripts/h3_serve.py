"""Start the pinned native H3 service on our explicitly allocated H100 Pod.

Run remotely with /opt/sglang/bin/python. Does not submit a generation request.
"""

import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import time

SOURCE = "408d2334c34d387a36a26398dff9a8f004328344"
REVISION = "42ed227ee7df40d41602854ae760620d6eb651fe"
ROOT = Path("/root/benchmark")


def main():
    guard = json.loads((ROOT / "guard-ready.json").read_text())
    if not guard.get("read_own_pod_verified") or guard["deadline"] - time.time() < 600:
        raise RuntimeError("Verified guard and at least ten minutes remaining required")
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
    record["command"] = command
    (ROOT / "runtime.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record), flush=True)
    env = dict(os.environ, PATH="/opt/sglang/bin:/usr/local/cuda/bin:/usr/local/bin:/usr/bin:/bin",
               HF_HOME=str(ROOT / "hf"), HF_HUB_DOWNLOAD_TIMEOUT="60")
    # The service needs public model access, not a cloud account or Pod control key.
    env.pop("RUNPOD_API_KEY", None)
    os.execve(command[0], command, env)


if __name__ == "__main__":
    main()
