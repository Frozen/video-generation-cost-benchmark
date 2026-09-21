"""On-Pod preparation and exactly one native LTX request; no cloud mutations."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs, urlparse

from ltx_config import FILES, FPS, FRAMES, HEIGHT, MODEL, REVISION, RUN_ID, SOURCE, WIDTH, validate_prompt

BASE = Path("/root/benchmark")
SRC = BASE / "ltx-source"
MODELS = BASE / "models"


def save(name, data):
    path = BASE / name
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n")
    temporary.chmod(0o600)
    os.replace(temporary, path)


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def download_file(item):
    """Fetch one authorized object; never receives the HF account token."""
    name, url = item
    if name not in FILES:
        raise ValueError("Unreviewed weight file")
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "us.aws.cdn.hf.co":
        raise ValueError("Unreviewed download destination")
    if not parse_qs(parsed.query).get("Signature"):
        raise ValueError("Expected temporary signed object URL")
    path = MODELS / name
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".download")
    # URL is a file-scoped temporary credential: stdin only, never argv or logs.
    config = "url = " + json.dumps(url) + "\n"
    r = subprocess.run(["curl", "-q", "--config", "-", "--fail", "--silent", "--show-error",
                        "--proto", "=https", "--max-redirs", "0", "--connect-timeout", "20",
                        "--max-time", "900", "--max-filesize", str(FILES[name][0]), "--output", str(temporary)],
                       input=config, text=True, capture_output=True, timeout=910)
    if r.returncode:
        raise RuntimeError("Object download failed for " + name + "; curl exit " + str(r.returncode))
    os.replace(temporary, path)


def frozen_natten_requirement(lock_path):
    import tomllib
    packages = tomllib.loads(lock_path.read_text()).get("package", [])
    matches = [package for package in packages if package.get("name") == "natten"]
    if len(matches) != 1 or matches[0].get("version") != "0.21.7+torch2130cu132":
        raise ValueError("Frozen NATTEN version mismatch")
    package = matches[0]
    if package.get("source") != {"registry": "https://whl.natten.org/"}:
        raise ValueError("Frozen NATTEN registry mismatch")
    url = ("https://github.com/SHI-Labs/NATTEN/releases/download/v0.21.7/"
           "natten-0.21.7%2Btorch2130cu132-cp312-cp312-linux_x86_64.whl")
    wheels = [wheel for wheel in package.get("wheels", []) if wheel.get("url") == url]
    manifest = json.loads((lock_path.parent / ".natten-wheel.json").read_text())
    if (manifest.get("name"), manifest.get("version"), manifest.get("url"), manifest.get("size")) != (
            "natten", "0.21.7+torch2130cu132", url, 203625872):
        raise ValueError("Reviewed NATTEN wheel manifest mismatch")
    sha = manifest.get("sha256", "")
    if len(wheels) != 1 or not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{64}", sha):
        raise ValueError("Missing reviewed CPython 3.12 Linux x86_64 NATTEN wheel hash")
    if wheels[0].get("hash") not in (None, "sha256:" + sha):
        raise ValueError("NATTEN lock and reviewed manifest hash disagree")
    return "natten @ " + url + " --hash=sha256:" + sha + "\n"


def prepare(frozen=False):
    if frozen and not (SRC / "uv.lock").is_file():
        raise ValueError("Frozen preparation requires the supplied uv.lock")
    requirement = frozen_natten_requirement(SRC / "uv.lock") if frozen else None
    if frozen and subprocess.check_output(["uv", "--version"], text=True).split()[:2] != ["uv", "0.12.17"]:
        raise ValueError("Frozen preparation requires uv 0.12.17")
    started = time.time()
    save("prepare-status.json", {"phase": "installing", "started_at": started})
    env = dict(os.environ, UV_CACHE_DIR=str(BASE / "uv-cache"), HF_HOME=str(BASE / "hf-cache"),
               HF_HUB_DISABLE_PROGRESS_BARS="1", HF_HUB_DOWNLOAD_TIMEOUT="60")
    sync = ["uv", "sync", "--no-dev", "--package", "ltx-pipelines"]
    if frozen:
        env["UV_PYTHON"] = "3.12"
        sync.append("--frozen")
    subprocess.run(sync, cwd=SRC, env=env, check=True)
    python = str(SRC / ".venv/bin/python")
    subprocess.run([python, "-c", "import torch; assert torch.__version__.startswith('2.13.0'); assert torch.cuda.device_count()==1; print(torch.__version__)"], check=True)
    if frozen:
        subprocess.run([python, "-c", "import sys; assert sys.version_info[:2] == (3, 12)"], check=True)
        subprocess.run(["uv", "pip", "install", "--python", python, "--no-deps", "--require-hashes",
                        "--reinstall-package", "natten", "--requirement", "-"],
                       input=requirement, text=True, env=env, check=True)
    else:
        subprocess.run(["uv", "pip", "install", "--python", python, "--no-deps", "--find-links",
                        "https://whl.natten.org", "natten==0.21.7+torch2130cu132"], env=env, check=True)
    with (BASE / "dependencies.txt").open("w") as out:
        subprocess.run(["uv", "pip", "freeze", "--python", python], stdout=out, check=True)
    save("prepare-status.json", {"phase": "downloading", "started_at": started, "download_started_at": time.time()})
    links_path = BASE / "download-links.json"
    links = json.loads(links_path.read_text())
    if set(links) != set(FILES):
        raise ValueError("Download links do not match the reviewed six-file manifest")
    downloaded_at = time.monotonic()
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(download_file, links.items()))
    finally:
        links_path.unlink()
    download_seconds = time.monotonic() - downloaded_at
    del links
    save("prepare-status.json", {"phase": "hash_verification", "started_at": started,
                                "download_seconds": download_seconds})
    verified = []
    for name, (size, expected) in FILES.items():
        path = MODELS / name
        if path.stat().st_size != size or digest(path) != expected:
            raise ValueError("Weight integrity mismatch: " + name)
        verified.append({"file": name, "bytes": size, "sha256": expected})
    subprocess.run([python, "-c", "from ltx_pipelines.distilled import DistilledPipeline; import natten; print(natten.__version__)"], check=True)
    save("prepare-status.json", {"phase": "ready", "started_at": started, "ready_at": time.time(),
                                "download_seconds": download_seconds, "verified_files": verified,
                                "source_revision": SOURCE, "model_revision": REVISION,
                                "frozen": frozen, "uv_lock_sha256": digest(SRC / "uv.lock") if frozen else None,
                                "natten_wheel_manifest_sha256": digest(SRC / ".natten-wheel.json") if frozen else None})


def generate():
    script_started = time.monotonic()
    # Exclusive claim prevents accidental second generation even if SSH observation fails.
    with (BASE / "generation-claim.json").open("x") as out:
        json.dump({"run_id": RUN_ID, "started_at": time.time()}, out)
    save("generation-status.json", {"phase": "imports", "started_at": time.time()})
    import torch
    from ltx_core.model.video_vae import AUTO_TILING, get_video_chunks_number
    from ltx_pipelines.distilled import DistilledPipeline
    from ltx_pipelines.utils.constants import DISTILLED_SIGMA_VALUES, STAGE_2_DISTILLED_SIGMA_VALUES
    from ltx_pipelines.utils.media_io import encode_video
    from ltx_pipelines.utils.model_paths import ModelPaths

    prompt = validate_prompt(json.loads((BASE / "request.json").read_text())["prompt"])
    names = list(FILES)
    model_paths = ModelPaths.from_split(transformer_path=str(MODELS / names[0]),
        text_encoder_path=str(MODELS / names[1]), video_vae_path=str(MODELS / names[2]),
        audio_vae_path=str(MODELS / names[3]), duration_head_path=str(MODELS / names[4]))
    pipeline = DistilledPipeline(model_paths=model_paths, spatial_upsampler_path=str(MODELS / names[5]), loras=())
    stages = []

    class TimedBlock:
        def __init__(self, name, block):
            self.name, self.block = name, block
        def __getattr__(self, name):
            return getattr(self.block, name)
        def __call__(self, *args, **kwargs):
            torch.cuda.synchronize()
            start = time.monotonic()
            value = self.block(*args, **kwargs)
            torch.cuda.synchronize()
            stages.append({"stage": self.name, "seconds": time.monotonic() - start})
            print(json.dumps(stages[-1]), flush=True)
            return value

    for name in ("prompt_encoder", "stage", "upsampler", "audio_decoder"):
        setattr(pipeline, name, TimedBlock(name, getattr(pipeline, name)))
    save("generation-status.json", {"phase": "generating", "started_at": time.time()})
    torch.cuda.reset_peak_memory_stats()
    torch.cuda.synchronize()
    start = time.monotonic()
    with torch.inference_mode():
        output = pipeline(prompt=prompt, seed=42, width=WIDTH, height=HEIGHT, num_frames=FRAMES,
                          frame_rate=FPS, images=[], enhance_prompt=False, tiling_config=AUTO_TILING)
        torch.cuda.synchronize()
        returned = time.monotonic()
        path = BASE / (RUN_ID + ".mp4")
        encode_video(video=output.video, fps=FPS, audio=output.audio, output_path=str(path),
                     video_chunks_number=get_video_chunks_number(output.num_frames, output.tiling_config))
    torch.cuda.synchronize()
    finished = time.monotonic()
    result = {"phase": "completed", "run_id": RUN_ID, "completed_at": time.time(),
        "processing_seconds": finished - start, "script_seconds": finished - script_started,
        "pipeline_return_seconds": returned - start, "lazy_video_decode_and_encode_seconds": finished - returned,
        "stages_including_weight_loading": stages, "warmup_requests": 0,
        "source_revision": SOURCE, "model_revision": REVISION, "torch": torch.__version__,
        "cuda": torch.version.cuda, "gpu": torch.cuda.get_device_name(), "gpu_count": torch.cuda.device_count(),
        "peak_allocated_bytes": torch.cuda.max_memory_allocated(), "peak_reserved_bytes": torch.cuda.max_memory_reserved(),
        "stage_1_sigmas": DISTILLED_SIGMA_VALUES, "stage_2_sigmas": STAGE_2_DISTILLED_SIGMA_VALUES,
        "width": WIDTH, "height": HEIGHT, "frames": FRAMES, "fps": FPS, "seed": 42,
        "precision": "BF16", "quantization": None, "compile": False, "offload": "none",
        "diffvae_mode": "chunked_eager", "prompt_enhancement": False,
        "output_bytes": path.stat().st_size, "output_sha256": digest(path)}
    save("generation-status.json", result)
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "generate"))
    parser.add_argument("--frozen", action="store_true", help="Require the supplied lock for preparation")
    args = parser.parse_args()
    action = args.action
    if args.frozen and action != "prepare":
        parser.error("--frozen applies only to prepare")
    try:
        prepare(frozen=args.frozen) if action == "prepare" else generate()
    except Exception as exc:
        save(action + "-failure.json", {"phase": "failed", "error_type": type(exc).__name__, "at": time.time()})
        traceback.print_exc()
        raise SystemExit(1)
