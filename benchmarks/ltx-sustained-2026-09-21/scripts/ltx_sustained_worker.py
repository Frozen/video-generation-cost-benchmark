"""One-hour varied-prompt five-second queue with two full warmups; no provisioning.

The controller exports artifacts independently and measures its own complete
submission-to-delivery window. This worker's interval alone is not delivery cost.
"""

import argparse
import os
from pathlib import Path
import time

from load_window import (Journal, read_manifest, sha256, validate_manifest,
                         verify_checkout, verify_guard, wait_for_start, finite)
from ltx_config import FILES, FPS, HEIGHT, IMAGE, MODEL, REVISION, SOURCE, WIDTH

from sustained_queue import run_queue, validate_sustained
from ltx_reuse import ResidentTransformer
from ltx_audio_off import AuditedDenoiser

FRAMES = 121
GPU_CAPABILITIES = {
    'NVIDIA A100-SXM4-80GB': (8, 0),
    'NVIDIA RTX PRO 6000 Blackwell Server Edition': (12, 0),
    'NVIDIA H200': (9, 0),
}


class TracedBlock:
    """Observe component calls without synchronizing or changing GPU scheduling."""

    def __init__(self, name, block, calls, *, audio=None, forwards=None):
        self.name, self.block, self.calls = name, block, calls
        self.audio, self.forwards = audio, forwards

    def __getattr__(self, name):
        return getattr(self.block, name)

    def __call__(self, *args, **kwargs):
        started = time.monotonic()
        if self.name == "stage" and self.forwards is not None:
            kwargs["denoiser"] = AuditedDenoiser(kwargs["denoiser"], self.audio, self.forwards)
        value = self.block(*args, **kwargs)
        self.calls.append({"component": self.name,
                           "host_call_seconds": time.monotonic() - started})
        return value


def profile(gpu):
    if gpu not in GPU_CAPABILITIES:
        raise ValueError("Unreviewed GPU")
    return {"backend": "ltx25", "mode": "resident", "model": MODEL, "model_revision": REVISION,
            "source_revision": SOURCE, "container_image": IMAGE, "gpu_count": 1,
            "gpu_name": gpu, "width": WIDTH, "height": HEIGHT, "frames": FRAMES, "fps": FPS,
            "requested_video_seconds": 5, "audio": True, "precision": "BF16",
            "compile": False, "quantization": None, "prompt_enhancement": False,
            "output_cache": False, "embedding_cache": False, "schedule": "distilled_8_plus_3",
            "decoder_tiling": {"frames": 128, "temporal_overlap": 40, "height": 768,
                               "width": 1344, "spatial_overlap": 160}}


def validate_profile(plan):
    validate_sustained(plan)
    if plan["profile"] != profile("NVIDIA RTX PRO 6000 Blackwell Server Edition"):
        raise ValueError("Only the frozen RTX resident five-second native-audio profile is supported")
    if len(plan["requests"]) != 500 or plan["limits"]["max_requests"] != 500:
        raise ValueError("The registered request pool contains 500 primary requests")
    seeds = [r["seed"] for r in plan["requests"]] + plan["technical_warmup_seeds"]
    if len(seeds) != 502 or len(set(seeds)) != 502 or any(type(s) is not int or not 0 <= s < 2**31 for s in seeds):
        raise ValueError("Fresh unique 31-bit seeds and two separate warmup seeds are required")
    finite(plan["limits"].get("warmup_bound_seconds", 0), positive=True)
    return "resident"


def required_suite_seconds(plan):
    validate_profile(plan)
    return (2 * plan["limits"]["warmup_bound_seconds"]
            + plan["limits"]["target_queue_seconds"] + plan["limits"]["request_bound_seconds"]
            + plan["limits"]["export_reserve_seconds"])


def require_complete_queue(result):
    if result["worker_window_seconds"] < 3600 or result["stop_reason"] != "target_duration_reached":
        raise RuntimeError("Incomplete one-hour run; retain every attempt and artifact")


def write_preparing(journal, plan, manifest_digest, **fields):
    """Every queue, including inherited warm queues, has the same admission proof."""
    return journal.write("preparing", manifest_sha256=manifest_digest,
                         profile=plan["profile"], **fields)


def serve(manifest, base):
    plan, manifest_digest = read_manifest(manifest)
    mode = validate_profile(plan)
    verify_guard(base / "guard-ready.json", plan["limits"]["shutdown_deadline_epoch"])
    source = base / "ltx-source"
    verify_checkout(source, SOURCE)
    # Claim before preparation or warmup: a restart requires a new reviewed run.
    output = base / plan["run_id"]
    output.mkdir(mode=0o700)
    journal = Journal(output / "events.jsonl", plan["run_id"])
    resident = None
    try:
        write_preparing(journal, plan, manifest_digest)
        names = list(FILES)
        models = base / "models"
        for name, (size, expected_hash) in FILES.items():
            path = models / name
            if path.stat().st_size != size or sha256(path) != expected_hash:
                raise ValueError("Pinned weight verification failed")
        import torch
        from ltx_core.model.video_vae import DimensionSizeConfig, TileSizeConfig, get_video_chunks_number
        fixed_tiling = TileSizeConfig(frames=DimensionSizeConfig(tile_size=128, overlap=40),
            height=DimensionSizeConfig(tile_size=768, overlap=160),
            width=DimensionSizeConfig(tile_size=1344, overlap=160))
        from ltx_pipelines.distilled import DistilledPipeline
        from ltx_pipelines.utils.media_io import encode_video
        from ltx_pipelines.utils.model_paths import ModelPaths

        if (torch.cuda.device_count() != 1 or torch.cuda.get_device_name() != plan["profile"]["gpu_name"]
                or tuple(torch.cuda.get_device_capability()) != GPU_CAPABILITIES[plan["profile"]["gpu_name"]]
                or torch.__version__ != "2.13.0+cu132" or torch.version.cuda != "13.2"):
            raise ValueError("The allocated GPU/runtime differs from the frozen candidate")
        from ltx_core.model.transformer.attention import _select_primary_attention, _select_masked_attention
        dispatch = {
            "primary_policy": getattr(_select_primary_attention(), "label", "unlabeled"),
            "masked_policy": getattr(_select_masked_attention(), "label", "unlabeled"),
            "note": "SDPA labels show dispatch policy, not the final CUDA kernel. See first full-warmup profiler."}
        journal.write("runtime_verified", gpu_name=torch.cuda.get_device_name(),
                      capability=list(torch.cuda.get_device_capability()), attention_dispatch=dispatch)
        paths = ModelPaths.from_split(transformer_path=str(models / names[0]),
            text_encoder_path=str(models / names[1]), video_vae_path=str(models / names[2]),
            audio_vae_path=str(models / names[3]), duration_head_path=str(models / names[4]))
        audio = plan["profile"]["audio"]
        pipeline_type = DistilledPipeline
        if not audio:
            from ltx_audio_off import pipeline_class
            pipeline_type = pipeline_class()
        pipeline = pipeline_type(model_paths=paths, spatial_upsampler_path=str(models / names[5]), loras=())
        resident = ResidentTransformer(pipeline.stage) if mode == "resident" else None
        component_calls, forward_calls = [], []
        for name in ("prompt_encoder", "stage", "upsampler", "video_decoder", "audio_decoder"):
            setattr(pipeline, name, TracedBlock(name, getattr(pipeline, name), component_calls,
                                              audio=audio, forwards=forward_calls))

        def generate(request, path, warmup=False):
            before_build_count = resident.build_count
            before_build_seconds = resident.build_seconds
            component_calls.clear()
            forward_calls.clear()
            torch.cuda.reset_peak_memory_stats()
            torch.cuda.synchronize()
            with torch.inference_mode():
                clip = pipeline(prompt=request["prompt"], seed=request["seed"], width=WIDTH,
                    height=HEIGHT, num_frames=int(request["requested_video_seconds"] * FPS + 1), frame_rate=FPS, images=[],
                    enhance_prompt=False, tiling_config=fixed_tiling)
                encode_video(video=clip.video, fps=FPS, audio=clip.audio, output_path=str(path),
                    video_chunks_number=get_video_chunks_number(clip.num_frames, clip.tiling_config))
            torch.cuda.synchronize()
            observed = [call["component"] for call in component_calls]
            expected = ["prompt_encoder", "stage", "upsampler", "stage", "video_decoder"]
            if audio:
                expected.append("audio_decoder")
            if observed != expected or len(forward_calls) != 11:
                raise RuntimeError("Expected fresh pipeline execution was not observed")
            if not warmup and (resident.build_count != 1 or before_build_count != 1):
                raise RuntimeError("Measured request rebuilt the transformer or ran without warmup")
            return {"warmup": warmup, "worker_pid": os.getpid(),
                    "transformer_builds_this_request": resident.build_count - before_build_count,
                    "transformer_build_seconds_this_request": resident.build_seconds - before_build_seconds, "peak_allocated_bytes": torch.cuda.max_memory_allocated(),
                    "peak_reserved_bytes": torch.cuda.max_memory_reserved(),
                    "resident_total_build_count": resident.build_count if resident else None,
                    "torch": torch.__version__, "cuda": torch.version.cuda,
                    "resolved_tiling": repr(clip.tiling_config),
                    "component_calls": list(component_calls),
                    "transformer_calls": list(forward_calls),
                    "trace_boundary": "Host calls; video decoding is lazy and included in total processing"}

        if time.time() + required_suite_seconds(plan) >= plan["limits"]["shutdown_deadline_epoch"]:
            raise TimeoutError("Insufficient time for both full warmups, the one-hour queue and export")
        for index, seed in enumerate(plan["technical_warmup_seeds"]):
            request = dict(plan["requests"][0], seed=seed)
            journal.write("warmup_started", ordinal=index + 1, seed=seed, requested_video_seconds=5)
            path = output / ("technical-warmup-%d.mp4" % (index + 1))
            if index == 0:
                # Profiling affects only the first untimed warmup, never the measured queue.
                with torch.profiler.profile(activities=[torch.profiler.ProfilerActivity.CPU,
                                                       torch.profiler.ProfilerActivity.CUDA]) as trace:
                    metadata = generate(request, path, warmup=True)
                names = sorted({str(e.name) for e in trace.events()})
                journal.write("warmup_kernel_names", names=names)
                del trace
            else:
                metadata = generate(request, path, warmup=True)
            journal.write("warmup_finished", ordinal=index + 1, artifact=path.name,
                          artifact_sha256=sha256(path), runtime=metadata)
        if time.time() + 3600 + plan["limits"]["request_bound_seconds"] + plan["limits"]["export_reserve_seconds"] >= plan["limits"]["shutdown_deadline_epoch"]:
            raise TimeoutError("Warmups consumed the complete-queue allowance")
        wait_for_start(plan, manifest_digest, output, journal, base)
        result = run_queue(plan, generate, output, journal,
                           stop_requested=lambda: (output / "stop.json").exists())
        require_complete_queue(result)
    except Exception as exc:
        journal.write("worker_failed", error_type=type(exc).__name__)
        raise
    finally:
        try:
            if resident:
                resident.close()
        finally:
            journal.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--base", type=Path, default=Path("/root/benchmark"))
    args = parser.parse_args()
    serve(args.manifest, args.base)
