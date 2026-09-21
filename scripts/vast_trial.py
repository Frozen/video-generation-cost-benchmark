"""Verified-only Vast LTX stage with separately authorized, cumulative-cost attempts."""

import argparse
import base64
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation, ROUND_CEILING
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import shutil
import subprocess
import tarfile
import time
from urllib.parse import urlencode

from check_access import load_keys
from ltx_config import FILES, IMAGE, PROMPT_SHA256, REVISION, SOURCE, validate_prompt
from ltx_reuse_config import (VAST_RUN_ID, VAST_RETRY_RUN_ID, VAST_RECOVERY_RUN_ID, VAST_HANDOFF_RUN_ID, VAST_RESUME_RUN_ID, VAST_PROXY_RUN_ID, VAST_STABLE_RUN_ID, VAST_ALTERNATE_RUN_ID,
                              VAST_EXTENDED_RUN_IDS, VAST_RUN_IDS, case_settings, cases_for, output_id)
from vast_api import API, APIError, SafetyError, save

ROOT = Path(__file__).resolve().parents[1]
RUN_ID = VAST_RUN_ID
LEASE = ROOT / "private/vast-h100-p01-001"
RETRY_LEASE = ROOT / "private/vast-h100-p01-002"
RECOVERY_LEASE = ROOT / "private/vast-h100-p01-003"
HANDOFF_LEASE = ROOT / "private/vast-h100-p01-004"
RESUME_LEASE = ROOT / "private/vast-h100-p01-005"
PROXY_LEASE = ROOT / "private/vast-h100-p01-006"
STABLE_LEASE = ROOT / "private/vast-h100-p01-007"
ALTERNATE_LEASE = ROOT / "private/vast-h100-p01-008"
INPUT = ROOT / "private/vast-preflight"
SECONDS = 2700
PREPARATION_SECONDS = 1800
SUBMISSION_SECONDS = 2100
GENERATION_SECONDS = 300
STOP_USD = Decimal("6.40")
MAX_HOURLY = Decimal("4.10")
QUOTE_FIELDS = ("id", "machine_id", "gpu_name", "num_gpus", "gpu_ram", "cpu_ram", "driver_version",
                "cuda_max_good", "reliability", "verification", "dph_base", "dph_total",
                "storage_total_cost", "storage_cost", "inet_down_cost", "inet_up_cost")
ACCOUNT_FIELDS = ("credit", "can_pay", "total_spend")
SEARCH = {"type": "on-demand", "allocated_storage": 200, "limit": 100,
          "verified": {"eq": True}, "verification": {"eq": "verified"},
          "rentable": {"eq": True}, "rented": {"eq": False},
          "gpu_name": {"eq": "H100 SXM"}, "num_gpus": {"eq": 1}, "gpu_ram": {"gte": 80000},
          "cpu_ram": {"gte": 64000}, "disk_space": {"gte": 200}, "cpu_arch": {"eq": "amd64"},
          "cuda_max_good": {"gte": 13.2}, "reliability": {"gte": 0.99},
          "direct_port_count": {"gte": 1}, "dph_total": {"lte": float(MAX_HOURLY)},
          "inet_down_cost": {"lte": 0.04}, "inet_up_cost": {"lte": 0.04},
          "order": [["dph_total", "asc"]]}


def number(value, *, signed=False):
    if isinstance(value, bool):
        raise SafetyError("Boolean used as a monetary or numeric value")
    try:
        result = Decimal(str(value))
    except InvalidOperation:
        raise SafetyError("Required finite numeric value missing") from None
    if not result.is_finite() or (not signed and result < 0):
        raise SafetyError("Required finite numeric value outside its allowed range")
    return result


def identifier(value):
    if type(value) is not int or value <= 0:
        raise SafetyError("Invalid provider resource identifier")
    return value


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def client(env_file):
    return API(load_keys(env_file, {"vast": ("VAST_API_KEY", "VAST_API", "VASTAI_API_KEY")})["vast"])


def account(api):
    raw = api.request("GET", "/api/v0/users/current/")
    if not isinstance(raw, dict):
        raise SafetyError("Invalid account response")
    raw = raw.get("user", raw)
    result = {field: raw.get(field) for field in ACCOUNT_FIELDS}
    result["credit"] = str(number(result["credit"], signed=True))
    if result["total_spend"] is not None:
        result["total_spend"] = str(number(result["total_spend"], signed=True))
    if type(result["can_pay"]) is not bool:
        raise SafetyError("Missing account can_pay flag")
    return dict(result, observed_at=time.time())


def require_credit(snapshot, run_id=RUN_ID, baseline=None):
    remaining = stage_allowance(run_id)
    if baseline is not None:
        from vast_deadline import accounting_exposure
        remaining = max(Decimal(0), remaining - accounting_exposure(baseline, snapshot))
    if snapshot["can_pay"] is not True or number(snapshot["credit"]) < remaining:
        raise SafetyError("Funding pending: remaining approved allowance must be prepaid and can_pay=true; no provider mutation allowed")


def require_run_id(run_id):
    if run_id not in VAST_RUN_IDS:
        raise SafetyError("Unapproved Vast attempt identity")
    return run_id


def default_lease(run_id):
    require_run_id(run_id)
    return {RUN_ID: LEASE, VAST_RETRY_RUN_ID: RETRY_LEASE, VAST_RECOVERY_RUN_ID: RECOVERY_LEASE,
            VAST_HANDOFF_RUN_ID: HANDOFF_LEASE, VAST_RESUME_RUN_ID: RESUME_LEASE, VAST_PROXY_RUN_ID: PROXY_LEASE,
            VAST_STABLE_RUN_ID: STABLE_LEASE, VAST_ALTERNATE_RUN_ID: ALTERNATE_LEASE}[run_id]


def stage_allowance(run_id):
    require_run_id(run_id)
    return Decimal("9.99") if run_id in (VAST_HANDOFF_RUN_ID, VAST_RESUME_RUN_ID, VAST_PROXY_RUN_ID, VAST_STABLE_RUN_ID, VAST_ALTERNATE_RUN_ID) else Decimal("8.00")


def quote_envelope(quote):
    return (Decimal(SECONDS) / 3600 * number(quote["dph_total"])
            + 100 * number(quote["inet_down_cost"]) + 5 * number(quote["inet_up_cost"]))


def admit_stage(quote, prior_exposure="0", observed_exposure="0", allowance="8.00"):
    exposure = max(number(prior_exposure), number(observed_exposure))
    limit = number(allowance)
    if exposure >= limit - Decimal("1.60") or exposure + quote_envelope(quote) > limit:
        raise SafetyError("Prior exposure plus the new lease/traffic envelope exceeds the cumulative stage allowance")


def check_quote(offer, run_id=RUN_ID):
    require_run_id(run_id)
    if run_id == VAST_ALTERNATE_RUN_ID and offer.get("machine_id") == 108977:
        raise SafetyError("This host failed both proxy and direct SSH; the alternate run must use a different verified host")
    minimum_cuda = Decimal("13.0") if run_id in (VAST_PROXY_RUN_ID, VAST_STABLE_RUN_ID, VAST_ALTERNATE_RUN_ID) else Decimal("13.2")
    maximum_hourly = Decimal("5.10") if run_id in (VAST_PROXY_RUN_ID, VAST_STABLE_RUN_ID, VAST_ALTERNATE_RUN_ID) else MAX_HOURLY
    if (offer.get("verification") != "verified" or offer.get("rentable") is not True
            or offer.get("rented") is not False or offer.get("cpu_arch") != "amd64"
            or offer.get("gpu_name", "").replace("_", " ") != "H100 SXM"
            or offer.get("num_gpus") != 1 or number(offer.get("gpu_ram")) < 80000
            or number(offer.get("cpu_ram")) < 64000 or number(offer.get("disk_space")) < 200
            or number(offer.get("cuda_max_good")) < minimum_cuda
            or number(offer.get("reliability", offer.get("reliability2"))) < Decimal("0.99")
            or number(offer.get("direct_port_count")) < 1):
        raise SafetyError("Offer fails verified H100 SXM admission")
    identifier(offer.get("id"))
    identifier(offer.get("machine_id"))
    base = number(offer.get("dph_base"))
    storage = number(offer.get("storage_total_cost"))
    total = number(offer.get("dph_total"))
    # Both totals must fit; never treat compute-only price as the disk-inclusive quote.
    if total > maximum_hourly or base + storage > maximum_hourly or total + Decimal("0.000001") < base + storage:
        raise SafetyError(f"Compute plus allocated 200 GB storage exceeds USD {maximum_hourly}/hour or is inconsistent")
    if any(number(offer.get(key)) > Decimal("0.04") for key in ("inet_down_cost", "inet_up_cost")):
        raise SafetyError("Transfer quote exceeds USD 0.04/GB")
    quote = {field: offer.get(field) for field in QUOTE_FIELDS}
    quote["reliability"] = offer.get("reliability", offer.get("reliability2"))
    quote["gpu_name"] = "H100 SXM"
    quote["allocated_storage"] = 200
    for field in QUOTE_FIELDS:
        if field not in ("gpu_name", "verification", "driver_version"):
            value = number(quote[field])
            quote[field] = int(value) if value == value.to_integral_value() else float(value)
    if not isinstance(quote["driver_version"], str) or not re.fullmatch(r"\d+\.\d+(?:\.\d+)?", quote["driver_version"]):
        raise SafetyError("Missing quote driver version")
    if run_id in (VAST_PROXY_RUN_ID, VAST_STABLE_RUN_ID, VAST_ALTERNATE_RUN_ID) and int(quote["driver_version"].split(".")[0]) < 580:
        raise SafetyError("CUDA 13.x minor-version compatibility requires NVIDIA driver 580 or newer")
    return quote


def offers(api, selected=None, run_id=RUN_ID):
    require_run_id(run_id)
    query = dict(SEARCH)
    if run_id in (VAST_PROXY_RUN_ID, VAST_STABLE_RUN_ID, VAST_ALTERNATE_RUN_ID):
        query.update(cuda_max_good={"gte": 13.0}, dph_total={"lte": 5.10})
    if selected is not None:
        identifier(selected)
    response = api.request("POST", "/api/v0/bundles/", query)
    if not isinstance(response, dict) or not isinstance(response.get("offers"), list):
        raise SafetyError("Invalid offer search response")
    eligible = []
    for offer in response["offers"]:
        try:
            quote = check_quote(offer, run_id)
        except (SafetyError, TypeError, AttributeError):
            continue
        if selected is None or quote["id"] == selected:
            eligible.append(quote)
    return eligible


def approval(path, run_id=RUN_ID):
    require_run_id(run_id)
    data = json.loads(path.read_text())
    expected = {"status": "approved", "provider": "vast.ai", "run_id": run_id,
                "verified_only": True, "max_usd": "8.00",
                "budget_scope": "new_additional_vast_stage_not_historical_ledger_reset",
                "max_instances": 1, "gpu_name": "H100 SXM", "gpu_count": 1,
                "max_lease_seconds": SECONDS, "case_order": [case for case, _, _ in cases_for(run_id)],
                "prompt_sha256": PROMPT_SHA256, "allow_temporary_ssh_key": True,
                "allow_owned_resource_deletion": True, "automatic_generation_retries": 0}
    if run_id in VAST_EXTENDED_RUN_IDS:
        expected.update(budget_scope="cumulative_vast_stage_including_first_attempt", prior_run_id=RUN_ID,
                        max_stage_paid_creates=2, max_additional_paid_creates=1, cumulative_allowance_usd="8.00",
                        requested_durations_seconds=[5, 20], measured_outputs=4, technical_warmups=2)
    if run_id == VAST_RECOVERY_RUN_ID:
        expected.update(max_stage_paid_creates=3, previous_run_id=VAST_RETRY_RUN_ID)
    if run_id == VAST_HANDOFF_RUN_ID:
        expected.update(max_stage_paid_creates=4, previous_run_id=VAST_RECOVERY_RUN_ID,
                        max_usd="9.99", cumulative_allowance_usd="9.99")
    if run_id == VAST_RESUME_RUN_ID:
        expected.update(max_stage_paid_creates=5, previous_run_id=VAST_HANDOFF_RUN_ID,
                        max_usd="9.99", cumulative_allowance_usd="9.99")
    if run_id == VAST_PROXY_RUN_ID:
        expected.update(max_stage_paid_creates=6, previous_run_id=VAST_RESUME_RUN_ID,
                        max_usd="9.99", cumulative_allowance_usd="9.99",
                        cuda_compatibility="CUDA 13.x minor-version compatibility, driver >= 580",
                        max_hourly_compute_and_disk_usd="5.10", ssh_transport="proxy")
    if run_id == VAST_STABLE_RUN_ID:
        expected.update(max_stage_paid_creates=7, previous_run_id=VAST_PROXY_RUN_ID,
                        max_usd="9.99", cumulative_allowance_usd="9.99",
                        cuda_compatibility="CUDA 13.x minor-version compatibility, driver >= 580",
                        max_hourly_compute_and_disk_usd="5.10", ssh_transport="direct")
    if run_id == VAST_ALTERNATE_RUN_ID:
        expected.update(max_stage_paid_creates=8, previous_run_id=VAST_STABLE_RUN_ID,
                        max_usd="9.99", cumulative_allowance_usd="9.99",
                        cuda_compatibility="CUDA 13.x minor-version compatibility, driver >= 580",
                        max_hourly_compute_and_disk_usd="5.10", ssh_transport="direct",
                        excluded_machine_ids=[108977])
    if any(data.get(key) != value or type(data.get(key)) is not type(value) for key, value in expected.items()):
        raise SafetyError("Approval does not authorize this exact Vast identity, case order and cumulative allowance")
    return expected


def inputs(input_dir, archive, run_id=RUN_ID):
    require_run_id(run_id)
    filename = {RUN_ID: "approval.json", VAST_RETRY_RUN_ID: "retry-approval.json",
                VAST_RECOVERY_RUN_ID: "recovery-approval.json", VAST_HANDOFF_RUN_ID: "handoff-approval.json",
                VAST_RESUME_RUN_ID: "resume-approval.json", VAST_PROXY_RUN_ID: "proxy-approval.json",
                VAST_STABLE_RUN_ID: "stable-approval.json", VAST_ALTERNATE_RUN_ID: "alternate-approval.json"}[run_id]
    approved = approval(input_dir / filename, run_id)
    request = json.loads((input_dir / "request.json").read_text())
    validate_prompt(request.get("prompt", ""))
    if request.get("seed") != 42 or type(request.get("seed")) is not int:
        raise SafetyError("Frozen seed 42 required")
    actual = digest(archive)
    expected = archive.with_suffix(archive.suffix + ".sha256").read_text().split()[0]
    if actual != expected or not re.fullmatch("[0-9a-f]{64}", expected):
        raise SafetyError("Pinned source archive digest mismatch")
    with tarfile.open(archive, "r:gz") as source:
        members = source.getmembers()
        names = [member.name.rstrip("/") for member in members]
        if len(set(names)) != len(names):
            raise SafetyError("Duplicate archive paths")
        for member in members:
            path = Path(member.name)
            if (path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] != "ltx-source"
                    or not (member.isdir() or member.isfile())):
                raise SafetyError("Unsafe pinned source archive member")
        revision = source.extractfile("ltx-source/.source-revision").read().decode().strip()
        lock = source.extractfile("ltx-source/uv.lock").read()
        if revision != SOURCE or not lock:
            raise SafetyError("Pinned source revision or locally frozen dependency lock missing")
    return approved, {"prompt": request["prompt"], "seed": 42}, {
        "source_archive_sha256": actual, "source_archive_bytes": archive.stat().st_size,
        "dependency_lock_sha256": hashlib.sha256(lock).hexdigest()}


def transfer_admission(path, source):
    """Operational bound, never represented as provider-enforced byte accounting."""
    evidence = json.loads(path.read_text())
    if (evidence.get("image") != IMAGE or evidence.get("source_sha256") != source["source_archive_sha256"]
            or evidence.get("source_archive_bytes") != source["source_archive_bytes"]
            or evidence.get("image_download_attempts") != 1 or evidence.get("dependency_download_attempts") != 1):
        raise SafetyError("Missing pinned image/source/dependency transfer evidence or retry-free preparation")
    keys = ("image_compressed_bytes", "dependency_download_bytes", "source_archive_bytes", "overhead_bytes", "outbound_bound_bytes")
    for key in keys:
        if type(evidence.get(key)) is not int or evidence[key] <= 0:
            raise SafetyError("Transfer byte bounds must be positive integers")
    for key in ("image_manifest_sha256", "dependency_manifest_sha256"):
        if not re.fullmatch("[0-9a-f]{64}", evidence.get(key, "")):
            raise SafetyError("Transfer manifest provenance missing")
    image_manifest = path.with_name("image-manifest.json")
    dependency_manifest = path.with_name("dependency-manifest.json")
    if (digest(image_manifest) != evidence["image_manifest_sha256"]
            or evidence["image_manifest_sha256"] != IMAGE.split("@sha256:", 1)[1]
            or digest(dependency_manifest) != evidence["dependency_manifest_sha256"]):
        raise SafetyError("Transfer manifest evidence digests do not match the pinned inputs")
    image_data = json.loads(image_manifest.read_text())
    dependency_data = json.loads(dependency_manifest.read_text())
    if (sum(int(item["size"]) for item in image_data["layers"]) != evidence["image_compressed_bytes"]
            or sum(int(item["size"]) for item in dependency_data["artifacts"]) != evidence["dependency_download_bytes"]
            or dependency_data.get("uv_lock_sha256") != source["dependency_lock_sha256"]
            or dependency_data.get("source_revision") != SOURCE or dependency_data.get("python") != "3.12"
            or dependency_data.get("platform") != "linux_x86_64" or dependency_data.get("resolver") != "uv 0.12.17"):
        raise SafetyError("Image/dependency sizes or frozen-platform provenance do not match")
    if evidence["overhead_bytes"] < 2_000_000_000:
        raise SafetyError("Transfer admission needs at least 2 GB protocol/bootstrap headroom")
    inbound = sum(size for size, _ in FILES.values()) + sum(evidence[key] for key in keys[:-1])
    if inbound > 100_000_000_000 or evidence["outbound_bound_bytes"] > 5_000_000_000:
        raise SafetyError("Transfer admission exceeds 100 GB inbound or 5 GB outbound")
    return {key: evidence[key] for key in ("image", *keys, "image_manifest_sha256", "dependency_manifest_sha256") } | {
        "admitted_inbound_bytes": inbound, "admitted_outbound_bytes": evidence["outbound_bound_bytes"],
        "weights_bytes": sum(size for size, _ in FILES.values()), "billing_unit_bytes": None,
        "bound_basis": "Pinned payload sizes plus headroom, independent account drawdown guard and container network counters; not provider-enforced",
        "uncertainty": "Image-layer retries and provider billing lag are not directly observable; account guard covers pre-container loading. GB/GiB conservatively costed as decimal GB."}


def accounting_estimate(state, now, inbound=None, outbound=None):
    """Conservative decimal-GB estimate; unknown actual billing units stay unknown."""
    quote = state["quote"]
    elapsed = max(0, now - state["create_requested_at"])
    image = state["transfer_admission"]["image_compressed_bytes"]
    return (number(state.get("prior_exposure_usd", "0"))
            + number(elapsed) / 3600 * number(quote["dph_total"])
            + number(image + (inbound or 0)) / 1_000_000_000 * number(quote["inet_down_cost"])
            + number(outbound or 0) / 1_000_000_000 * number(quote["inet_up_cost"]))


def preflight(api, run_id=RUN_ID):
    require_run_id(run_id)
    snapshot = account(api)
    instances = api.instances()
    eligible = offers(api, run_id=run_id)
    budget = prior_attempt(run_id) if run_id in VAST_EXTENDED_RUN_IDS else {"prior_exposure_usd": "0"}
    observed = retry_exposure(budget, snapshot) if run_id in VAST_EXTENDED_RUN_IDS else Decimal(0)
    eligible = [quote for quote in eligible
                if max(number(budget["prior_exposure_usd"]), observed) < stage_allowance(run_id) - Decimal("1.60")
                and max(number(budget["prior_exposure_usd"]), observed) + quote_envelope(quote) <= stage_allowance(run_id)]
    blockers = []
    try:
        require_credit(snapshot, run_id, budget.get("stage_account_baseline"))
    except SafetyError as exc:
        blockers.append(str(exc))
    if instances:
        blockers.append("Account must have no instances: shared account spend and auto-attached SSH key would affect unrelated resources")
    if not eligible:
        blockers.append("No eligible verified H100 SXM offer")
    return {"provider": "vast.ai", "run_id": run_id, "account": snapshot,
            "prior_exposure_usd": budget["prior_exposure_usd"],
            "existing_instance_count": len(instances), "eligible_quotes": eligible,
            "blockers": blockers, "provider_mutations": 0}


@contextmanager
def controller_lock(lease):
    with (lease / "controller.lock").open("a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SafetyError("Another controller owns this lease") from None
        yield


def read_state(lease):
    state = json.loads((lease / "state.json").read_text())
    run_id = require_run_id(state.get("run_id"))
    if (state.get("provider") != "vast.ai"
            or state.get("image") != IMAGE or state.get("source_revision") != SOURCE
            or state.get("model_revision") != REVISION or state.get("prompt_sha256") != PROMPT_SHA256
            or not re.fullmatch(re.escape(run_id) + "-[0-9a-f]{16}", state.get("label", ""))):
        raise SafetyError("Unrecognized lease ownership journal")
    number(state.get("prior_exposure_usd", "0"))
    if run_id in VAST_EXTENDED_RUN_IDS:
        if (state.get("reservation_usd") != str(stage_allowance(run_id))
                or not isinstance(state.get("stage_account_baseline"), dict)
                or not isinstance(state.get("prior_attempt"), dict)
                or state["prior_attempt"].get("run_id") != RUN_ID
                or state["prior_attempt"].get("instance_id") != 51778886
                or state["prior_attempt"].get("absence_verified") is not True
                or not isinstance(state.get("prior_account_at_close"), dict)):
            raise SafetyError("Retry journal is missing its original cumulative budget evidence")
        additional = state.get("additional_prior_attempts", [])
        if run_id in (VAST_RECOVERY_RUN_ID, VAST_HANDOFF_RUN_ID, VAST_RESUME_RUN_ID, VAST_PROXY_RUN_ID, VAST_STABLE_RUN_ID, VAST_ALTERNATE_RUN_ID):
            expected = [(VAST_RETRY_RUN_ID, 51807213)]
            if run_id in (VAST_HANDOFF_RUN_ID, VAST_RESUME_RUN_ID, VAST_PROXY_RUN_ID, VAST_STABLE_RUN_ID, VAST_ALTERNATE_RUN_ID):
                expected.append((VAST_RECOVERY_RUN_ID, 51811500))
            if run_id in (VAST_RESUME_RUN_ID, VAST_PROXY_RUN_ID, VAST_STABLE_RUN_ID, VAST_ALTERNATE_RUN_ID):
                expected.append((VAST_HANDOFF_RUN_ID, 51812997))
            if run_id in (VAST_PROXY_RUN_ID, VAST_STABLE_RUN_ID, VAST_ALTERNATE_RUN_ID):
                expected.append((VAST_RESUME_RUN_ID, 51815605))
            if run_id in (VAST_STABLE_RUN_ID, VAST_ALTERNATE_RUN_ID):
                expected.append((VAST_PROXY_RUN_ID, 51818794))
            if run_id == VAST_ALTERNATE_RUN_ID:
                expected.append((VAST_STABLE_RUN_ID, 51821924))
            if (not isinstance(additional, list) or len(additional) != len(expected)
                    or any(not isinstance(item, dict) or item.get("run_id") != identity
                           or item.get("instance_id") != instance or item.get("absence_verified") is not True
                           for item, (identity, instance) in zip(additional, expected))):
                raise SafetyError("Recovery journal is missing a required verified closeout")
        elif additional:
            raise SafetyError("Retry cannot include an unapproved prior attempt")
        held = number(state["prior_attempt"]["exposure_hold_usd"])
        held += sum((number(item["exposure_hold_usd"]) for item in additional), Decimal(0))
        if held != number(state["prior_exposure_usd"]):
            raise SafetyError("Cumulative prior exposure does not equal the prior attempt holds")
    return state


def prior_attempt(run_id=VAST_RETRY_RUN_ID):
    """Read, never rewrite, all required controller and independent closeout evidence."""
    if run_id not in VAST_EXTENDED_RUN_IDS:
        raise SafetyError("Prior evidence is only defined for the two approved extended attempts")
    from vast_deadline import accounting_exposure
    prior = read_state(LEASE)
    guard = json.loads((LEASE / "guard-state.json").read_text())
    if (prior["run_id"] != RUN_ID or prior.get("status") != "failed"
            or prior.get("instance_id") != 51778886
            or type(prior.get("create_submissions")) is not int or prior["create_submissions"] != 1
            or type(prior.get("generation_submissions")) is not int or prior["generation_submissions"] != 0
            or prior.get("cases") != {} or prior.get("absence_verified") is not True
            or prior.get("ssh_key_removed") is not True
            or guard.get("run_id") != RUN_ID or guard.get("label") != prior["label"]
            or guard.get("instance_id") != identifier(prior.get("instance_id"))
            or guard.get("status") != "closed" or guard.get("absence_verified") is not True
            or guard.get("ssh_key_removed") is not True):
        raise SafetyError("Retry requires the exact failed original lease, zero generations and two verified closeouts")
    baseline = prior["account_before_create"]
    require_credit(baseline)
    for other in (prior.get("stage_account_baseline", baseline), guard["account_baseline"]):
        if any(other.get(key) != baseline.get(key) for key in ACCOUNT_FIELDS):
            raise SafetyError("Original account baseline differs between controller and independent guard")
    closed_account = prior.get("account_after_closeout") or guard["account"]
    observed = max(accounting_exposure(baseline, guard["account"]),
                   accounting_exposure(baseline, closed_account, guard["account"]),
                   number(guard["observed_exposure_usd"]), number(prior.get("account_drawdown_observed_usd", "0")))
    created = number(prior["create_requested_at"])
    absent = max(number(prior["verified_absent_at"]), number(guard["verified_absent_at"]))
    if created <= 0 or absent < created:
        raise SafetyError("Original lease lifetime cannot be established")
    quote = prior["quote"]
    lifetime_bound = ((absent - created) / 3600 * number(quote["dph_total"])
                      + 100 * number(quote["inet_down_cost"]) + 5 * number(quote["inet_up_cost"]))
    reported = prior.get("provider_actual_charge_usd")
    hold = max(observed, number(reported) if reported is not None else Decimal(0),
               lifetime_bound).quantize(Decimal("0.01"), rounding=ROUND_CEILING)
    budget = {"stage_account_baseline": baseline, "prior_exposure_usd": str(hold),
            "prior_attempt": {"run_id": RUN_ID, "instance_id": prior["instance_id"],
                              "absence_verified": True, "reported_charge_usd": reported,
                              "observed_drawdown_usd": str(observed), "exposure_hold_usd": str(hold)},
            "prior_account_at_close": closed_account}
    if run_id == VAST_RETRY_RUN_ID:
        return budget
    second = read_state(RETRY_LEASE)
    second_guard = json.loads((RETRY_LEASE / "guard-state.json").read_text())
    if (second["run_id"] != VAST_RETRY_RUN_ID or second.get("instance_id") != 51807213
            or second.get("status") != "failed" or second.get("absence_verified") is not True
            or second.get("ssh_key_removed") is not True
            or type(second.get("create_submissions")) is not int or second["create_submissions"] != 1
            or type(second.get("generation_submissions")) is not int or second["generation_submissions"] != 0
            or second.get("cases") != {} or not second.get("hardware")
            or not second.get("prepare_started_at") or second.get("prepare_pid") is not None
            or second.get("prepared_at") is not None
            or second.get("failure", {}).get("type") != "CalledProcessError"
            or second.get("bootstrap_phase") not in (None, "source_upload")
            or second_guard.get("run_id") != VAST_RETRY_RUN_ID
            or second_guard.get("label") != second["label"]
            or second_guard.get("instance_id") != 51807213
            or second_guard.get("status") != "closed"
            or second_guard.get("absence_verified") is not True
            or second_guard.get("ssh_key_removed") is not True):
        raise SafetyError("Recovery requires the exact pre-model second failure and two verified closeouts")
    if any(second.get(key) != value for key, value in budget.items()):
        raise SafetyError("Second attempt changed the original cumulative baseline or cost evidence")
    if (any(second_guard["account_baseline"].get(key) != baseline.get(key) for key in ACCOUNT_FIELDS)
            or number(second_guard["prior_exposure_usd"]) != hold):
        raise SafetyError("Second independent guard lost the original cumulative budget")
    created = number(second["create_requested_at"])
    prepared = number(second["prepare_started_at"])
    absent = max(number(second["verified_absent_at"]), number(second_guard["verified_absent_at"]))
    if created <= 0 or not created <= prepared <= absent:
        raise SafetyError("Second pre-model lease lifetime cannot be established")
    second_account = second.get("account_after_closeout") or second_guard["account"]
    cumulative_observed = max(
        accounting_exposure(baseline, second_guard["account"], closed_account),
        accounting_exposure(baseline, second_account, second_guard["account"]),
        number(second_guard["observed_exposure_usd"]))
    increment = accounting_exposure(closed_account, second_account)
    second_reported = second.get("provider_actual_charge_usd")
    reported_sum = sum((number(value) for value in (reported, second_reported) if value is not None), Decimal(0))
    quote = second["quote"]
    # Guard estimate already includes both the original hold and second image/time.
    # Only this proven pre-model failure admits 2 GB missing bootstrap ingress.
    bounded = (number(second_guard["estimated_exposure_usd"])
               + 2 * number(quote["inet_down_cost"]) + 5 * number(quote["inet_up_cost"]))
    cumulative_hold = max(hold, reported_sum, cumulative_observed, bounded).quantize(
        Decimal("0.01"), rounding=ROUND_CEILING)
    budget.update(prior_exposure_usd=str(cumulative_hold), prior_account_at_close=second_account,
                  additional_prior_attempts=[{
                      "run_id": VAST_RETRY_RUN_ID, "instance_id": 51807213, "absence_verified": True,
                      "reported_charge_usd": second_reported, "observed_drawdown_usd": str(increment),
                      "exposure_hold_usd": str(cumulative_hold - hold)}])
    if run_id in (VAST_HANDOFF_RUN_ID, VAST_RESUME_RUN_ID, VAST_PROXY_RUN_ID, VAST_STABLE_RUN_ID, VAST_ALTERNATE_RUN_ID):
        third = read_state(RECOVERY_LEASE)
        third_guard = json.loads((RECOVERY_LEASE / "guard-state.json").read_text())
        if (third["run_id"] != VAST_RECOVERY_RUN_ID or third.get("instance_id") != 51811500
                or third.get("status") != "failed" or third.get("absence_verified") is not True
                or third.get("ssh_key_removed") is not True or third.get("create_submissions") != 1
                or third.get("generation_submissions") != 0 or third.get("cases") != {}
                or third.get("prepare_pid") is not None or third.get("prepare_started_at") is not None
                or third.get("prepared_at") is not None
                or third_guard.get("run_id") != VAST_RECOVERY_RUN_ID
                or third_guard.get("instance_id") != 51811500 or third_guard.get("label") != third["label"]
                or third_guard.get("status") != "closed" or third_guard.get("absence_verified") is not True
                or third_guard.get("ssh_key_removed") is not True
                or third_guard.get("stop_reason") != "remote_counter_stale_or_unavailable"):
            raise SafetyError("Handoff recovery requires the exact closed pre-model third lease")
        if any(third.get(key) != value for key, value in budget.items()):
            raise SafetyError("Third attempt changed the cumulative baseline or earlier cost evidence")
        if any(third_guard["account_baseline"].get(key) != baseline.get(key) for key in ACCOUNT_FIELDS):
            raise SafetyError("Third independent guard lost the original account baseline")
        third_account = third.get("account_after_closeout") or third_guard["account"]
        third_observed = max(accounting_exposure(baseline, third_account, second_account),
                             number(third_guard["observed_exposure_usd"]))
        third_reported = third.get("provider_actual_charge_usd")
        third_quote = third["quote"]
        third_bound = (number(third_guard["estimated_exposure_usd"])
                       + 2 * number(third_quote["inet_down_cost"]) + 5 * number(third_quote["inet_up_cost"]))
        combined_reported = reported_sum + (number(third_reported) if third_reported is not None else Decimal(0))
        third_hold = max(cumulative_hold, third_observed, combined_reported, third_bound).quantize(
            Decimal("0.01"), rounding=ROUND_CEILING)
        budget["additional_prior_attempts"].append({
            "run_id": VAST_RECOVERY_RUN_ID, "instance_id": 51811500, "absence_verified": True,
            "reported_charge_usd": third_reported,
            "observed_drawdown_usd": str(accounting_exposure(second_account, third_account)),
            "exposure_hold_usd": str(third_hold - cumulative_hold)})
        budget.update(prior_exposure_usd=str(third_hold), prior_account_at_close=third_account)
    if run_id in (VAST_RESUME_RUN_ID, VAST_PROXY_RUN_ID, VAST_STABLE_RUN_ID, VAST_ALTERNATE_RUN_ID):
        later = [(HANDOFF_LEASE, VAST_HANDOFF_RUN_ID, 51812997)]
        if run_id in (VAST_PROXY_RUN_ID, VAST_STABLE_RUN_ID, VAST_ALTERNATE_RUN_ID):
            later.append((RESUME_LEASE, VAST_RESUME_RUN_ID, 51815605))
        if run_id in (VAST_STABLE_RUN_ID, VAST_ALTERNATE_RUN_ID):
            later.append((PROXY_LEASE, VAST_PROXY_RUN_ID, 51818794))
        if run_id == VAST_ALTERNATE_RUN_ID:
            later.append((STABLE_LEASE, VAST_STABLE_RUN_ID, 51821924))
        reported_total = sum(number(item["reported_charge_usd"]) if item["reported_charge_usd"] is not None else Decimal(0)
                             for item in (budget["prior_attempt"], *budget["additional_prior_attempts"]))
        for previous_lease, previous_id, previous_instance in later:
            previous_state = read_state(previous_lease)
            previous_guard = json.loads((previous_lease / "guard-state.json").read_text())
            if (previous_state["run_id"] != previous_id or previous_state.get("instance_id") != previous_instance
                    or previous_state.get("status") != "failed" or previous_state.get("absence_verified") is not True
                    or previous_state.get("ssh_key_removed") is not True or previous_state.get("create_submissions") != 1
                    or previous_state.get("generation_submissions") != 0 or previous_state.get("cases") != {}
                    or previous_state.get("prepare_pid") is not None or previous_state.get("prepare_started_at") is not None
                    or previous_state.get("prepared_at") is not None
                    or previous_guard.get("run_id") != previous_id or previous_guard.get("instance_id") != previous_instance
                    or previous_guard.get("label") != previous_state["label"]
                    or previous_guard.get("status") != "closed" or previous_guard.get("absence_verified") is not True
                    or previous_guard.get("ssh_key_removed") is not True
                    or previous_guard.get("stop_reason") != "control_observation_failed"):
                raise SafetyError("Continuation requires every exact closed pre-model lease")
            if any(previous_state.get(key) != value for key, value in budget.items()):
                raise SafetyError("A prior attempt changed cumulative cost evidence")
            if any(previous_guard["account_baseline"].get(key) != baseline.get(key) for key in ACCOUNT_FIELDS):
                raise SafetyError("A prior independent guard lost the original baseline")
            previous_account = previous_state.get("account_after_closeout") or previous_guard["account"]
            previous_hold = number(budget["prior_exposure_usd"])
            observed = max(accounting_exposure(baseline, previous_account, budget["prior_account_at_close"]),
                           number(previous_guard["observed_exposure_usd"]))
            reported = previous_state.get("provider_actual_charge_usd")
            reported_total += number(reported) if reported is not None else Decimal(0)
            quote = previous_state["quote"]
            # A failed observation can predate deletion; cover the full verified lifetime.
            lifetime = accounting_estimate(previous_state, previous_guard["verified_absent_at"],
                                           previous_guard.get("inbound_bytes"), previous_guard.get("outbound_bytes"))
            bound = (max(lifetime, number(previous_guard["estimated_exposure_usd"]))
                     + 2 * number(quote["inet_down_cost"]) + 5 * number(quote["inet_up_cost"]))
            increment = accounting_exposure(budget["prior_account_at_close"], previous_account)
            known_increment = max(increment, number(reported) if reported is not None else Decimal(0))
            hold = max(previous_hold + known_increment, observed, reported_total, bound).quantize(
                Decimal("0.01"), rounding=ROUND_CEILING)
            budget["additional_prior_attempts"].append({
                "run_id": previous_id, "instance_id": previous_instance, "absence_verified": True,
                "reported_charge_usd": reported,
                "observed_drawdown_usd": str(increment),
                "exposure_hold_usd": str(hold - previous_hold)})
            budget.update(prior_exposure_usd=str(hold), prior_account_at_close=previous_account)
    return budget


def retry_exposure(budget, snapshot):
    from vast_deadline import accounting_exposure
    return accounting_exposure(budget["stage_account_baseline"], snapshot, budget["prior_account_at_close"])


def retry_claim_path(run_id=VAST_RETRY_RUN_ID):
    if run_id not in VAST_EXTENDED_RUN_IDS:
        raise SafetyError("Single-use extended authorization requires an approved identity")
    return default_lease(run_id).with_suffix(".claim.json")


def require_retry_claim(lease, state):
    claim = json.loads(retry_claim_path(state["run_id"]).read_text())
    expected = {"run_id": state["run_id"], "label": state["label"], "lease": str(lease.resolve())}
    if claim != expected:
        raise SafetyError("Retry journal does not own the single-use stage authorization")


def revalidate_retry(lease, state, snapshot):
    budget = prior_attempt(state["run_id"])
    for key, value in budget.items():
        if state.get(key) != value:
            raise SafetyError("Prior closeout evidence or cumulative baseline changed since admission")
    require_retry_claim(lease, state)
    return retry_exposure(budget, snapshot)


def arm(api, lease=None, input_dir=INPUT, archive=None, selected=None, *, run_id=RUN_ID):
    require_run_id(run_id)
    lease = default_lease(run_id) if lease is None else lease
    archive = archive or ROOT / "private/ltx-source.tar.gz"
    # Fail funding before local setup and, critically, before key registration.
    snapshot = account(api)
    if api.instances():
        raise SafetyError("Nonempty account: unrelated resources cannot be touched or charged to this trial")
    if LEASE.exists() and run_id == RUN_ID:
        raise SafetyError("Original attempt already has an exclusive journal; only its approved retry is available")
    if run_id in VAST_EXTENDED_RUN_IDS and (default_lease(run_id).exists() or retry_claim_path(run_id).exists()):
        raise SafetyError("This extended attempt already has a single-use journal or authorization claim")
    budget = (prior_attempt(run_id) if run_id in VAST_EXTENDED_RUN_IDS else
              {"stage_account_baseline": snapshot, "prior_exposure_usd": "0"})
    observed = retry_exposure(budget, snapshot) if run_id in VAST_EXTENDED_RUN_IDS else Decimal(0)
    require_credit(snapshot, run_id, budget["stage_account_baseline"])
    approved, request, source = inputs(input_dir, archive, run_id)
    transfer = transfer_admission(input_dir / "transfer-manifest.json", source)
    eligible = offers(api, selected, run_id)
    eligible = [quote for quote in eligible
                if max(number(budget["prior_exposure_usd"]), observed) < stage_allowance(run_id) - Decimal("1.60")
                and max(number(budget["prior_exposure_usd"]), observed) + quote_envelope(quote) <= stage_allowance(run_id)]
    if not eligible:
        raise SafetyError("No live verified H100 SXM quote fits the remaining cumulative stage allowance")
    quote = min(eligible, key=quote_envelope)
    lease.mkdir(mode=0o700, parents=True, exist_ok=False)
    state = {"provider": "vast.ai", "run_id": run_id, "label": run_id + "-" + secrets.token_hex(8),
             "status": "armed", "armed_at": time.time(), "instance_id": None,
             "create_requested_at": None, "deadline": None, "absence_verified": False,
             "verified_absent_at": None, "reservation_usd": str(stage_allowance(run_id)), "image": IMAGE,
             "source_revision": SOURCE, "model_revision": REVISION, "prompt_sha256": PROMPT_SHA256,
             "quote": quote, "cases": {}, "generation_submissions": 0, "create_submissions": 0,
             "provider_actual_charge_usd": None, "provider_charge_status": "pending",
             "transfer_admission": transfer, "transfer_observation": {
                 "inbound_bytes": None, "outbound_bytes": None, "provider_counters": None,
                 "billable_inbound_gb": None, "billable_outbound_gb": None, "billing_unit_bytes": None},
             "source_archive": str(archive.resolve()), "input_directory": str(input_dir.resolve()), **source, **budget}
    save(lease / "state.json", state)
    if run_id in VAST_EXTENDED_RUN_IDS:
        # Each authorization has one exclusive claim, even with a --lease override.
        claim_path = retry_claim_path(run_id)
        claim_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor = os.open(claim_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            json.dump({"run_id": run_id, "label": state["label"], "lease": str(lease.resolve())}, stream)
            stream.flush()
            os.fsync(stream.fileno())
        directory = os.open(claim_path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    save(lease / "approval.json", approved)
    save(lease / "request.json", request)
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", state["label"],
                    "-f", str(lease / "id_ed25519")], check=True, capture_output=True, timeout=20)
    return {"status": "armed", "label": state["label"], "quote": quote, "provider_mutations": 0,
            "next": "Start vast_trial.py guard in a separate hub process; wait for guard-ready before execute"}


def owns(row, state):
    return (isinstance(row, dict) and row.get("label") == state["label"]
            and row.get("machine_id") == state["quote"]["machine_id"]
            and (state.get("instance_id") is None or row.get("id") == state["instance_id"]))


def image_matches(image):
    # Provider qualification does not change the pinned repository/digest.
    return image in (IMAGE, "docker.io/" + IMAGE, "index.docker.io/" + IMAGE)


def discover(api, state):
    rows = api.instances()
    suspects = [row for row in rows if row.get("label") == state["label"] or
                (state.get("instance_id") is not None and row.get("id") == state["instance_id"])]
    if len(suspects) > 1 or any(not owns(row, state) for row in suspects):
        raise SafetyError("Ownership collision: refusing to adopt or delete any conflicting resource")
    return suspects[0] if suspects else None


def guard_ready(lease, state):
    observation = json.loads((lease / "guard-state.json").read_text())
    if (observation.get("run_id") != state["run_id"] or observation.get("label") != state["label"]
            or observation.get("status") != "watching" or observation.get("pid") == os.getpid()
            or time.time() - observation.get("heartbeat", 0) > 15
            or observation.get("stop_reason") or observation.get("absence_verified")):
        raise SafetyError("Independent local guard not ready or heartbeat stale")
    try:
        os.kill(identifier(observation.get("pid")), 0)
    except OSError:
        raise SafetyError("Independent local guard process is not alive") from None
    return observation


def keys(api):
    try:
        rows = api.request("GET", "/api/v0/ssh/")
    except APIError as exc:
        if exc.status == 404:
            return []
        raise
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise SafetyError("Invalid SSH-key listing")
    return [row for row in rows if row.get("deleted_at") is None]


def key_text(row):
    return row.get("public_key", row.get("key", "")).strip()


def upload_key(api, lease, state):
    require_credit(account(api), state["run_id"], state.get("stage_account_baseline"))
    if api.instances():
        raise SafetyError("Refusing account-wide key attachment while unrelated instances exist")
    public = (lease / "id_ed25519.pub").read_text().strip()
    if any(key_text(row) == public for row in keys(api)) or state.get("ssh_upload_requested_at"):
        raise SafetyError("Dedicated key upload already attempted; recovery only")
    state["ssh_upload_requested_at"] = time.time()
    save(lease / "state.json", state)
    # An ambiguous key response is recovered by exact public key, never by uploading twice.
    try:
        result = api.request("POST", "/api/v0/ssh/", {"ssh_key": public})
        if result.get("success") is not True or key_text(result.get("key", {})) != public:
            raise SafetyError("SSH-key registration not confirmed")
        key_id = identifier(result["key"]["id"])
    except (APIError, SafetyError, KeyError, TypeError):
        matched = [row for row in keys(api) if key_text(row) == public]
        if len(matched) != 1:
            raise SafetyError("SSH-key registration ambiguous; retain ownership journal and recover") from None
        key_id = identifier(matched[0]["id"])
    state["ssh_key_id"] = key_id
    save(lease / "state.json", state)


def cleanup_key(api, lease, state):
    if not state.get("ssh_upload_requested_at"):
        return True
    public = (lease / "id_ed25519.pub").read_text().strip()
    matched = [row for row in keys(api) if key_text(row) == public]
    if len(matched) > 1:
        raise SafetyError("Multiple temporary key matches; refusing broad key deletion")
    if not matched:
        return True
    key_id = identifier(matched[0]["id"])
    if state.get("ssh_key_id") is not None and key_id != state["ssh_key_id"]:
        raise SafetyError("Temporary SSH-key identity mismatch")
    api.request("DELETE", "/api/v0/ssh/%d/" % key_id)
    return all(key_text(row) != public for row in keys(api))


def destroy_owned(api, state):
    """One idempotent delete attempt; only independent list proves absence."""
    row = discover(api, state)
    if row is None:
        # An uncertain create can arrive later. Never release its reservation on an empty list.
        return state.get("instance_id") is not None or not state.get("create_requested_at")
    identifier(row["id"])
    try:
        api.request("DELETE", "/api/v0/instances/%d/" % row["id"])
    except APIError:
        pass
    return discover(api, dict(state, instance_id=row["id"])) is None


def startup(state):
    # Tiny deadline bootstrap runs during helper upload; full traffic guard takes
    # over via exec only after both helper files have been completely transferred.
    from vast_deadline import BOOTSTRAP
    config = {key: state[key] for key in ("run_id", "label", "deadline", "create_requested_at", "image", "quote", "transfer_admission")}
    config["reservation_usd"] = state.get("reservation_usd", "8.00")
    config["prior_exposure_usd"] = str(number(state.get("prior_exposure_usd", "0")))
    bundle = json.dumps({"program": BOOTSTRAP, "config": config}).encode()
    encoded = base64.b64encode(gzip.compress(bundle)).decode()
    program = ("import base64,gzip,json,os,pathlib,subprocess;"
               "p=pathlib.Path('/root/benchmark');p.mkdir(mode=448,exist_ok=True);"
               "d=json.loads(gzip.decompress(base64.b64decode(" + repr(encoded) + ")));"
               "os.environ['VAST_BENCHMARK_CONFIG']=json.dumps(d['config']);"
               "subprocess.Popen(['python3.12','-c',d['program']],"
               "stdin=subprocess.DEVNULL,stdout=open(p/'remote-guard.log','ab'),"
               "stderr=subprocess.STDOUT,start_new_session=True)")
    command = shlex.join(["python3.12", "-c", program])
    # Preserve StrictModes; repair metadata on the provider-installed public key.
    command += ("; chown root:root /root/.ssh /root/.ssh/authorized_keys"
                " && chmod 700 /root/.ssh && chmod 600 /root/.ssh/authorized_keys")
    if len(command) > 4048:
        raise SafetyError("Embedded startup guard exceeds provider 4048-character limit")
    return command


def create_once(api, lease, state):
    require_run_id(state["run_id"])
    if state.get("create_submissions") or state.get("create_requested_at"):
        raise SafetyError("Create already attempted: recovery only, never a second create")
    if state["run_id"] in VAST_EXTENDED_RUN_IDS:
        current = account(api)
        require_credit(current, state["run_id"], state.get("stage_account_baseline"))
        observed = revalidate_retry(lease, state, current)
        from vast_deadline import accounting_exposure
        observed = max(observed, accounting_exposure(state["stage_account_baseline"], current,
                                                    state.get("account_before_create")))
        admit_stage(state["quote"], state["prior_exposure_usd"], observed, state["reservation_usd"])
    now = time.time()
    state.update(status="create_requested", create_requested_at=now, deadline=now + SECONDS, create_submissions=1)
    # Durable write precedes the only PUT, including interrupted or ambiguous responses.
    save(lease / "state.json", state)
    payload = {"image": IMAGE, "disk": 200, "runtype": "ssh_proxy" if state["run_id"] == VAST_PROXY_RUN_ID else "ssh_direc ssh_proxy", "label": state["label"],
               "target_state": "running", "cancel_unavail": True, "vm": False,
               "onstart": startup(state)}
    try:
        result = api.request("PUT", "/api/v0/asks/%d/" % state["quote"]["id"], payload)
        if not isinstance(result, dict) or result.get("success") is not True:
            raise SafetyError("Create not confirmed")
        state["instance_id"] = identifier(result.get("new_contract"))
        state["status"] = "created"
    except (APIError, SafetyError):
        state["status"] = "create_ambiguous"
        save(lease / "state.json", state)
        row = discover(api, state)
        if row is not None:
            state.update(instance_id=identifier(row["id"]), status="created", discovered_after_ambiguous_create=True)
    save(lease / "state.json", state)
    if state["instance_id"] is None:
        raise SafetyError("Create result ambiguous; independent guard remains armed; use recover, never execute again")


def observe_charges(api, state):
    if state.get("instance_id") is None or not state.get("create_requested_at"):
        return
    query = {"select_filters": json.dumps({"day": {"gte": int(state["create_requested_at"]) - 86400,
                                                     "lte": int(time.time()) + 86400}, "type": {"in": ["instance"]}}),
             "format": "table", "limit": 100}
    rows = api.pages("/api/v0/charges/", "results", query)
    rows = [row for row in rows if row.get("source") == "instance-%d" % state["instance_id"] and row.get("type") == "instance"]
    if len(rows) == 1:
        amount = number(rows[0].get("amount"))
        state["provider_actual_charge_usd"] = float(amount)
        state["provider_charge_status"] = "reported_to_date_not_final"
        state["provider_charge_observed_at"] = time.time()
    # No row means pending, never zero. Purchases/invoices are never usage costs.


def close(api, lease=LEASE):
    state = read_state(lease)
    state["close_requested_at"] = state.get("close_requested_at") or time.time()
    save(lease / "state.json", state)
    for _ in range(6):
        if state.get("instance_id") is None and state.get("create_requested_at"):
            row = discover(api, state)
            if row is not None:
                state["instance_id"] = identifier(row["id"])
                state["discovered_after_ambiguous_create"] = True
                save(lease / "state.json", state)
        if destroy_owned(api, state):
            state.update(absence_verified=True, verified_absent_at=time.time())
            save(lease / "state.json", state)
            if not cleanup_key(api, lease, state):
                break
            state["ssh_key_removed"] = True
            expected_cases = {case for case, _, _ in cases_for(state["run_id"])}
            complete = (set(state["cases"]) == expected_cases
                        and state["generation_submissions"] == len(expected_cases)
                        and all(case.get("status") == "exported" and case.get("decode_verified") is True
                                for case in state["cases"].values()))
            state["status"] = "terminated" if complete else (
                "partial" if any(case.get("status") == "exported" for case in state["cases"].values()) else "failed")
            try:
                observe_charges(api, state)
            except (APIError, SafetyError):
                state["provider_charge_status"] = "pending_lookup_failed"
            save(lease / "state.json", state)
            return state
        time.sleep(5)
    state["status"] = "closeout_pending"
    save(lease / "state.json", state)
    raise SafetyError("Closeout incomplete; no success claimed; independent guard must remain running")


def ssh_args(lease, connection):
    if not re.fullmatch(r"[A-Za-z0-9.-]+", connection["host"]) or not 1 <= connection["port"] <= 65535:
        raise SafetyError("Invalid SSH endpoint")
    return ["-i", str(lease / "id_ed25519"), "-o", "IdentitiesOnly=yes", "-o", "BatchMode=yes",
            "-o", "ConnectTimeout=8", "-o", "StrictHostKeyChecking=accept-new",
            "-o", "UserKnownHostsFile=" + str(lease / "known_hosts")]


def private_command_failure(lease, kind, result, **metadata):
    # Never record argv, remote code or stdin: those can carry download credentials.
    # Retain stderr first within one shared 64 KiB output bound.
    remaining = 64 * 1024
    captured = {}
    for name in ("stderr", "stdout"):
        value = getattr(result, name, None) or b""
        raw = value.encode("utf-8") if isinstance(value, str) else value
        chunk = raw[:remaining]
        captured[name] = chunk.decode("utf-8", errors="replace")
        captured[name + "_truncated"] = len(raw) > len(chunk)
        remaining -= len(chunk)
    save(lease / (kind + "-failure-" + secrets.token_hex(8) + ".json"),
         {"operation": kind, "at": time.time(), "returncode": result.returncode, **metadata, **captured})


def remote(lease, connection, code, input_text=None, timeout=30):
    result = subprocess.run(["ssh", *ssh_args(lease, connection), "-p", str(connection["port"]),
                             "root@" + connection["host"], shlex.join(["python3.12", "-c", code])],
                            input=input_text, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        private_command_failure(lease, "remote", result, command_sha256=hashlib.sha256(code.encode()).hexdigest())
        error = SafetyError("Remote command failed; secret-bearing stderr is not published")
        error.returncode = result.returncode
        raise error
    return result.stdout


def transfer(lease, connection, paths, upload, timeout=90):
    peer = "root@" + connection["host"] + ":/root/benchmark/"
    sources = [str(path) for path in paths] if upload else [peer + path for path in paths]
    try:
        subprocess.run(["scp", *ssh_args(lease, connection), "-P", str(connection["port"]), *sources,
                        peer if upload else str(lease) + "/"], check=True, capture_output=True, timeout=timeout)
    except subprocess.CalledProcessError as exc:
        private_command_failure(lease, "transfer", exc, direction="upload" if upload else "download",
                                local_basenames=[Path(path).name for path in paths])
        raise


def read_remote(lease, connection, filename):
    code = "import json;from pathlib import Path;p=Path('/root/benchmark')/" + repr(filename) + ";print(p.read_text() if p.exists() else '{}')"
    # Only read-only observations retry transport failures. Mutations and generations
    # remain single-shot, and the full read stays inside the 15-second freshness fence.
    deadline = time.monotonic() + 8
    for attempt in range(3):
        try:
            return json.loads(remote(lease, connection, code, timeout=max(0.001, deadline - time.monotonic())))
        except SafetyError as exc:
            if getattr(exc, "returncode", None) != 255 or attempt == 2 or deadline - time.monotonic() <= 1:
                raise
        time.sleep(1)


def check_watchdogs(lease, connection, state):
    guard_ready(lease, state)
    observation = read_remote(lease, connection, "guard-ready.json")
    if (observation.get("run_id") != state["run_id"] or observation.get("label") != state["label"]
            or observation.get("instance_id") != state["instance_id"]
            or not observation.get("read_own_instance_verified") or not observation.get("delete_permission_documented")
            or not observation.get("self_manage_verified") or observation.get("stop_reason")
            or time.time() - observation.get("heartbeat", 0) > 15):
        raise SafetyError("Remote deadline/traffic guard not ready")
    state["transfer_observation"].update({key: observation.get(key) for key in ("inbound_bytes", "outbound_bytes")})
    state["transfer_observation"]["observed_at"] = observation["heartbeat"]
    state["transfer_observation"]["counter_scope"] = "container namespace since boot; excludes host image pull; not billable counters"
    save(lease / "state.json", state)


def hardware(lease, connection):
    code = ("import json,platform,subprocess,shutil;from pathlib import Path;"
            "g=subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.total,driver_version,mig.mode.current','--format=csv,noheader,nounits'],text=True).strip().splitlines();"
            "m=int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemTotal:')))*1024;"
            "c=Path('/sys/fs/cgroup/memory.max');"
            "c=c if c.exists() else Path('/sys/fs/cgroup/memory/memory.limit_in_bytes');"
            "v=c.read_text().strip() if c.exists() else 'max';"
            "m=min(m,int(v)) if v.isdigit() else m;d=shutil.disk_usage('/root/benchmark');"
            "print(json.dumps({'architecture':platform.machine(),'gpu_rows':g,'memory_bytes':m,'disk_total_bytes':d.total,'disk_free_bytes':d.free,'cpu_count':__import__('os').cpu_count()}))")
    data = json.loads(remote(lease, connection, code))
    if len(data["gpu_rows"]) != 1:
        raise SafetyError("Actual host does not have exactly one GPU")
    fields = [field.strip() for field in data.pop("gpu_rows")[0].split(",")]
    if len(fields) != 4:
        raise SafetyError("Cannot verify actual GPU identity and MIG state")
    gpu, memory, driver, mig = fields
    if (not re.fullmatch(r"NVIDIA H100 (80GB HBM3|SXM.*)", gpu) or number(memory) < 80000
            or mig not in ("Disabled", "[N/A]") or data["architecture"] != "x86_64"
            or data["memory_bytes"] < 64_000_000_000 or data["disk_total_bytes"] < 200_000_000_000
            or data["disk_free_bytes"] < 125_000_000_000):
        raise SafetyError("Actual GPU/RAM/disk/architecture/MIG differs from the approved host")
    if not re.fullmatch(r"\d+\.\d+(?:\.\d+)?", driver):
        raise SafetyError("Invalid actual driver version")
    data.update(gpu_name=gpu, gpu_memory_mib=int(number(memory)), driver_version=driver, mig_mode=mig)
    return data


def spawn(lease, connection, command, phase):
    code = ("import os,subprocess;from pathlib import Path;"
            "e=dict(os.environ,UV_HTTP_RETRIES='0',UV_PYTHON='3.12',UV_PYTHON_DOWNLOADS='never',"
            "UV_BUILD_CONSTRAINT='/root/benchmark/ltx-source/.build-constraints.txt');"
            "p=subprocess.Popen(" + repr(command) + ",env=e,stdin=subprocess.DEVNULL,"
            "stdout=open('/root/benchmark/" + phase + ".log','ab'),stderr=subprocess.STDOUT,start_new_session=True);"
            "Path('/root/benchmark/" + phase + ".pid').write_text(str(p.pid));print(p.pid)")
    return int(remote(lease, connection, code))


def wait_phase(lease, connection, state, phase, case, cutoff):
    while time.time() < cutoff:
        check_watchdogs(lease, connection, state)
        failure = read_remote(lease, connection, "prepare-failure.json" if case is None else "reuse-failure.json")
        if failure:
            raise SafetyError("Worker failed; no retry or substituted settings permitted")
        status = read_remote(lease, connection, "prepare-status.json" if case is None else "reuse-service-status.json")
        if status.get("phase") == phase and (case is None or (status.get("case") == case and status.get("run_id") == state["run_id"])):
            return status
        time.sleep(1)
    raise SafetyError("Preparation/generation deadline reached; no retry")


def workload(api, env_file, lease, state):
    connection = None
    # A manual pre-model handoff publishes this file only after scoped readiness.
    # check_watchdogs below revalidates the same owned instance before any work.
    helpers_uploaded = (lease / "connection.json").is_file()
    while time.time() < state["create_requested_at"] + PREPARATION_SECONDS:
        guard_ready(lease, state)
        row = discover(api, state)
        if row is None:
            raise SafetyError("Owned instance disappeared before preparation")
        if not image_matches(row.get("image_uuid")):
            raise SafetyError("Owned instance has an unexpected image; deleting rather than running substituted software")
        if row.get("actual_status") in ("exited", "unknown", "offline"):
            raise SafetyError("Host failed startup; no restart/replacement allowed")
        if state["run_id"] == VAST_PROXY_RUN_ID and state.get("ssh_transport", "proxy") == "proxy":
            host, port = row.get("ssh_host"), row.get("ssh_port")
        else:
            host = row.get("public_ipaddr")
            port = ((row.get("ports") or {}).get("22/tcp") or [{}])[0].get("HostPort")
        if row.get("actual_status") == "running" and port and host:
            candidate = {"host": host, "port": int(port)}
            try:
                if not helpers_uploaded:
                    boot = read_remote(lease, candidate, "boot-ready.json")
                    if (boot.get("instance_id") != state["instance_id"] or boot.get("label") != state["label"]
                            or time.time() - boot.get("heartbeat", 0) > 15):
                        raise SafetyError("Scoped bootstrap guard not ready")
                    transfer(lease, candidate, [ROOT / "scripts/vast_api.py", ROOT / "scripts/vast_deadline.py"], True)
                    remote(lease, candidate, "from pathlib import Path;(Path('/root/benchmark')/'remote-launch').touch(exist_ok=False)")
                    helpers_uploaded = True
                check_watchdogs(lease, candidate, state)
                connection = candidate
                break
            except (SafetyError, subprocess.TimeoutExpired, ValueError):
                pass
        time.sleep(5)
    if connection is None:
        raise SafetyError("SSH/remote guard not ready by preparation cutoff")
    save(lease / "connection.json", connection)
    state["hardware"] = hardware(lease, connection)
    state["prepare_started_at"] = time.time()
    save(lease / "state.json", state)
    archive = Path(state["source_archive"])
    if digest(archive) != state["source_archive_sha256"]:
        raise SafetyError("Source archive changed since arm")
    files = [ROOT / "scripts" / name for name in ("ltx_config.py", "ltx_worker.py", "ltx_reuse.py", "ltx_reuse_config.py", "ltx_reuse_worker.py")]
    state["bootstrap_phase"] = "source_upload"
    save(lease / "state.json", state)
    transfer(lease, connection, [*files, archive, lease / "request.json"], True)
    state["bootstrap_phase"] = "archive_extract"
    save(lease / "state.json", state)
    code = ("import hashlib,tarfile;from pathlib import Path;p=Path('/root/benchmark/ltx-source.tar.gz');"
            "h=hashlib.file_digest(p.open('rb'),'sha256').hexdigest();"
            "assert h==" + repr(state["source_archive_sha256"]) + ";"
            "t=tarfile.open(p,'r:gz');t.extractall('/root/benchmark',filter='data')")
    remote(lease, connection, code, timeout=90)
    check_watchdogs(lease, connection, state)
    state["bootstrap_phase"] = "uv_install"
    save(lease / "state.json", state)
    remote(lease, connection,
           "import subprocess;subprocess.run(['python3.12','-m','pip','install','--no-deps','--no-cache-dir',"
           "'--disable-pip-version-check','--retries','0','uv==0.12.17'],check=True)",
           timeout=90)
    state["bootstrap_phase"] = "link_resolution"
    save(lease / "state.json", state)
    from ltx_trial import download_links
    links = download_links(env_file)
    code = ("import sys,os; p='/root/benchmark/download-links.json';"
            "fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);"
            "f=os.fdopen(fd,'wb');f.write(sys.stdin.buffer.read());f.close()")
    remote(lease, connection, code, json.dumps(links))
    del links
    state["bootstrap_phase"] = "prepare_launch"
    save(lease / "state.json", state)
    state["prepare_pid"] = spawn(lease, connection, ["python3.12", "-u", "/root/benchmark/ltx_worker.py", "prepare", "--frozen"], "prepare")
    state["bootstrap_phase"] = "prepare_running"
    save(lease / "state.json", state)
    wait_phase(lease, connection, state, "ready", None, state["create_requested_at"] + PREPARATION_SECONDS)
    transfer(lease, connection, ["prepare-status.json", "dependencies.txt"], False)
    state["prepared_at"] = time.time()
    state["bootstrap_phase"] = "prepared"
    state["service_launch_claimed_at"] = time.time()
    save(lease / "state.json", state)
    state["service_pid"] = spawn(lease, connection, ["/root/benchmark/ltx-source/.venv/bin/python", "-u",
                                                        "/root/benchmark/ltx_reuse_worker.py", "--run-id", state["run_id"]], "reuse")
    save(lease / "state.json", state)
    from export_vast_ltx import validate_artifact
    for case, mode, warmup in cases_for(state["run_id"]):
        wait_phase(lease, connection, state, "ready", case, state["create_requested_at"] + SUBMISSION_SECONDS)
        if time.time() >= state["create_requested_at"] + SUBMISSION_SECONDS:
            raise SafetyError("No new generation after minute 35")
        state["generation_submissions"] += 1
        state["cases"][case] = {**case_settings(case, state["run_id"]),
                                "submitted_at": time.time(), "status": "submission_claimed"}
        save(lease / "state.json", state)
        started = time.monotonic()
        stem = output_id(case, state["run_id"])
        code = ("import json,os;from pathlib import Path;b=Path('/root/benchmark');"
                "assert not (b/'vast-stop').exists();p=b/" + repr(stem + ".request.json") + ";"
                "t=p.with_suffix('.pending');f=t.open('x');json.dump(" + repr({"run_id": state["run_id"], "case": case}) +
                ",f);f.flush();os.fsync(f.fileno());f.close();os.link(t,p);t.unlink()")
        remote(lease, connection, code)
        cutoff = min(state["cases"][case]["submitted_at"] + GENERATION_SECONDS, state["deadline"] - 120)
        wait_phase(lease, connection, state, "completed", case, cutoff)
        state["cases"][case]["status"] = "completed"
        save(lease / "state.json", state)
        transfer(lease, connection, [stem + ".mp4", stem + ".json"], False,
                 timeout=max(1, min(90, int(state["deadline"] - time.time() - 60))))
        state["cases"][case].update(end_to_end_seconds=time.monotonic() - started,
                                     downloaded_at=time.time(), status="downloaded")
        save(lease / "state.json", state)
        runtime = json.loads((lease / (stem + ".json")).read_text())
        metadata = validate_artifact(lease / (stem + ".mp4"), runtime, run_id=state["run_id"])
        state["cases"][case].update(status="exported", decode_verified=True, artifact=metadata)
        save(lease / "state.json", state)
        check_watchdogs(lease, connection, state)
        remote(lease, connection, "from pathlib import Path;(Path('/root/benchmark')/" + repr(stem + ".exported") + ").touch(exist_ok=False)")
    state["decode_verified"] = True
    save(lease / "state.json", state)


def execute(api, env_file, lease=LEASE):
    with controller_lock(lease):
        state = read_state(lease)
        if state["status"] != "armed" or state.get("create_submissions") or state.get("ssh_upload_requested_at"):
            raise SafetyError("Execute is single-use; use recover/close for an interrupted attempt")
        snapshot = account(api)
        require_credit(snapshot, state["run_id"], state.get("stage_account_baseline"))
        if state["run_id"] in VAST_EXTENDED_RUN_IDS:
            revalidate_retry(lease, state, snapshot)
        if api.instances():
            raise SafetyError("Account is no longer empty; refusing account-wide SSH-key attachment")
        approved, request, source = inputs(Path(state["input_directory"]), Path(state["source_archive"]), state["run_id"])
        if source["source_archive_sha256"] != state["source_archive_sha256"]:
            raise SafetyError("Prepared source changed since arm")
        transfer_admission(Path(state["input_directory"]) / "transfer-manifest.json", source)
        guard_ready(lease, state)
        state["account_before_create"] = account(api)
        require_credit(state["account_before_create"], state["run_id"], state.get("stage_account_baseline"))
        from vast_deadline import accounting_exposure
        baseline = state.setdefault("stage_account_baseline", state["account_before_create"])
        observed = accounting_exposure(baseline, state["account_before_create"])
        if state["run_id"] in VAST_EXTENDED_RUN_IDS:
            observed = revalidate_retry(lease, state, state["account_before_create"])
        admit_stage(state["quote"], state.get("prior_exposure_usd", "0"), observed, state["reservation_usd"])
        save(lease / "state.json", state)
        try:
            upload_key(api, lease, state)
            guard_ready(lease, state)
            # Refresh credit and quote once more immediately before the sole create.
            current = account(api)
            require_credit(current, state["run_id"], state.get("stage_account_baseline"))
            observed = accounting_exposure(baseline, current, state["account_before_create"])
            if state["run_id"] in VAST_EXTENDED_RUN_IDS:
                observed = max(observed, revalidate_retry(lease, state, current))
            # Arm is not an offer reservation. Select from freshly admitted stock;
            # ownership freezes only at the durable create intent below.
            exposure = max(number(state.get("prior_exposure_usd", "0")), observed)
            final_quotes = [quote for quote in offers(api, run_id=state["run_id"])
                            if exposure + quote_envelope(quote) <= number(state["reservation_usd"])]
            if not final_quotes:
                raise SafetyError("No currently available approved H100 quote fits the cumulative allowance")
            state["quote"] = min(final_quotes, key=quote_envelope)
            admit_stage(state["quote"], state.get("prior_exposure_usd", "0"), observed, state["reservation_usd"])
            create_once(api, lease, state)
            workload(api, env_file, lease, state)
        except BaseException as exc:
            state["failure"] = {"type": type(exc).__name__, "at": time.time()}
            save(lease / "state.json", state)
            raise
        finally:
            # Never mistake killing a worker or stopping a VM for ending storage bills.
            close(api, lease)


def recover(api, lease=LEASE):
    with controller_lock(lease):
        state = read_state(lease)
        if state.get("create_requested_at") and state.get("instance_id") is None:
            row = discover(api, state)
            if row is not None:
                state["instance_id"] = identifier(row["id"])
                state["discovered_after_ambiguous_create"] = True
                save(lease / "state.json", state)
        return close(api, lease)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "arm", "guard", "execute", "close", "recover", "status"))
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--attempt", choices=("initial", "retry", "recovery", "handoff", "resume", "proxy", "stable", "alternate"), default="initial")
    parser.add_argument("--lease", type=Path)
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--archive", type=Path, default=ROOT / "private/ltx-source.tar.gz")
    parser.add_argument("--offer", type=int)
    args = parser.parse_args()
    run_id = {"initial": RUN_ID, "retry": VAST_RETRY_RUN_ID, "recovery": VAST_RECOVERY_RUN_ID,
              "handoff": VAST_HANDOFF_RUN_ID, "resume": VAST_RESUME_RUN_ID, "proxy": VAST_PROXY_RUN_ID,
              "stable": VAST_STABLE_RUN_ID, "alternate": VAST_ALTERNATE_RUN_ID}[args.attempt]
    args.lease = default_lease(run_id) if args.lease is None else args.lease
    try:
        api = client(args.env_file)
        if args.action == "preflight":
            result = preflight(api, run_id)
        elif args.action == "arm":
            result = arm(api, args.lease, args.input, args.archive, args.offer, run_id=run_id)
        elif args.action == "guard":
            from vast_deadline import local_guard
            return local_guard(api, args.lease)
        elif args.action == "execute":
            execute(api, args.env_file, args.lease)
            result = {"status": read_state(args.lease)["status"]}
        elif args.action in ("close", "recover"):
            state = recover(api, args.lease)
            result = {"status": state["status"], "absence_verified": state["absence_verified"]}
        else:
            state = read_state(args.lease)
            row = discover(api, state)
            result = {"status": state["status"], "instance_id": state["instance_id"], "owned_instance_present": row is not None,
                      "generation_submissions": state["generation_submissions"], "absence_verified": state["absence_verified"]}
        print(json.dumps(result, indent=2))
        return 0
    except (SafetyError, APIError) as exc:
        print(json.dumps({"status": "blocked_or_failed", "reason": str(exc)}))
    except Exception as exc:
        # Exceptions from SSH, credentials, JSON and provider libraries may contain secrets.
        print(json.dumps({"status": "blocked_or_failed", "error_type": type(exc).__name__}))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
