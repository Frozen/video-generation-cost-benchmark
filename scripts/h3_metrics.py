"""Offline summaries of H3 logs and sampled GPU telemetry; no cloud calls."""

import csv
from datetime import datetime, timezone
from decimal import Decimal
import io
import math
import re


def cost_estimate(seconds, hourly_usd, requested_video_seconds):
    """Normalize a measured interval by requested video time, never runtime."""
    interval, rate, duration = map(Decimal, map(str, (seconds, hourly_usd, requested_video_seconds)))
    if not all(value.is_finite() for value in (interval, rate, duration)):
        raise ValueError("Finite values required")
    if interval < 0 or rate < 0 or duration <= 0:
        raise ValueError("Invalid interval, rate or requested duration")
    total = interval * rate / 3600
    return {"total_usd": str(total), "usd_per_requested_video_second": str(total / duration)}


def stage_metrics(log):
    """Last completed request stages; warmup is reported separately."""
    stages = {}
    for name, elapsed in re.findall(r"\[(MiniMaxH3\w+Stage)\] finished in ([0-9.]+) seconds", log):
        stages[name] = float(elapsed)
    warmups = re.findall(r"server warmup req \(([^)]+)\), last=([0-9.]+)s", log)
    return {"last_completed_stages_seconds": stages,
            # tqdm repeats its final line; this is a final reported value, not a count.
            "builtin_warmup_last_seconds": float(warmups[-1][1]) if warmups else None,
            "builtin_warmup_logged_profile": warmups[-1][0] if warmups else None}


def gpu_summary(csv_text, start_epoch, end_epoch):
    """Summarize UTC samples in a client interval, not an exact continuous peak.

    Host/client clock alignment is assumed. Do not infer energy, throughput or
    workload utilization from these GPU-utilization samples.
    """
    if not all(math.isfinite(x) for x in (start_epoch, end_epoch)) or end_epoch < start_epoch:
        raise ValueError("Invalid sample interval")
    grouped = {}
    rows = list(csv.DictReader(io.StringIO(csv_text), skipinitialspace=True))
    for position, raw in enumerate(rows):
        if any(value is None for value in raw.values()):
            if position == len(rows) - 1:
                # A copy taken while nvidia-smi writes can end mid-record.
                continue
            raise ValueError("Incomplete nonterminal telemetry row")
        row = {key.strip(): value.strip() for key, value in raw.items()}
        stamp = datetime.strptime(row["timestamp"], "%Y/%m/%d %H:%M:%S.%f").replace(tzinfo=timezone.utc).timestamp()
        if not start_epoch <= stamp <= end_epoch:
            continue
        values = grouped.setdefault(int(row["index"]), {"used_mib": [], "utilization_percent": [], "power_w": []})
        for key, field in (("used_mib", "memory.used [MiB]"),
                           ("utilization_percent", "utilization.gpu [%]"),
                           ("power_w", "power.draw [W]")):
            try:
                number = float(row[field].split()[0])
            except (ValueError, IndexError):
                continue
            if math.isfinite(number):
                values[key].append(number)
    return {str(index): {
                "sample_count": len(values["used_mib"]),
                **{key + "_sampled_max": max(samples) if samples else None for key, samples in values.items()},
                **{key + "_sampled_mean": sum(samples) / len(samples) if samples else None
                   for key, samples in values.items() if key != "used_mib"}}
            for index, values in sorted(grouped.items())}
