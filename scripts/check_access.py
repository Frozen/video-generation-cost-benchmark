"""Read-only credential checks. Never submit inference or provision resources."""

import argparse
import json
from pathlib import Path
import re
import shlex
import subprocess

ENDPOINT = "minimax/h3/text-to-video"
CHECKS = {
    "fal_pricing": ("fal", "https://api.fal.ai/v1/models/pricing?endpoint_id=minimax%2Fh3%2Ftext-to-video", "Key "),
    "fal_balance": ("fal", "https://api.fal.ai/v1/account/billing?expand=credits", "Key "),
    "runpod_pods": ("runpod", "https://api.runpod.io/v2/pods", "Bearer "),
}
ALIASES = {"fal": ("FAL_KEY", "FAL_API"), "runpod": ("RUNPOD_API_KEY", "RUNPOD_API")}


def load_keys(path):
    """Parse literal assignments, without sourcing a shell or expanding values."""
    values = {}
    names = {name for aliases in ALIASES.values() for name in aliases}
    for line in path.read_text().splitlines():
        match = re.fullmatch(r"\s*(?:export\s+)?([A-Za-z_][A-Za-z_0-9]*)\s*=\s*(.*?)\s*", line)
        if not match or match[1] not in names:
            continue
        name = match[1]
        if name in values:
            raise ValueError("Duplicate credential assignment")
        try:
            parts = shlex.split(match[2], comments=True)
        except ValueError:
            raise ValueError("Invalid credential quoting") from None
        if len(parts) > 1:
            raise ValueError("Credential must be a single literal value")
        values[name] = parts[0] if parts else ""
    keys = {}
    for provider, aliases in ALIASES.items():
        candidates = {values[name] for name in aliases if values.get(name)}
        if len(candidates) > 1:
            raise ValueError("Conflicting credential aliases")
        keys[provider] = next(iter(candidates), "")
    return keys


def check(name, key, run=subprocess.run):
    provider, url, prefix = CHECKS[name]
    result = {"check": name, "provider": provider}
    if not key:
        return dict(result, status="missing_key")
    if any(char.isspace() or ord(char) < 32 or ord(char) > 126 for char in key):
        return dict(result, status="invalid_key_format")
    # The key is passed on stdin, never in process arguments or diagnostic output.
    config = "header = " + json.dumps("Authorization: " + prefix + key) + "\n"
    command = [
        "curl", "-q", "--config", "-", "--silent", "--show-error",
        "--proto", "=https", "--max-redirs", "0", "--connect-timeout", "10",
        "--max-time", "30", "--max-filesize", "1048576",
        "--write-out", "\n%{http_code}", url,
    ]
    try:
        reply = run(command, input=config, capture_output=True, text=True, timeout=35)
    except (OSError, subprocess.SubprocessError):
        return dict(result, status="transport_error")
    if reply.returncode:
        return dict(result, status="transport_error", transport_exit=reply.returncode)
    try:
        body, code = reply.stdout.rsplit("\n", 1)
        http = int(code)
    except (ValueError, AttributeError):
        return dict(result, status="invalid_response")
    result["http"] = http
    if http != 200:
        status = {401: "unauthorized", 403: "access_denied"}.get(http, "http_error")
        return dict(result, status=status)
    try:
        data = json.loads(body)
        if name == "fal_pricing":
            prices = [item for item in data["prices"] if item["endpoint_id"] == ENDPOINT]
            if len(prices) != 1:
                raise ValueError("Expected endpoint price missing")
            price = prices[0]
            result["pricing"] = {field: price[field] for field in ("unit_price", "unit", "currency")}
            result["pricing_note"] = "Base billing-unit price; not a resolution-specific quote."
        elif name == "fal_balance":
            result["credits"] = {field: data["credits"][field] for field in ("current_balance", "currency")}
        elif not isinstance(data, (dict, list)):
            raise ValueError("Expected resource listing")
    except (ValueError, TypeError, KeyError):
        return dict(result, status="invalid_response")
    # Disallow an unexpected reflected credential in even an allowlisted field.
    if key in json.dumps(result):
        return {"check": name, "status": "unsafe_response_suppressed"}
    return dict(result, status="ok")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--provider", choices=("fal", "runpod", "both"), default="both")
    args = parser.parse_args()
    try:
        keys = load_keys(args.env_file)
    except (OSError, UnicodeError, ValueError):
        print(json.dumps({"status": "credential_file_error", "details": "Check literal assignments and duplicate aliases; values are not printed."}))
        return 2
    results = [check(name, keys[provider]) for name, (provider, _, _) in CHECKS.items()
               if args.provider in ("both", provider)]
    print(json.dumps({"checks": results, "paid_actions": 0}, indent=2))
    # Credit visibility is separate from authentication; a 403 is not a bad key.
    return int(any(item["status"] != "ok" for item in results if item["check"] != "fal_balance"))


if __name__ == "__main__":
    raise SystemExit(main())
