"""Four explicit requests: one short technical warmup and one measure per mode."""

import gc
import hashlib
import json
from pathlib import Path
import time
import traceback

from ltx_config import FILES, FPS, FRAMES, HEIGHT, REVISION, SOURCE, WIDTH, validate_prompt
from ltx_reuse_config import CASES, RUN_ID, WARMUP_STAGE_1, WARMUP_STAGE_2, output_id
from ltx_reuse import ResidentTransformer
from ltx_worker import BASE, MODELS, save, digest


def serve():
    import torch
    from ltx_core.model.video_vae import AUTO_TILING, get_video_chunks_number
    from ltx_pipelines.distilled import DistilledPipeline
    from ltx_pipelines.utils.media_io import encode_video
    from ltx_pipelines.utils.model_paths import ModelPaths
    from ltx_pipelines.utils.constants import DISTILLED_SIGMA_VALUES, STAGE_2_DISTILLED_SIGMA_VALUES

    if torch.cuda.device_count() != 1:
        raise ValueError("One GPU is required")
    with (BASE / "reuse-service-claim.json").open("x") as out:
        json.dump({"run_id": RUN_ID, "started_at": time.time()}, out)
    names = list(FILES)
    paths = ModelPaths.from_split(transformer_path=str(MODELS / names[0]),
        text_encoder_path=str(MODELS / names[1]), video_vae_path=str(MODELS / names[2]),
        audio_vae_path=str(MODELS / names[3]), duration_head_path=str(MODELS / names[4]))
    prompt = validate_prompt(json.loads((BASE / "request.json").read_text())["prompt"])
    pipeline, current_mode, resident = None, None, None
    stats, builds = [], []

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
            stats.append({"stage": self.name, "seconds": time.monotonic() - start})
            print(json.dumps(stats[-1]), flush=True)
            return value

    try:
        for case, mode, warmup in CASES:
            if mode != current_mode:
                if resident:
                    resident.close()
                pipeline = None
                gc.collect()
                torch.cuda.empty_cache()
                pipeline = DistilledPipeline(model_paths=paths, spatial_upsampler_path=str(MODELS / names[5]), loras=())
                stage = pipeline.stage
                original_build = stage._build_transformer

                def counted_build(*args, _build=original_build, **kwargs):
                    torch.cuda.synchronize()
                    started = time.monotonic()
                    model = _build(*args, **kwargs)
                    torch.cuda.synchronize()
                    builds.append(time.monotonic() - started)
                    return model

                stage._build_transformer = counted_build
                resident = ResidentTransformer(stage) if mode == "resident" else None
                for name in ("prompt_encoder", "stage", "upsampler", "audio_decoder"):
                    setattr(pipeline, name, TimedBlock(name, getattr(pipeline, name)))
                current_mode = mode
            save("reuse-service-status.json", {"phase": "ready", "case": case, "at": time.time()})
            trigger = BASE / (case + ".request.json")
            while not trigger.exists():
                time.sleep(0.05)
            request = json.loads(trigger.read_text())
            if request != {"run_id": RUN_ID, "case": case}:
                raise ValueError("Unexpected request identity")
            with (BASE / (case + ".claim.json")).open("x") as out:
                json.dump({"started_at": time.time()}, out)
            stats.clear()
            builds.clear()
            save("reuse-service-status.json", {"phase": "generating", "case": case, "at": time.time()})
            torch.cuda.reset_peak_memory_stats()
            torch.cuda.synchronize()
            started = time.monotonic()
            schedule = ({"stage_1_sigmas": torch.tensor(WARMUP_STAGE_1),
                         "stage_2_sigmas": torch.tensor(WARMUP_STAGE_2)} if warmup else {})
            with torch.inference_mode():
                output = pipeline(prompt=prompt, seed=42, width=WIDTH, height=HEIGHT,
                    num_frames=FRAMES, frame_rate=FPS, images=[], enhance_prompt=False,
                    tiling_config=AUTO_TILING, **schedule)
                torch.cuda.synchronize()
                returned = time.monotonic()
                path = BASE / (output_id(case) + ".mp4")
                encode_video(video=output.video, fps=FPS, audio=output.audio, output_path=str(path),
                    video_chunks_number=get_video_chunks_number(output.num_frames, output.tiling_config))
            torch.cuda.synchronize()
            finished = time.monotonic()
            result = {"run_id": RUN_ID, "case": case, "mode": mode, "warmup": warmup,
                "processing_seconds": finished - started, "pipeline_return_seconds": returned - started,
                "lazy_video_decode_and_encode_seconds": finished - returned,
                "stages_including_weight_loading": list(stats), "transformer_build_seconds": list(builds),
                "transformer_build_count": len(builds), "resident_total_build_count": resident.build_count if resident else None,
                "peak_allocated_bytes": torch.cuda.max_memory_allocated(), "peak_reserved_bytes": torch.cuda.max_memory_reserved(),
                "torch": torch.__version__, "cuda": torch.version.cuda, "gpu": torch.cuda.get_device_name(),
                "source_revision": SOURCE, "model_revision": REVISION,
                "width": WIDTH, "height": HEIGHT, "frames": FRAMES, "fps": FPS, "seed": 42,
                "stage_1_sigmas": WARMUP_STAGE_1 if warmup else DISTILLED_SIGMA_VALUES,
                "stage_2_sigmas": WARMUP_STAGE_2 if warmup else STAGE_2_DISTILLED_SIGMA_VALUES,
                "precision": "BF16", "compile": False, "quantization": None,
                "prompt_enhancement": False, "output_cache": False, "embedding_cache": False,
                "diffvae_mode": "chunked_eager", "output_bytes": path.stat().st_size,
                "output_sha256": digest(path), "completed_at": time.time()}
            save(output_id(case) + ".json", result)
            save("reuse-service-status.json", {"phase": "completed", "case": case, "at": time.time()})
            # The controller must export the completed artifact before another case starts.
            while not (BASE / (case + ".exported")).exists():
                time.sleep(0.05)
            del output
        save("reuse-service-status.json", {"phase": "finished", "at": time.time()})
    finally:
        if resident:
            resident.close()


if __name__ == "__main__":
    try:
        serve()
    except Exception as exc:
        save("reuse-failure.json", {"error_type": type(exc).__name__, "at": time.time()})
        traceback.print_exc()
        raise SystemExit(1)
