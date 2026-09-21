"""Start one prepared load worker and export without blocking its request queue.

No provisioning or lease extension. Requires an existing budget reservation,
verified rental quote and separately armed shutdown guard. Run in a durable
controller process; after an interruption, inspect original worker and files,
never delete the controller claim or replay the trigger.
"""

import argparse
from fractions import Fraction
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import time

from budget import cents, exposure, compute_gate, validate as validate_ledger
from load_window import read_manifest, sha256


def write_json(path, data):
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as target:
        os.chmod(temporary, 0o600)
        json.dump(data, target, allow_nan=False, indent=2)
        target.write("\n")
        target.flush()
        os.fsync(target.fileno())
    os.replace(temporary, path)


def verify_reservation(ledger, entry_id, quote):
    validate_ledger(ledger)
    entry = ledger["entries"].get(entry_id, {})
    if (ledger["blocked"] or exposure(ledger) > compute_gate(ledger, entry_id)
            or entry.get("status") != "reserved" or entry.get("phase") != "generation"
            or entry.get("reserved_cents", 0) < cents(quote) or cents(quote) <= 0):
        raise ValueError("A sufficient active reservation within the original total cap is required")


class SSH:
    def __init__(self, connection):
        host, port = connection["host"], connection["port"]
        if not re.fullmatch(r"[A-Za-z0-9.-]+", host) or type(port) is not int or not 1 <= port <= 65535:
            raise ValueError("Invalid direct SSH endpoint")
        self.peer, self.port = "root@" + host, port
        # macOS TMPDIR can exceed the Unix socket path limit. Keep the private
        # control directory short, unique and owned by this collector instance.
        self.control_directory = tempfile.TemporaryDirectory(prefix="video-ssh-", dir="/tmp")
        self.control_path = str(Path(self.control_directory.name) / "control")
        self.options = ["-i", str(Path(connection["identity_file"]).resolve()),
                        "-o", "IdentitiesOnly=yes", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
                        "-o", "StrictHostKeyChecking=accept-new", "-o",
                        "UserKnownHostsFile=" + str(Path(connection["known_hosts_file"]).resolve()),
                        "-o", "ControlMaster=auto", "-o", "ControlPersist=30",
                        "-o", "ControlPath=" + self.control_path]

    def run(self, code, timeout=15):
        try:
            result = subprocess.run(["ssh", *self.options, "-p", str(self.port), self.peer,
                shlex.join(["python3", "-c", code])], capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise ConnectionError("SSH observation timed out; original work remains uncertain") from exc
        if result.returncode:
            raise ConnectionError("SSH operation failed; do not resubmit")
        return result.stdout

    def download(self, remote_path, local_path, timeout):
        # Resume the same immutable artifact after a slow or interrupted transfer.
        # The collector verifies the producer's SHA-256 before accepting the file.
        local_path = Path(local_path)
        offset = local_path.stat().st_size if local_path.exists() else 0
        code = ("import os,sys,shutil;f=open(" + repr(remote_path) + ", 'rb');"
                "assert os.fstat(f.fileno()).st_size >= " + str(offset) + ";"
                "f.seek(" + str(offset) + ");shutil.copyfileobj(f,sys.stdout.buffer)")
        try:
            with local_path.open("ab") as output:
                result = subprocess.run(["ssh", *self.options, "-p", str(self.port), self.peer,
                    shlex.join(["python3", "-c", code])], stdout=output, stderr=subprocess.PIPE,
                    timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise ConnectionError("Artifact transfer timed out; partial bytes retained") from exc
        if result.returncode:
            raise ConnectionError("Artifact transfer failed; partial bytes retained")


    def close(self):
        if self.control_directory is None:
            return
        try:
            # -O exit addresses only our private control socket; it cannot
            # terminate another collector's connection or the remote worker.
            subprocess.run(["ssh", *self.options, "-O", "exit", "-p", str(self.port), self.peer],
                           capture_output=True, timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            pass  # A surviving idle master expires after ControlPersist.
        finally:
            self.control_directory.cleanup()
            self.control_directory = None


def inspect_output(path, profile, timeout):
    try:
        subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(path), "-f", "null", "-"],
                       capture_output=True, check=True, timeout=timeout)
    except subprocess.CalledProcessError:
        return False, False
    data = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(path)],
                                             timeout=timeout))
    video = [s for s in data["streams"] if s["codec_type"] == "video"]
    audio = [s for s in data["streams"] if s["codec_type"] == "audio"]
    contract = (len(video) == 1 and bool(audio) == profile["audio"]
                and video[0].get("width") == profile["width"] and video[0].get("height") == profile["height"]
                and int(video[0].get("nb_frames", -1)) == profile["frames"]
                and Fraction(video[0]["r_frame_rate"]) == profile["fps"])
    return True, contract


def collect(manifest, connection, ledger, reservation_id, lease_bound, destination):
    plan, manifest_digest = read_manifest(manifest)
    verify_reservation(json.loads(ledger.read_text()), reservation_id, lease_bound)
    destination.mkdir(mode=0o700)  # The durable, exclusive controller claim.
    remote = "/root/benchmark/" + plan["run_id"]
    ssh = SSH(json.loads(connection.read_text()))
    deadline = plan["limits"]["shutdown_deadline_epoch"]
    cutoff = plan["limits"]["admission_deadline_epoch"]
    controller_deadline = time.monotonic() + deadline - time.time()
    delivery = {"version": 1, "run_id": plan["run_id"], "clock": "controller_monotonic",
                "window_seconds": None, "worker_observed_until_seconds": 0, "receipts": [],
                "trigger_claimed": False, "controller_complete": False,
                "transport": "ssh_multiplexed_private_control_socket"}
    write_json(destination / "delivery.json", delivery)
    started, exported, events = None, set(), []
    try:
        while time.time() < deadline and time.monotonic() < controller_deadline:
            remaining = min(deadline - time.time(), controller_deadline - time.monotonic())
            try:
                text = ssh.run("from pathlib import Path; p=Path(" + repr(remote + "/events.jsonl") + "); "
                    "s=p.read_text() if p.exists() else ''; print(s[:s.rfind('\\n')+1],end='')",
                    timeout=max(.1, min(15, remaining)))
            except ConnectionError:
                time.sleep(.25)
                continue
            fresh = [json.loads(line) for line in text.splitlines()]
            if fresh[:len(events)] != events:
                raise ValueError("Worker log was rewritten or truncated")
            events = fresh
            for index, event in enumerate(events):
                if event.get("run_id") != plan["run_id"] or event.get("sequence") != index:
                    raise ValueError("Unexpected worker log identity or sequence")
            (destination / "events.jsonl").write_text(text)
            if not delivery["trigger_claimed"]:
                if any(e["event"] == "worker_failed" for e in events):
                    raise RuntimeError("Worker failed before admission; retain setup expenses")
                if time.time() >= cutoff:
                    raise TimeoutError("No ready worker before admission cutoff")
                if not any(e["event"] == "ready" for e in events):
                    time.sleep(.25)
                    continue
                prep = next(e for e in events if e["event"] == "preparing")
                if (prep["manifest_sha256"] != manifest_digest or prep["profile"] != plan["profile"]
                        or sha256(manifest) != manifest_digest):
                    raise ValueError("Prepared worker differs from the frozen manifest")
                verify_reservation(json.loads(ledger.read_text()), reservation_id, lease_bound)
                started = time.monotonic()
                delivery.update(trigger_claimed=True, submitted_at_epoch=time.time(), controller_monotonic_start=started)
                write_json(destination / "delivery.json", delivery)
                trigger = {"run_id": plan["run_id"], "manifest_sha256": manifest_digest}
                code = ("import json,os; from pathlib import Path; "
                    "g=json.loads(Path('/root/benchmark/guard-ready.json').read_text()); "
                    "assert g['read_own_pod_verified'] is True and g['deadline']==" + repr(deadline) + "; "
                    "os.kill(g['pid'],0); p=Path(" + repr(remote + "/start.json") + "); "
                    "pending=p.with_suffix('.pending'); f=pending.open('x'); json.dump(" + repr(trigger) +
                    ",f); f.flush(); os.fsync(f.fileno()); f.close(); os.link(pending,p); pending.unlink()")
                try:
                    ssh.run(code, timeout=max(.1, min(15, cutoff - time.time())))
                except ConnectionError:
                    # A lost response is not evidence that the trigger was absent.
                    pass
                continue
            delivery["worker_observed_until_seconds"] = time.monotonic() - started
            for event in events:
                if event["event"] != "artifact_ready" or event["request_id"] in exported:
                    continue
                if event["request_id"] not in {r["request_id"] for r in plan["requests"] + plan.get("retry_requests", [])}:
                    raise ValueError("Unplanned output")
                filename = event["request_id"] + ".mp4"
                if event["artifact"] != filename:
                    raise ValueError("Unexpected artifact path")
                target = destination / filename
                partial = destination / (filename + ".part")
                remaining = min(deadline - time.time(), controller_deadline - time.monotonic())
                if remaining <= 1:
                    break
                try:
                    ssh.download(remote + "/" + filename, partial, timeout=min(60, remaining))
                except ConnectionError:
                    break  # Retry transfer of the same immutable artifact only.
                if sha256(partial) != event["artifact_sha256"]:
                    raise ValueError("Exported artifact hash differs from producer")
                os.replace(partial, target)
                delivered_at = time.monotonic() - started
                decode, contract = inspect_output(target, plan["profile"], timeout=max(.1, min(20, controller_deadline - time.monotonic())))
                delivery["receipts"].append({"request_id": event["request_id"], "artifact_sha256": event["artifact_sha256"],
                    "delivered_at_seconds": delivered_at, "decode_verified": decode, "output_contract_pass": contract})
                exported.add(event["request_id"])
                write_json(destination / "delivery.json", delivery)
                if not decode or not contract:
                    ssh.run("from pathlib import Path; Path(" + repr(remote + "/stop.json") + ").touch()",
                            timeout=max(.1, min(10, controller_deadline - time.monotonic())))
            closed = any(e["event"] in ("window_finished", "worker_failed") for e in events)
            ready_ids = {e["request_id"] for e in events if e["event"] == "artifact_ready"}
            if closed and ready_ids <= exported:
                delivery["controller_complete"] = True
                break
            time.sleep(.25)
    finally:
        try:
            if delivery["trigger_claimed"] and not delivery["controller_complete"]:
                try:
                    ssh.run("from pathlib import Path; Path(" + repr(remote + "/stop.json") + ").touch()", timeout=5)
                except ConnectionError:
                    pass  # The independent lease guard remains authoritative.
            if started is not None:
                delivery["window_seconds"] = time.monotonic() - started
            write_json(destination / "delivery.json", delivery)
        finally:
            ssh.close()
    return delivery


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest", "connection", "ledger", "destination"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--reservation-id", required=True)
    parser.add_argument("--lease-bound-usd", required=True)
    args = parser.parse_args()
    result = collect(args.manifest, args.connection, args.ledger, args.reservation_id,
                     args.lease_bound_usd, args.destination)
    print(json.dumps(result, indent=2))
