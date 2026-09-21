"""Separate warm/resident experiment; the original cold test remains unchanged."""

RUN_ID = "P01_EN_RUNPOD_H100_LTX25_REUSE_5S_001"
VAST_RUN_ID = "P01_EN_VAST_H100_LTX25_REUSE_5S_001"
VAST_RETRY_RUN_ID = "P01_EN_VAST_H100_LTX25_REUSE_5S20S_002"
VAST_RECOVERY_RUN_ID = "P01_EN_VAST_H100_LTX25_REUSE_5S20S_003"
VAST_HANDOFF_RUN_ID = "P01_EN_VAST_H100_LTX25_REUSE_5S20S_004"
VAST_RESUME_RUN_ID = "P01_EN_VAST_H100_LTX25_REUSE_5S20S_005"
VAST_PROXY_RUN_ID = "P01_EN_VAST_H100_LTX25_REUSE_5S20S_006"
VAST_STABLE_RUN_ID = "P01_EN_VAST_H100_LTX25_REUSE_5S20S_007"
VAST_ALTERNATE_RUN_ID = "P01_EN_VAST_H100_LTX25_REUSE_5S20S_008"
VAST_EXTENDED_RUN_IDS = (VAST_RETRY_RUN_ID, VAST_RECOVERY_RUN_ID, VAST_HANDOFF_RUN_ID, VAST_RESUME_RUN_ID, VAST_PROXY_RUN_ID, VAST_STABLE_RUN_ID, VAST_ALTERNATE_RUN_ID)
VAST_RUN_IDS = (VAST_RUN_ID, *VAST_EXTENDED_RUN_IDS)
# Technical warmup only: two intervals per native stage, not a full output
# schedule. The measured requests retain the original eight-plus-three steps.
WARMUP_STAGE_1 = [1.0, 0.725, 0.0]
WARMUP_STAGE_2 = [0.909375, 0.421875, 0.0]
CASES = (
    ("BASE_WARMUP", "baseline", True),
    ("BASE_WARM", "baseline", False),
    ("REUSE_WARMUP", "resident", True),
    ("REUSE_WARM", "resident", False),
)
RETRY_CASES = (
    ("BASE_WARMUP", "baseline", True),
    ("BASE_WARM_5S", "baseline", False),
    ("BASE_WARM_20S", "baseline", False),
    ("REUSE_WARMUP", "resident", True),
    ("REUSE_WARM_5S", "resident", False),
    ("REUSE_WARM_20S", "resident", False),
)


def validate_run_id(run_id):
    if run_id not in (RUN_ID, *VAST_RUN_IDS):
        raise ValueError("Unreviewed run identity")
    return run_id


def cases_for(run_id=RUN_ID):
    validate_run_id(run_id)
    return RETRY_CASES if run_id in VAST_EXTENDED_RUN_IDS else CASES


def case_settings(case, run_id=RUN_ID):
    for name, mode, warmup in cases_for(run_id):
        if name == case:
            seconds = 20 if name.endswith("_20S") else 5
            return {"mode": mode, "warmup": warmup, "requested_seconds": seconds,
                    "frames": seconds * 24 + 1}
    raise ValueError("Unreviewed case")


def output_id(case, run_id=RUN_ID):
    case_settings(case, run_id)
    return run_id + "_" + case
