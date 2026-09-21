"""Separate warm/resident experiment; the original cold test remains unchanged."""

RUN_ID = "P01_EN_RUNPOD_H100_LTX25_REUSE_5S_001"
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


def output_id(case):
    if case not in {item[0] for item in CASES}:
        raise ValueError("Unreviewed case")
    return RUN_ID + "_" + case
