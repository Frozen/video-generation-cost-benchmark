"""Explicit rental-cost scenarios; never infer self-host runtime from API latency."""

import argparse
import csv
from decimal import Decimal
import sys

UTILIZATIONS = ("1", "0.75", "0.5", "0.25", "0.1", "0.05", "0.01")


def number(value, *, positive=False, fraction=False):
    result = Decimal(str(value))
    if not result.is_finite() or result < 0 or (positive and result == 0):
        raise ValueError("Expected a finite nonnegative value, positive where required")
    if fraction and result > 1:
        raise ValueError("Fraction exceeds one")
    return result


def scenario(gpu_hourly, utilization, accepted_fraction, reference_price,
             service_seconds=None, other_hourly="0", extra_per_attempt="0"):
    rate = number(gpu_hourly, positive=True) + number(other_hourly)
    utilization = number(utilization, positive=True, fraction=True)
    accepted = number(accepted_fraction, fraction=True)
    price = number(reference_price, positive=True)
    extra = number(extra_per_attempt)
    seconds = None if service_seconds is None else number(service_seconds, positive=True)
    if accepted == 0:
        return {"cost_per_accepted_usd": None, "reference_price_headroom_usd": None,
                "break_even_service_seconds": None}
    remaining = price * accepted - extra
    limit = remaining * Decimal(3600) * utilization / rate if remaining > 0 else None
    cost = None if seconds is None else (rate * seconds / (Decimal(3600) * utilization) + extra) / accepted
    return {"cost_per_accepted_usd": cost,
            "reference_price_headroom_usd": None if cost is None else price - cost,
            "break_even_service_seconds": limit}


def rows(args):
    for utilization in UTILIZATIONS:
        values = scenario(args.gpu_hourly, utilization, args.accepted_fraction,
                          args.reference_price, args.service_seconds,
                          args.other_hourly, args.extra_per_attempt)
        yield {"utilization": utilization, "gpu_hourly_usd": args.gpu_hourly,
               "other_hourly_usd": args.other_hourly, "extra_per_attempt_usd": args.extra_per_attempt,
               "assumed_accepted_fraction": args.accepted_fraction,
               "reference_price_usd": args.reference_price,
               "self_host_service_seconds": args.service_seconds or "",
               **{name: "" if value is None else str(value.quantize(Decimal("0.000001")))
                  for name, value in values.items()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gpu-hourly", required=True)
    parser.add_argument("--reference-price", required=True)
    parser.add_argument("--accepted-fraction", required=True,
                        help="Joint quality/contract/latency acceptance fraction; assumed until measured")
    parser.add_argument("--service-seconds", help="Measured GPU-occupied seconds per attempt, not fal latency")
    parser.add_argument("--other-hourly", default="0", help="Explicit hourly overhead scenario; zero is optimistic")
    parser.add_argument("--extra-per-attempt", default="0", help="Explicit per-attempt overhead scenario")
    args = parser.parse_args()
    try:
        data = list(rows(args))
    except (ValueError, ArithmeticError):
        parser.error("Invalid scenario assumptions")
    writer = csv.DictWriter(sys.stdout, fieldnames=list(data[0]))
    writer.writeheader()
    writer.writerows(data)


if __name__ == "__main__":
    main()
