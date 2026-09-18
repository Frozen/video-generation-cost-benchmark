"""Read-only Runpod S3 credential probe; no bucket creation or file upload."""

import argparse
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

from check_access import load_keys

ALIASES = {"access": ("AWS_ACCESS_KEY_ID", "RUNPOD_S3_API_USER"),
           "secret": ("AWS_SECRET_ACCESS_KEY", "RUNPOD_S3_API")}
REGIONS = ("EU-CZ-1", "EU-RO-1", "EUR-IS-1", "EUR-NO-1", "US-CA-2", "US-GA-2",
           "US-IL-1", "US-KS-2", "US-MD-1", "US-MO-1", "US-MO-2", "US-NC-1",
           "US-NC-2", "US-NE-1", "US-WA-1")


def check(region, keys, run=subprocess.run):
    if region not in REGIONS:
        raise ValueError("Unreviewed S3 region")
    if any(not keys.get(name) or any(ord(c) < 33 or ord(c) > 126 for c in keys[name])
           for name in ("access", "secret")):
        return {"status": "missing_or_invalid_credentials"}
    config = "user = " + json.dumps(keys["access"] + ":" + keys["secret"]) + "\n"
    try:
        reply = run(["curl", "-q", "--config", "-", "--silent", "--show-error",
                     "--aws-sigv4", "aws:amz:" + region + ":s3", "--proto", "=https",
                     "--max-redirs", "0", "--connect-timeout", "10", "--max-time", "30",
                     "--max-filesize", "1048576", "--write-out", "\n%{http_code}",
                     "https://s3api-" + region.lower() + ".runpod.io/"],
                    input=config, text=True, capture_output=True, timeout=35)
        if reply.returncode:
            return {"status": "transport_error", "exit_code": reply.returncode}
        body, http = reply.stdout.rsplit("\n", 1)
        code = int(http)
        if code != 200:
            return {"status": "access_not_verified", "http": code}
        root = ET.fromstring(body)
        if not root.tag.endswith("ListAllMyBucketsResult"):
            return {"status": "unexpected_response", "http": code}
        return {"status": "ok", "http": code, "region": region,
                "bucket_count": sum(node.tag.split("}")[-1] == "Bucket" for node in root.iter()),
                "paid_actions": 0}
    except (OSError, subprocess.SubprocessError, ValueError, ET.ParseError):
        return {"status": "probe_error"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--region", choices=REGIONS, required=True)
    args = parser.parse_args()
    try:
        keys = load_keys(args.env_file, ALIASES)
    except (OSError, UnicodeError, ValueError):
        print('{"status":"credential_file_error"}')
        return 2
    result = check(args.region, keys)
    print(json.dumps(result))
    return int(result["status"] != "ok")


if __name__ == "__main__":
    raise SystemExit(main())
