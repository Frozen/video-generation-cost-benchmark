"""On-Pod preparation and exactly one native LTX request; no cloud mutations."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import traceback

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


def prepare():
    started = time.time()
    save("prepare-status.json", {"phase": "installing", "started_at": started})
    env = dict(os.environ, UV_CACHE_DIR=str(BASE / "uv-cache"), HF_HOME=str(BASE / "hf-cache"),
               HF_HUB_DISABLE_PROGRESS_BARS="1", HF_HUB_DOWNLOAD_TIMEOUT="60")
    subprocess.run(["uv", "sync", "--no-dev", "--package", "ltx-pipelines"], cwd=SRC, env=env, check=True)
    python = str(SRC / ".venv/bin/python")
    subprocess.run([python, "-c", "import torch; assert torch.__version__.startswith('2.13.0'); assert torch.cuda.device_count()==1; print(torch.__version__)"], check=True)
    subprocess.run(["uv", "pip", "install", "--python", python, "--no-deps", "--find-links",
                    "https://whl.natten.org", "natten==0.21.7+torch2130cu132"], env=env, check=True)
    with (BASE / "dependencies.txt").open("w") as out:
        subprocess.run(["uv", "pip", "freeze", "--python", python], stdout=out, check=True)
    save("prepare-status.json", {"phase": "downloading", "started_at": started, "download_started_at": time.time()})
    token_path = BASE / "hf-token"
    env["HF_TOKEN"] = token_path.read_text().strip()
    downloaded_at = time.monotonic()
    subprocess.run([str(SRC / ".venv/bin/hf"), "download", MODEL, *FILES, "--revision", REVISION,
                    "--local-dir", str(MODELS), "--max-workers", "4"], env=env, check=True)
    download_seconds = time.monotonic() - downloaded_at
    del env["HF_TOKEN"]
    token_path.unlink()
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
                                "source_revision": SOURCE, "model_revision": REVISION})


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
    action = parser.parse_args().action
    try:
        prepare() if action == "prepare" else generate()
    except Exception as exc:
        save(action + "-failure.json", {"phase": "failed", "error_type": type(exc).__name__, "at": time.time()})
        traceback.print_exc()
        raise SystemExit(1)
