"""Independent local account/lease guard and scoped on-instance traffic guard."""

import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import time

from vast_api import API, APIError, SafetyError, save

# Embedded at create time: no downloads, no account key, and no full worker startup.
# It watches the absolute deadline even before SSH/helper upload becomes available.
BOOTSTRAP = r'''
import json,os,pathlib,subprocess,time,urllib.request
p=pathlib.Path('/root/benchmark');p.mkdir(mode=448,exist_ok=True)
c=json.loads(os.environ['VAST_BENCHMARK_CONFIG'])
i=int(os.environ['CONTAINER_ID']);k=os.environ['CONTAINER_API_KEY']
u='https://console.vast.ai/api/v0/instances/'+str(i)+'/'
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None
opener=urllib.request.build_opener(NoRedirect())
def request(method,data=None):
 r=urllib.request.Request(u,method=method,data=None if data is None else json.dumps(data).encode(),headers={'Authorization':'Bearer '+k,'Content-Type':'application/json'})
 with opener.open(r,timeout=10) as f:return json.load(f)
def owned(d):
 return d.get('id')==i and d.get('label')==c['label'] and d.get('machine_id')==c['quote']['machine_id']
while True:
 try:
  d=request('GET')['instances']
  if not owned(d):raise RuntimeError('ownership')
  (p/'boot-ready.json').write_text(json.dumps({'instance_id':i,'label':c['label'],'heartbeat':time.time()}))
  (p/'boot-ready.json').chmod(384)
  if time.time()>=c['deadline']-120:
   request('DELETE')
  elif (p/'remote-launch').exists():
   os.execv('/usr/bin/env',['env','python3.12',str(p/'vast_deadline.py'),'remote'])
 except Exception:pass
 time.sleep(3)
'''


def accounting_exposure(baseline, current, previous=None):
    """Conservative observed spend, not a provider-enforced cap or final invoice."""
    from vast_trial import number
    # Account JSON contains binary-float summation artifacts below a trillionth USD.
    roundoff = number("0.000000000001")
    credit_delta = number(baseline["credit"], signed=True) - number(current["credit"], signed=True)
    if credit_delta < -roundoff:
        raise SafetyError("Unexpected credit increase: account baseline no longer isolates this trial")
    if previous is not None and number(current["credit"], signed=True) > number(previous["credit"], signed=True) + roundoff:
        raise SafetyError("Account credit increased during lease; cannot attribute spend safely")
    spent = max(number(0), credit_delta)
    if baseline.get("total_spend") is not None:
        if current.get("total_spend") is None:
            raise SafetyError("Account total_spend counter disappeared")
        # Vast records cumulative usage debits as negative amounts.
        delta = number(baseline["total_spend"], signed=True) - number(current["total_spend"], signed=True)
        if delta < -roundoff or (previous and number(current["total_spend"], signed=True) > number(previous["total_spend"], signed=True) + roundoff):
            raise SafetyError("Account spend counter reset")
        spent = max(spent, delta)
    return spent


def stop_reason(state, now, spent, inbound=None, outbound=None):
    from vast_trial import number
    if spent >= number(state.get("reservation_usd", "8.00")) - number("1.60"):
        return "account_or_estimated_exposure_limit"
    start = state.get("create_requested_at")
    if not start:
        return None
    if now >= state["deadline"] - 120:
        return "deadline_closeout_reserve"
    if not state.get("prepared_at") and now >= start + 1800:
        return "preparation_cutoff"
    for case in state.get("cases", {}).values():
        if case.get("status") == "submission_claimed" and now >= case["submitted_at"] + 300:
            return "generation_timeout"
    if inbound is not None:
        # Budget image traffic outside the namespace separately; reserve 2 GB for detection/closeout.
        allowance = 100_000_000_000 - state["transfer_admission"]["image_compressed_bytes"] - 2_000_000_000
        if inbound >= allowance:
            return "inbound_transfer_headroom"
    if outbound is not None and outbound >= 4_000_000_000:
        return "outbound_transfer_headroom"
    return None


def local_guard(api, lease):
    from vast_trial import (ACCOUNT_FIELDS, account, accounting_estimate, cleanup_key, discover,
                            identifier, number, read_remote, read_state)
    # A separate journal and lock ensure that the controller never clobbers guard evidence.
    with (lease / "guard.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SafetyError("Independent guard already running") from None
        state = read_state(lease)
        baseline = state.get("stage_account_baseline") or state.get("account_before_create") or account(api)
        prior_exposure = number(state.get("prior_exposure_usd", "0"))
        observation = {"run_id": state["run_id"], "label": state["label"], "instance_id": state.get("instance_id"),
                       "pid": os.getpid(), "status": "watching", "heartbeat": time.time(),
                       "absence_verified": False, "verified_absent_at": None, "stop_reason": None,
                       "account_baseline": baseline, "billing_lag": "Provider says every few seconds; no guaranteed lag bound",
                       "prior_exposure_usd": str(prior_exposure),
                       "closeout_reserve_usd": "1.60"}
        save(lease / "guard-state.json", observation)
        print("guard-ready", flush=True)
        previous = state.get("account_before_create") or state.get("prior_account_at_close") or baseline
        while True:
            try:
                state = read_state(lease)
            except (OSError, ValueError, SafetyError):
                # Retain the last valid ownership record and attempt closeout,
                # rather than abandoning a paid lease on a damaged journal.
                observation["stop_reason"] = "controller_journal_unavailable"
            if observation["instance_id"] is not None and state.get("instance_id") is None:
                state["instance_id"] = observation["instance_id"]
            candidate = state.get("stage_account_baseline") or state.get("account_before_create")
            if candidate and any(candidate.get(key) != baseline.get(key) for key in ACCOUNT_FIELDS):
                observation["stop_reason"] = "cumulative_account_baseline_changed"
            if number(state.get("prior_exposure_usd", "0")) != prior_exposure:
                observation["stop_reason"] = "prior_exposure_hold_changed"
            now = time.time()
            row = None
            listing_ok = False
            try:
                rows = api.instances()
                owned = [item for item in rows if item.get("label") == state["label"] or item.get("id") == state.get("instance_id")]
                from vast_trial import owns
                if len(owned) > 1 or any(not owns(item, state) for item in owned):
                    raise SafetyError("Ownership collision in local guard")
                if owned:
                    row = owned[0]
                    state["instance_id"] = identifier(row["id"])
                    observation["instance_id"] = row["id"]
                if len(rows) != len(owned):
                    observation["stop_reason"] = "unrelated_resource_detected_account_spend_not_isolated"
                listing_ok = True
                current = account(api)
                if time.time() - current["observed_at"] > 20:
                    raise SafetyError("Stale account observation")
                spent = accounting_exposure(baseline, current, previous)
                previous = current
                observation.update(account=current, observed_exposure_usd=str(spent))
                observation["stop_reason"] = observation["stop_reason"] or stop_reason(
                    state, now, max(spent, prior_exposure))
                if state.get("create_requested_at"):
                    inbound = outbound = None
                    if (lease / "connection.json").exists():
                        connection = json.loads((lease / "connection.json").read_text())
                        traffic = read_remote(lease, connection, "guard-ready.json")
                        if traffic and time.time() - traffic.get("heartbeat", 0) <= 15:
                            inbound, outbound = traffic.get("inbound_bytes"), traffic.get("outbound_bytes")
                            observation.update(inbound_bytes=inbound, outbound_bytes=outbound)
                            if traffic.get("stop_reason"):
                                observation["stop_reason"] = "remote_guard_stop"
                        else:
                            observation["stop_reason"] = "remote_counter_stale_or_unavailable"
                    estimated = accounting_estimate(state, now, inbound, outbound)
                    observation["estimated_exposure_usd"] = str(estimated)
                    reason = stop_reason(state, now, max(spent, estimated), inbound, outbound)
                    observation["stop_reason"] = observation["stop_reason"] or reason
            except (APIError, SafetyError, OSError, ValueError, subprocess.SubprocessError) as exc:
                # Missing/stale control observations are not permission to keep spending.
                observation["stop_reason"] = observation["stop_reason"] or "control_observation_failed"
                observation.setdefault("control_observation_error", {
                    "type": type(exc).__name__, "http_status": getattr(exc, "status", None),
                    "reason": str(exc) if isinstance(exc, (APIError, SafetyError)) else "Private transport/read failure"})
            if state.get("close_requested_at"):
                observation["stop_reason"] = observation["stop_reason"] or "controller_close_requested"
            if observation["stop_reason"]:
                observation["status"] = "closing"
                try:
                    if listing_ok and row is not None:
                        api.request("DELETE", "/api/v0/instances/%d/" % identifier(row["id"]))
                    # Always perform a second independent account listing after a delete attempt.
                    absent = discover(api, state) is None
                    known_allocation = state.get("instance_id") is not None or not state.get("create_requested_at")
                    if absent and known_allocation:
                        observation.update(absence_verified=True, verified_absent_at=time.time())
                        if cleanup_key(api, lease, state):
                            observation.update(status="closed", ssh_key_removed=True, heartbeat=time.time())
                            save(lease / "guard-state.json", observation)
                            print("guard-closeout-verified", flush=True)
                            return 0
                    # Empty listings after an ambiguous create never release the reservation.
                except (APIError, SafetyError, OSError, ValueError) as exc:
                    observation["cleanup_pending"] = True
                    observation["cleanup_error"] = {"type": type(exc).__name__, "http_status": getattr(exc, "status", None)}
            observation["heartbeat"] = time.time()
            save(lease / "guard-state.json", observation)
            time.sleep(3)


def network_counters(root=Path("/sys/class/net")):
    incoming = outgoing = 0
    names = sorted(path.name for path in root.iterdir() if path.name != "lo")
    if not names:
        raise SafetyError("No observable network interfaces")
    for name in names:
        base = root / name / "statistics"
        incoming += int((base / "rx_bytes").read_text())
        outgoing += int((base / "tx_bytes").read_text())
    return names, incoming, outgoing


def remote_main():
    base = Path("/root/benchmark")
    config = json.loads(os.environ["VAST_BENCHMARK_CONFIG"])
    instance_id = int(os.environ["CONTAINER_ID"])
    api = API(os.environ.pop("CONTAINER_API_KEY"))
    path = "/api/v0/instances/%d/" % instance_id
    from decimal import Decimal
    reason = None
    ready = {"run_id": config["run_id"], "label": config["label"], "instance_id": instance_id,
             "deadline": config["deadline"], "pid": os.getpid(), "stop_reason": None,
             "delete_permission_documented": True, "read_own_instance_verified": False,
             "self_manage_verified": False}

    def owned(row):
        return (row.get("id") == instance_id and row.get("label") == config["label"]
                and row.get("machine_id") == config["quote"]["machine_id"])

    try:
        row = api.request("GET", path)["instances"]
        if not owned(row):
            raise SafetyError("Instance-scoped ownership mismatch")
        ready["read_own_instance_verified"] = True
        # Probe instance_write with an identical label, never a runtime state change.
        # The same provider-injected per-instance credential is documented to allow destroy.
        result = api.request("PUT", path, {"label": config["label"]})
        if result.get("success") is not True:
            raise SafetyError("Instance-scoped manage permission not verified")
        ready["self_manage_verified"] = True
        names, previous_in, previous_out = network_counters()
    except Exception:
        reason = "remote_permission_or_counter_verification_failed"
        names, previous_in, previous_out = [], 0, 0
    while True:
        now = time.time()
        try:
            current_names, incoming, outgoing = network_counters()
            if current_names != names or incoming < previous_in or outgoing < previous_out:
                raise SafetyError("Network counter reset or interface changed")
            previous_in, previous_out = incoming, outgoing
            ready.update(inbound_bytes=incoming, outbound_bytes=outgoing)
            preboot = config["transfer_admission"]["image_compressed_bytes"]
            if incoming >= 100_000_000_000 - preboot - 2_000_000_000:
                reason = reason or "inbound_transfer_headroom"
            if outgoing >= 4_000_000_000:
                reason = reason or "outbound_transfer_headroom"
            quote = config["quote"]
            estimated = (Decimal(str(config.get("prior_exposure_usd", "0")))
                         + Decimal(str(max(0, now - config["create_requested_at"]))) / 3600 * Decimal(str(quote["dph_total"]))
                         + Decimal(incoming + preboot) / 1_000_000_000 * Decimal(str(quote["inet_down_cost"]))
                         + Decimal(outgoing) / 1_000_000_000 * Decimal(str(quote["inet_up_cost"])))
            ready["estimated_exposure_usd"] = str(estimated)
            if estimated >= Decimal(str(config.get("reservation_usd", "8.00"))) - Decimal("1.60"):
                reason = reason or "estimated_exposure_limit"
        except Exception:
            reason = reason or "network_counters_unavailable"
        if now >= config["deadline"] - 120:
            reason = reason or "deadline_closeout_reserve"
        prepare_path = base / "prepare-status.json"
        try:
            prepared = prepare_path.exists() and json.loads(prepare_path.read_text()).get("phase") == "ready"
            if not prepared and now >= config["create_requested_at"] + 1800:
                reason = reason or "preparation_cutoff"
            service_path = base / "reuse-service-status.json"
            service = json.loads(service_path.read_text()) if service_path.exists() else {}
            for request in base.glob(config["run_id"] + "_*.request.json"):
                case = json.loads(request.read_text())["case"]
                if now >= request.stat().st_mtime + 300 and not (service.get("case") == case and service.get("phase") in ("completed", "ready", "finished")):
                    ack = request.with_name(request.name.removesuffix(".request.json") + ".exported")
                    if not ack.exists():
                        reason = reason or "generation_timeout"
                if request.stat().st_mtime >= config["create_requested_at"] + 2100:
                    reason = reason or "late_generation_submission"
        except Exception:
            reason = reason or "work_protocol_observation_failed"
        if reason:
            (base / "vast-stop").touch(exist_ok=True)
            # Freeze owned worker process groups before deletion; stopping is NOT closeout.
            for phase in ("prepare", "reuse"):
                try:
                    pid = int((base / (phase + ".pid")).read_text())
                    os.killpg(pid, __import__("signal").SIGKILL)
                except (OSError, ValueError):
                    pass
            ready.update(stop_reason=reason, heartbeat=now)
            save(base / "guard-ready.json", ready)
            try:
                row = api.request("GET", path)["instances"]
                if owned(row):
                    api.request("DELETE", path)
            except APIError as exc:
                if exc.status == 404:
                    return 0
            except Exception:
                pass
        else:
            ready.update(heartbeat=now)
            save(base / "guard-ready.json", ready)
        time.sleep(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("remote",))
    parser.parse_args()
    raise SystemExit(remote_main())
