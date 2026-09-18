"""Best-effort local expiry guard for explicitly journaled benchmark resources."""

import argparse
import json
from pathlib import Path
import re
import time

from check_access import load_keys
from runpod_trial import api, save


def expire(resource, key):
    if resource["kind"] not in ("pods", "network-volumes") or not re.fullmatch(r"[A-Za-z0-9_-]+", resource["id"]):
        raise ValueError("Invalid journaled resource")
    route = resource["kind"] + "/" + resource["id"]
    code, current = api("GET", route, key)
    if code == 404:
        return True
    if code != 200 or current.get("id") != resource["id"] or current.get("name") != resource["name"]:
        raise RuntimeError("Resource ownership mismatch")
    code, _ = api("DELETE", route, key)
    if code not in (200, 202, 204, 404):
        return False
    return api("GET", route, key)[0] == 404


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--journal", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, required=True)
    args = parser.parse_args()
    key = load_keys(args.env_file)["runpod"]
    save(args.journal.parent / "watchdog-ready.json", {"armed_at": time.time()})
    completed = {}
    while True:
        journal = json.loads(args.journal.read_text())
        for resource in journal["resources"]:
            if not resource.get("id") or resource["id"] in completed or time.time() < resource["expires_at"]:
                continue
            try:
                if expire(resource, key):
                    completed[resource["id"]] = {"kind": resource["kind"], "verified_absent_at": time.time()}
                    save(args.journal.parent / "watchdog-deletions.json", completed)
            except Exception as exc:
                print("Expiry check: " + type(exc).__name__, flush=True)
        if journal.get("closed"):
            return
        time.sleep(10)


if __name__ == "__main__":
    main()
