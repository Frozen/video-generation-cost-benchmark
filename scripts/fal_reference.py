"""Run exactly one authorized 5-second fal reference; never provision a GPU."""

import argparse
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import subprocess
import time
from urllib.parse import urlparse

from budget import transact
from check_access import ENDPOINT, check, load_keys

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "private" / "fal-p01"
LEDGER = ROOT / "private" / "ledger.json"
SOURCE = "https://awesomevideoprompts.com/en/prompts/2085162073810739210-chef-slicing-cartoon-onion"
RUN_ID = "P01_FAL_5S_001"
PARAMETERS = {"duration": 5, "resolution": "768P", "aspect_ratio": "16:9", "seed": 42,
              "prompt_expansion_mode": "disabled", "enable_safety_checker": True, "sync_mode": False}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


class PromptParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip = 0
        self.active = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)

    def handle_data(self, data):
        if self.skip:
            return
        if data.strip() == "Copy prompt":
            self.active = True
        elif data.strip() == "You Might Also Like":
            self.active = False
        elif self.active:
            self.parts.append(data)


def allowed_queue(url):
    parsed = urlparse(url)
    return (parsed.scheme == "https" and parsed.netloc == "queue.fal.run"
            and parsed.path.startswith("/minimax/h3/") and not parsed.fragment)


def curl(url, *, key=None, payload=None, output=None, headers=None):
    """No redirects/retries; secrets and signed URLs are passed on stdin."""
    if key is not None and not allowed_queue(url):
        raise ValueError("Refusing credentials outside the selected fal queue")
    if key is not None and (not key or any(c.isspace() or ord(c) < 32 for c in key)):
        raise ValueError("Invalid credential format")
    config = "url = " + json.dumps(url) + "\n"
    for header in (["Authorization: Key " + key] if key else []):
        config += "header = " + json.dumps(header) + "\n"
    command = ["curl", "-q", "--config", "-", "--silent", "--show-error",
               "--proto", "=https", "--max-redirs", "0", "--connect-timeout", "10",
               "--max-time", "120" if output else "30", "--max-filesize", "134217728",
               "--write-out", "\n%{http_code}"]
    if payload is not None:
        command += ["--request", "POST", "--header", "Content-Type: application/json",
                    "--header", "X-Fal-No-Retry: 1", "--header", "X-Fal-Request-Timeout: 120",
                    "--data-binary", "@" + str(payload)]
    if headers:
        command += ["--dump-header", str(headers)]
    if output:
        command += ["--output", str(output)]
    result = subprocess.run(command, input=config, text=True, capture_output=True, timeout=130)
    if result.returncode:
        raise RuntimeError("Transport failed (curl code %d); no automatic retry" % result.returncode)
    body, status = result.stdout.rsplit("\n", 1)
    if int(status) not in (200, 201, 202):
        raise RuntimeError("HTTP %s; no automatic retry" % status)
    return body


def prepare():
    PRIVATE.mkdir(parents=True, mode=0o700, exist_ok=True)
    if (PRIVATE / "payload.json").exists() or (PRIVATE / "state.json").exists():
        raise ValueError("Prepared input already exists; do not overwrite a frozen request")
    parser = PromptParser()
    parser.feed(curl(SOURCE))
    prompt = "".join(parser.parts).strip()
    if not prompt.startswith("A cinematic live-action cooking scene") or not prompt.endswith("dramatic cooking sounds."):
        raise ValueError("Source prompt structure changed; review before paying")
    payload = dict(PARAMETERS, prompt=prompt)
    save(PRIVATE / "payload.json", payload)
    metadata = {
        "run_id": RUN_ID, "endpoint": ENDPOINT, "parameters": PARAMETERS,
        "source_url": SOURCE, "author": "cocktail peanut",
        "original_source": "https://x.com/cocktailpeanut/status/2085162073810739210",
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "prompt_sha256": sha(prompt.encode()),
        "payload_sha256": sha((PRIVATE / "payload.json").read_bytes()),
        "prompt_words": len(prompt.split()), "prompt_modified": False,
        "expected_generation_usd": "0.30", "reservation_usd": "1.00",
        "rate_source": "https://fal.ai/models/" + ENDPOINT,
        "rate_usd_per_generated_second": "0.06",
        "permission_record": "Collection About page offers prompts free to use; no standalone redistribution license verified. Full prompt remains private.",
        "scope": "One API reference only; no Runpod commitment, repetitions or longer clips.",
    }
    save(PRIVATE / "input-manifest.json", metadata)
    print(json.dumps(metadata, indent=2), flush=True)


def validate_payload(payload, manifest):
    data = json.loads(payload)
    if {k: v for k, v in data.items() if k != "prompt"} != PARAMETERS:
        raise ValueError("Frozen request profile changed")
    if sha(payload) != manifest["payload_sha256"] or sha(data["prompt"].encode()) != manifest["prompt_sha256"]:
        raise ValueError("Frozen request hash changed")


def collect(key, monotonic_start=None):
    state = json.loads((PRIVATE / "state.json").read_text())
    if state.get("status") == "download_complete":
        print("Already downloaded; no network request or new generation.", flush=True)
        return
    queue = state.get("queue")
    if not queue:
        raise ValueError("No confirmed request ID; inspect provider history, never resubmit blindly")
    deadline = time.monotonic() + 900
    while time.monotonic() < deadline:
        status = json.loads(curl(queue["status_url"], key=key))
        elapsed = time.time() - state["submitted_epoch"]
        event = {"elapsed_seconds": round(elapsed, 3), "status": status.get("status")}
        state.setdefault("events", []).append(event)
        save(PRIVATE / "state.json", state)
        print(json.dumps(event), flush=True)
        if status.get("status") == "COMPLETED":
            save(PRIVATE / "completion.json", status)
            if status.get("error"):
                state["status"] = "provider_failed"
                save(PRIVATE / "state.json", state)
                raise RuntimeError("Provider reported failure; preserved privately, no retry")
            response = json.loads(curl(queue["response_url"], key=key,
                                       headers=PRIVATE / "response-headers.txt"))
            save(PRIVATE / "response.json", response)
            url = response["video"]["url"]
            parsed = urlparse(url)
            if parsed.scheme != "https" or not (parsed.hostname or "").endswith(".fal.media"):
                raise ValueError("Unexpected output host; review URL privately before download")
            curl(url, output=PRIVATE / "video.mp4")
            download_done = time.monotonic()
            state["status"] = "download_complete"
            state["end_to_end_seconds"] = ((download_done - monotonic_start) if monotonic_start is not None
                                            else time.time() - state["submitted_epoch"])
            state["timing_clock"] = "monotonic" if monotonic_start is not None else "wall_clock_resumed_collection"
            state["latency_pass"] = state["end_to_end_seconds"] <= 15
            state["video_sha256"] = sha((PRIVATE / "video.mp4").read_bytes())
            state["video_bytes"] = (PRIVATE / "video.mp4").stat().st_size
            save(PRIVATE / "state.json", state)
            print(json.dumps({k: state[k] for k in ("status", "end_to_end_seconds", "timing_clock", "latency_pass", "video_bytes", "video_sha256")}), flush=True)
            return
        if status.get("status") not in ("IN_QUEUE", "IN_PROGRESS"):
            raise RuntimeError("Unknown queue state; preserved for inspection")
        time.sleep(2)
    raise RuntimeError("Collection timed out; reservation retained, request may still run. Use collect, not submit.")


def submit(key):
    if (PRIVATE / "state.json").exists():
        raise ValueError("Submission marker exists; use collect, never submit again")
    manifest = json.loads((PRIVATE / "input-manifest.json").read_text())
    validate_payload((PRIVATE / "payload.json").read_bytes(), manifest)
    if check("fal_pricing", key)["status"] != "ok":
        raise ValueError("Read-only fal authentication check failed")
    if not LEDGER.exists():
        transact(LEDGER, "init")
    # A unique ledger ID prevents concurrent submissions even before the marker exists.
    transact(LEDGER, "reserve", RUN_ID, "1.00", "generation")
    state = {"run_id": RUN_ID, "status": "submission_started_do_not_retry",
             "submitted_epoch": time.time(), "actual_charge_usd": None,
             "expected_generation_usd": "0.30", "billing_status": "unreconciled"}
    save(PRIVATE / "state.json", state)
    start = time.monotonic()
    response = json.loads(curl("https://queue.fal.run/" + ENDPOINT, key=key,
                               payload=PRIVATE / "payload.json", headers=PRIVATE / "submit-headers.txt"))
    save(PRIVATE / "queue.json", response)
    if not response.get("request_id"):
        raise ValueError("Submission response has no request ID; no retry")
    for field in ("status_url", "response_url"):
        if not allowed_queue(response.get(field, "")):
            raise ValueError("Unexpected queue URL; inspect privately, no retry")
    state["queue"] = response
    state["status"] = "submitted"
    save(PRIVATE / "state.json", state)
    print("One paid request accepted. Polling the same request; no new submissions.", flush=True)
    collect(key, start)


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "submit", "collect"))
    parser.add_argument("--env-file", type=Path)
    args = parser.parse_args()
    try:
        if args.action == "prepare":
            prepare()
        else:
            if args.env_file is None:
                raise ValueError("--env-file required")
            key = load_keys(args.env_file)["fal"]
            if not key:
                raise ValueError("fal key missing")
            (submit if args.action == "submit" else collect)(key)
    except Exception as exc:
        # Exception text can contain request URLs or headers; never print it.
        print(json.dumps({"status": "stopped", "error_class": type(exc).__name__,
                          "instruction": "Inspect private state; never retry submission automatically."}), flush=True)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
