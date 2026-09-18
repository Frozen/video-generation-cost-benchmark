"""Pinned adapters for the explicitly approved two-output acceleration trial."""

ADAPTERS = {
    "larry8": {
        "repo": "larryvrh/MiniMax-H3-Turbo-Lora",
        "revision": "43a74557ac3f6539db8e0f2a959d03feb7a81480",
        "filename": "minimax_h3_turbo_v4_step600_ema.safetensors",
        "sha256": "5f3a626cd72c93a8b9318d6760c510bc5092d2ab13aaba1f932c5bab07a416d3",
        "bytes": 779849816, "evaluations": 8, "sigma_points": 9, "alpha": None,
    },
    "light4": {
        "repo": "lightx2v/Minimax-h3-Turbo",
        "revision": "3ec17a324ced54151364f24f8b5fb6bf7e26414f",
        "filename": "minimax_h3_fl2v_turbo_4step_v0.1.safetensors",
        "sha256": "5ff4a12c8b4599fec716e1b15a45e504e0d1129111896bdcde5ac4a15e395b29",
        "bytes": 1383677888, "evaluations": 4, "sigma_points": 5, "alpha": 8,
    },
}
