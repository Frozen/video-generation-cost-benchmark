"""Pinned, single-output LTX-2.5 smoke-test contract."""

MODEL = "Lightricks/LTX-2.5"
REVISION = "5e6e71018ee1756ed329b697a7b4aedc934dfce9"
SOURCE = "a95ab856bf29407b6b066ede0abe1846050db56c"
IMAGE = "runpod/pytorch@sha256:4d1721e62b56d345c83b4fd6090664be6daf9312caab5b2e76f23d8231941851"
RUN_ID = "P01_EN_RUNPOD_H100_LTX25_5S_001"
PROMPT_SHA256 = "9c924c21f39702c03de5287bb3307e1b6df82303b9e6d352704e7fa7a91a96a7"
FILES = {
    "diffusion_models/ltx-2.5-22b-distilled-transformer-bf16.safetensors":
        (42018190584, "31eb3cad89b9e54e99dd3baf286f70825ac4f6c660a70d9184d895be76d7bff4"),
    "text_encoders/gemma4-12b-with-proj-ltx-2.5-bf16.safetensors":
        (26263858182, "ef7243612fdae7a75cb4d5cee9433e81380675fb6c213bd98ae74a9cd16561d1"),
    "vae/ltx-2.5-video-vae-bf16.safetensors":
        (1472223346, "847e14ca7f3355debca0cea4eaa24ac0fbcdf0061da054ac89ca638a869ddba3"),
    "vae/ltx-2.5-audio-vae-bf16.safetensors":
        (364866540, "c52733d37f6a7fb7949c3dc0fb468c6cb2169e4d836983a73babb9f0d54837a5"),
    "model_patches/ltx-2.5-duration-head-bf16.safetensors":
        (3843690, "2ec71e4206ed365d015f00c05a48caccfb0ee862986809d06ae376c09f5d9190"),
    "latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors":
        (995778752, "eb5a71fe4068ee87ccdb1c3aa635e547ca76bd2d30ae20ae889f2c325c0677e8"),
}
HF_ALIASES = {"hf": ("HF_TOKEN", "HUGGINGFACE_HUB_TOKEN", "HUGGINGFACE_TOKEN", "FACE_API")}
HOURLY = 3.49
RESERVATION = "4.00"
MAX_LEASE_SECONDS = 3600
REGION = "CA-MTL-1"
WIDTH, HEIGHT, FRAMES, FPS = 1344, 768, 121, 24
REQUESTED_SECONDS = 5


def validate_prompt(prompt):
    import hashlib
    if hashlib.sha256(prompt.encode()).hexdigest() != PROMPT_SHA256:
        raise ValueError("Frozen P01_EN prompt mismatch")
    return prompt
