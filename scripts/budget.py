"""Offline spending admission ledger. This does not enforce a provider-side cap."""

import argparse
import copy
import fcntl
import json
import os
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from pathlib import Path
import tempfile

CAP_CENTS = 2500
NEW_COMPUTE_CENTS = 2250


def cents(value):
    """Round exposure UP to cents; retain authoritative precise charges separately."""
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0:
            raise ValueError("amount must be finite and nonnegative")
        return int((amount * 100).to_integral_value(rounding=ROUND_CEILING))
    except InvalidOperation as exc:
        raise ValueError("invalid amount") from exc


def empty_ledger():
    return {"version": 1, "cap_cents": CAP_CENTS, "entries": {}, "blocked": False}


def validate(state):
    if state.get("version") != 1 or state.get("cap_cents") != CAP_CENTS:
        raise ValueError("ledger version/cap mismatch")
    if not isinstance(state.get("blocked"), bool) or not isinstance(state.get("entries"), dict):
        raise ValueError("invalid ledger structure")
    for entry in state["entries"].values():
        if entry.get("status") not in ("reserved", "settled"):
            raise ValueError("invalid entry status")
        for key in ("reserved_cents", "actual_cents"):
            value = entry.get(key)
            if key == "actual_cents" and entry["status"] == "reserved" and value is None:
                continue
            if type(value) is not int or value < 0:
                raise ValueError("invalid entry amount")


def exposure(state):
    validate(state)
    return sum(entry["actual_cents"] if entry["status"] == "settled"
               else entry["reserved_cents"] for entry in state["entries"].values())


def reserve(state, entry_id, amount, phase):
    validate(state)
    if state["blocked"]:
        raise ValueError("ledger blocked after a quoted-bound violation")
    if not entry_id or entry_id in state["entries"]:
        raise ValueError("entry ID must be new and nonempty; never retry implicitly")
    if phase not in ("generation", "evaluation", "closeout"):
        raise ValueError("unknown phase")
    quote = cents(amount)
    if quote == 0:
        raise ValueError("paid work needs a positive upper-bound reservation")
    current = exposure(state)
    if phase != "closeout" and current + quote > NEW_COMPUTE_CENTS:
        raise ValueError("new compute would consume the closeout reserve")
    if current + quote > CAP_CENTS:
        raise ValueError("total exposure would exceed USD 25")
    result = copy.deepcopy(state)
    result["entries"][entry_id] = {"phase": phase, "status": "reserved",
                                   "reserved_cents": quote, "actual_cents": None}
    return result


def settle(state, entry_id, amount):
    validate(state)
    if entry_id not in state["entries"] or state["entries"][entry_id]["status"] != "reserved":
        raise ValueError("settlement needs an outstanding reservation")
    result = copy.deepcopy(state)
    entry = result["entries"][entry_id]
    actual = cents(amount)
    entry["actual_cents"] = actual
    entry["status"] = "settled"
    # Never reject/hide a charge that already happened. Preserve it and block work.
    entry["quoted_bound_exceeded"] = actual > entry["reserved_cents"]
    result["blocked"] = result["blocked"] or entry["quoted_bound_exceeded"]
    return result


def summary(state):
    total = exposure(state)
    return {"cap_usd": "25.00", "exposure_usd": f"{total / 100:.2f}",
            "remaining_usd": f"{(CAP_CENTS - total) / 100:.2f}",
            "blocked": state["blocked"], "budget_exceeded": total > CAP_CENTS,
            "outstanding_reservations": sum(e["status"] == "reserved" for e in state["entries"].values())}


def transact(path, action, entry_id=None, amount=None, phase=None):
    path = Path(path)
    # Private ledger: do not put account identifiers or credentials in entry IDs.
    with open(str(path) + ".lock", "a", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if action == "init":
            if path.exists():
                raise ValueError("refusing to reset an existing ledger")
            state = empty_ledger()
        else:
            # A missing/corrupt journal fails closed, never silently starts at zero.
            state = json.loads(path.read_text(encoding="utf-8"))
            validate(state)
            if action == "reserve":
                state = reserve(state, entry_id, amount, phase)
            elif action == "settle":
                state = settle(state, entry_id, amount)
            elif action != "show":
                raise ValueError("unknown action")
        if action != "show":
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                                 prefix=".ledger-", delete=False) as target:
                    temporary = target.name
                    json.dump(state, target, indent=2)
                    target.write("\n")
                    target.flush()
                    os.fsync(target.fileno())
                os.replace(temporary, path)
                temporary = None
            finally:
                if temporary is not None:
                    os.unlink(temporary)
        return summary(state)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", required=True, help="Private local journal path")
    parser.add_argument("action", choices=("init", "reserve", "settle", "show"))
    parser.add_argument("--id")
    parser.add_argument("--usd")
    parser.add_argument("--phase", choices=("generation", "evaluation", "closeout"))
    args = parser.parse_args()
    if args.action in ("reserve", "settle") and (args.id is None or args.usd is None):
        parser.error("--id and --usd are required")
    if args.action == "reserve" and args.phase is None:
        parser.error("--phase is required")
    try:
        result = transact(args.ledger, args.action, args.id, args.usd, args.phase)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(2, f"Budget admission refused: {exc}\n")
    print(json.dumps(result, indent=2))
    if result["blocked"] or result["budget_exceeded"]:
        raise SystemExit(3)


if __name__ == "__main__":
    main()
