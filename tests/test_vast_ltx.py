"""Offline artifact/privacy edge cases; these do not establish GPU execution."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import export_vast_ltx as export
from ltx_config import FILES, FPS, FRAMES, HEIGHT, IMAGE, PROMPT_SHA256, REVISION, SOURCE, WIDTH
from ltx_reuse_config import CASES, RUN_ID, VAST_RUN_ID, VAST_RETRY_RUN_ID, VAST_RECOVERY_RUN_ID, VAST_HANDOFF_RUN_ID, VAST_RESUME_RUN_ID, VAST_PROXY_RUN_ID, VAST_STABLE_RUN_ID, VAST_ALTERNATE_RUN_ID, VAST_EXTENDED_RUN_IDS, VAST_RUN_IDS, WARMUP_STAGE_1, WARMUP_STAGE_2, case_settings, cases_for, output_id
from ltx_reuse_worker import serve
from ltx_worker import frozen_natten_requirement


PAYLOAD = b"encoded-video-fixture"


def runtime(case="BASE_WARM", run_id=VAST_RUN_ID):
    settings = case_settings(case, run_id)
    mode, warmup = settings["mode"], settings["warmup"]
    builds = 2 if mode == "baseline" else int(warmup)
    return {"run_id": run_id, "case": case, "mode": mode, "warmup": warmup,
            "source_revision": SOURCE, "model_revision": REVISION, "prompt_sha256": PROMPT_SHA256,
            "width": WIDTH, "height": HEIGHT, "frames": settings["frames"], "fps": FPS, "seed": 42,
            **({"requested_video_seconds": settings["requested_seconds"]} if run_id in VAST_EXTENDED_RUN_IDS else {}),
            "stage_1_sigmas": list(WARMUP_STAGE_1 if warmup else export.STAGE_1),
            "stage_2_sigmas": list(WARMUP_STAGE_2 if warmup else export.STAGE_2),
            "precision": "BF16", "compile": False, "quantization": None, "offload": "none",
            "prompt_enhancement": False, "output_cache": False, "embedding_cache": False,
            "diffvae_mode": "chunked_eager", "torch": "2.13.0+cu132", "cuda": "13.2",
            "natten": "0.21.7+torch2130cu132", "gpu_count": 1,
            "gpu": "NVIDIA H100 80GB HBM3", "gpu_total_memory_bytes": 85_000_000_000,
            "transformer_build_count": builds, "resident_total_build_count": None if mode == "baseline" else 1,
            "processing_seconds": 30.0, "pipeline_return_seconds": 20.0,
            "lazy_video_decode_and_encode_seconds": 10.0, "completed_at": 100.0,
            "peak_allocated_bytes": 40_000_000_000, "peak_reserved_bytes": 46_000_000_000,
            "output_bytes": len(PAYLOAD), "output_sha256": hashlib.sha256(PAYLOAD).hexdigest(),
            "resolved_tiling": "TileSizeConfig(frames=DimensionSizeConfig(tile_size=128, overlap=40), height=DimensionSizeConfig(tile_size=768, overlap=160), width=DimensionSizeConfig(tile_size=1344, overlap=160))",
            "stages_including_weight_loading": [{"stage": "stage", "seconds": 18.0}],
            "transformer_build_seconds": [2.0] * builds}


def probe(frames=FRAMES):
    return {"streams": [{"codec_type": "video", "width": WIDTH, "height": HEIGHT,
                         "nb_frames": str(frames), "nb_read_frames": str(frames),
                         "r_frame_rate": "24/1", "avg_frame_rate": "24/1", "duration": f"{frames / FPS:.6f}"},
                        {"codec_type": "audio", "duration": f"{frames / FPS:.6f}", "channels": 2, "sample_rate": "48000", "nb_read_frames": "237"}]}


def metadata(frames=FRAMES):
    return {"duration_seconds": frames / FPS, "decoded_stream_sha256": {"video": "a" * 64, "audio": "b" * 64},
            "full_decode_verified": True}


def lease(directory, cases=(), status="failed", run_id=VAST_RUN_ID):
    state = {"provider": "vast.ai", "run_id": run_id, "status": status,
             "instance_id": 17, "label": "owned-test-lease", "absence_verified": True,
             "create_requested_at": 1000, "verified_absent_at": 2800, "deadline": 3700,
             "reservation_usd": "8.00", "generation_submissions": len(cases),
             "image": IMAGE, "source_revision": SOURCE, "model_revision": REVISION, "prompt_sha256": PROMPT_SHA256,
             "hardware": {"architecture": "x86_64", "gpu_name": "NVIDIA H100 80GB HBM3",
                          "gpu_memory_mib": 81920, "driver_version": "595.71.05", "mig_mode": "Disabled",
                          "memory_bytes": 112_000_000_000, "disk_total_bytes": 200_000_000_000,
                          "disk_free_bytes": 80_000_000_000, "cpu_count": 16},
             "cases": {case: {"status": "exported", "decode_verified": True, "end_to_end_seconds": 35.0} for case in cases},
             "quote": {"id": 7, "machine_id": 9, "gpu_name": "H100 SXM", "num_gpus": 1,
                       "allocated_storage": 200, "gpu_ram": 81920, "cpu_ram": 112834,
                       "driver_version": "595.71.05", "cuda_max_good": 13.2, "reliability": 0.995,
                       "verification": "verified", "dph_base": 3.0, "dph_total": 3.5,
                       "storage_total_cost": 0.5, "storage_cost": 0.0025,
                       "inet_down_cost": 0.04, "inet_up_cost": 0.03},
             "transfer_observation": {}, "provider_actual_charge_usd": None}
    if run_id in VAST_EXTENDED_RUN_IDS:
        state.update(prior_exposure_usd="0.65", prior_attempt={
            "run_id": VAST_RUN_ID, "instance_id": 51778886, "absence_verified": True,
            "reported_charge_usd": 0.194, "observed_drawdown_usd": "0.19336218", "exposure_hold_usd": "0.65"})
    if run_id in (VAST_RECOVERY_RUN_ID, VAST_HANDOFF_RUN_ID, VAST_RESUME_RUN_ID, VAST_PROXY_RUN_ID, VAST_STABLE_RUN_ID, VAST_ALTERNATE_RUN_ID):
        state.update(prior_exposure_usd="1.40", additional_prior_attempts=[{
            "run_id": VAST_RETRY_RUN_ID, "instance_id": 51807213, "absence_verified": True,
            "reported_charge_usd": 0.267, "observed_drawdown_usd": "0.266443223", "exposure_hold_usd": "0.75"}])
    if run_id in (VAST_HANDOFF_RUN_ID, VAST_RESUME_RUN_ID, VAST_PROXY_RUN_ID, VAST_STABLE_RUN_ID, VAST_ALTERNATE_RUN_ID):
        state.update(reservation_usd="9.99", prior_exposure_usd="2.15")
        state["additional_prior_attempts"].append({
            "run_id": VAST_RECOVERY_RUN_ID, "instance_id": 51811500, "absence_verified": True,
            "reported_charge_usd": 0.072, "observed_drawdown_usd": "0.072571889", "exposure_hold_usd": "0.75"})
    if run_id in (VAST_RESUME_RUN_ID, VAST_PROXY_RUN_ID, VAST_STABLE_RUN_ID, VAST_ALTERNATE_RUN_ID):
        state["prior_exposure_usd"] = "3.19"
        state["additional_prior_attempts"].append({
            "run_id": VAST_HANDOFF_RUN_ID, "instance_id": 51812997, "absence_verified": True,
            "reported_charge_usd": 0.424, "observed_drawdown_usd": "0.42438445", "exposure_hold_usd": "1.04"})
    if run_id in (VAST_PROXY_RUN_ID, VAST_STABLE_RUN_ID, VAST_ALTERNATE_RUN_ID):
        state["prior_exposure_usd"] = "4.05"
        state["additional_prior_attempts"].append({
            "run_id": VAST_RESUME_RUN_ID, "instance_id": 51815605, "absence_verified": True,
            "reported_charge_usd": 0.075, "observed_drawdown_usd": "0.075543155", "exposure_hold_usd": "0.86"})
    if run_id in (VAST_STABLE_RUN_ID, VAST_ALTERNATE_RUN_ID):
        state["prior_exposure_usd"] = "5.16"
        state["additional_prior_attempts"].append({
            "run_id": VAST_PROXY_RUN_ID, "instance_id": 51818794, "absence_verified": True,
            "reported_charge_usd": 1.104, "observed_drawdown_usd": "1.1037708378", "exposure_hold_usd": "1.11"})
    if run_id == VAST_ALTERNATE_RUN_ID:
        state["prior_exposure_usd"] = "5.57"
        state["additional_prior_attempts"].append({
            "run_id": VAST_STABLE_RUN_ID, "instance_id": 51821924, "absence_verified": True,
            "reported_charge_usd": 0.403, "observed_drawdown_usd": "0.402751955240001", "exposure_hold_usd": "0.41"})
    guard = {key: state[key] for key in ("run_id", "instance_id", "label", "absence_verified", "verified_absent_at")}
    (directory / "state.json").write_text(json.dumps(state))
    (directory / "guard-state.json").write_text(json.dumps(guard))
    for case in cases:
        (directory / (output_id(case, run_id) + ".json")).write_text(json.dumps(runtime(case, run_id)))
        (directory / (output_id(case, run_id) + ".mp4")).write_bytes(PAYLOAD)
    preparation = {"phase": "ready", "source_revision": SOURCE, "model_revision": REVISION,
                   "started_at": 1020, "ready_at": 1300, "download_seconds": 200,
                   "natten_wheel_manifest_sha256": "d" * 64,
                   "frozen": True, "uv_lock_sha256": "c" * 64,
                   "verified_files": [{"file": name, "bytes": size, "sha256": sha} for name, (size, sha) in FILES.items()]}
    (directory / "prepare-status.json").write_text(json.dumps(preparation))
    (directory / "dependencies.txt").write_text("torch==2.13.0+cu132\nnatten==0.21.7+torch2130cu132\n")
    return state


class VastArtifactTests(unittest.TestCase):
    def test_late_bookkeeping_does_not_extend_a_verified_deleted_lease(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            journal = lease(directory)
            journal["verified_absent_at"] = 4000
            (directory / "state.json").write_text(json.dumps(journal))
            result = export.export(directory, directory / "public")
            self.assertFalse(result["deadline_exceeded"])
            self.assertEqual(result["verified_lifetime_upper_bound_seconds"], 1800)
            self.assertEqual(result["controller_observation_window_seconds"], 3000)
            self.assertAlmostEqual(result["compute_and_disk_window_usd_estimate"], 1.75)

    def test_foreign_or_traversing_identity_never_reaches_gpu_imports(self):
        for identity in ("../../escape", "/tmp/escape", RUN_ID + "/x", "P01_EN_VAST_H100_LTX25_REUSE_5S_002", "P01_EN_VAST_H100_LTX25_REUSE_5S20S_009"):
            with self.subTest(identity=identity), self.assertRaises(ValueError):
                output_id("BASE_WARM", identity)
            with self.subTest(identity=identity), self.assertRaises(ValueError):
                serve(identity)
        self.assertEqual(output_id("BASE_WARM"), RUN_ID + "_BASE_WARM")
        self.assertEqual(output_id("BASE_WARM", VAST_RUN_ID), VAST_RUN_ID + "_BASE_WARM")

    def test_foreign_runtime_is_rejected_before_file_access(self):
        value = runtime()
        value["run_id"] = RUN_ID
        with self.assertRaises(ValueError):
            export.validate_artifact(Path("missing.mp4"), value)

    def test_equal_length_schedule_substitution_is_not_accepted(self):
        for case in ("BASE_WARM", "REUSE_WARMUP"):
            value = runtime(case)
            value["stage_1_sigmas"][1] -= 0.001
            with self.subTest(case=case), self.assertRaises(ValueError):
                export.public_runtime(value)

    def test_corrupted_encoded_bytes_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / (output_id("BASE_WARM", VAST_RUN_ID) + ".mp4")
            path.write_bytes(b"x" * len(PAYLOAD))
            with self.assertRaises(ValueError):
                export.validate_artifact(path, runtime())

    def test_wrong_shape_missing_audio_and_decode_failure_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / (output_id("BASE_WARM", VAST_RUN_ID) + ".mp4")
            path.write_bytes(PAYLOAD)
            wrong_shape = probe()
            wrong_shape["streams"][0]["nb_read_frames"] = "120"
            missing_audio = probe()
            missing_audio["streams"].pop()
            for observed in (wrong_shape, missing_audio):
                with patch.object(export.subprocess, "check_output", return_value=json.dumps(observed)):
                    with self.assertRaises(ValueError):
                        export.validate_artifact(path, runtime())
            with patch.object(export.subprocess, "check_output", side_effect=[json.dumps(probe()), subprocess.CalledProcessError(1, "ffmpeg")]):
                with self.assertRaises(subprocess.CalledProcessError):
                    export.validate_artifact(path, runtime())

    def test_pending_transfer_and_invoice_remain_unknown_on_failed_lease(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            lease(directory)
            result = export.export(directory, directory / "public")
            self.assertEqual(result["status"], "failed")
            self.assertIsNone(result["network"]["transfer_usd_estimate"])
            self.assertIsNone(result["whole_experiment_usd_estimate"])
            self.assertIsNone(result["provider_actual_charge_usd"])
            self.assertIsNone(result["provider_billed_seconds"])
            self.assertAlmostEqual(result["compute_and_disk_window_usd_estimate"], 1.75)
            self.assertAlmostEqual(result["network"]["admission_transfer_usd_bound"], 4.15)

    def test_partial_closeout_preserves_valid_artifact_and_rejects_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            state = lease(directory, ("BASE_WARMUP",), "terminated")
            # A deadline can interrupt between download and the controller acknowledgment.
            state["cases"]["BASE_WARMUP"]["status"] = "downloaded"
            state["cases"]["BASE_WARMUP"]["decode_verified"] = False
            (directory / "state.json").write_text(json.dumps(state))
            public = directory / "public"
            with patch.object(export, "validate_artifact", return_value=metadata()):
                result = export.export(directory, public)
                self.assertEqual(result["status"], "partial")
                self.assertEqual((public / (output_id("BASE_WARMUP", VAST_RUN_ID) + ".mp4")).read_bytes(), PAYLOAD)
                original = (public / (VAST_RUN_ID + ".json")).read_bytes()
                with self.assertRaises(FileExistsError):
                    export.export(directory, public)
                self.assertEqual((public / (VAST_RUN_ID + ".json")).read_bytes(), original)

    def test_untrusted_host_fields_do_not_leak_to_public_output(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            lease(directory, tuple(case for case, _, _ in CASES), "terminated")
            secret = "secret-signed-url-and-prompt"
            path = directory / (output_id("BASE_WARM", VAST_RUN_ID) + ".json")
            value = json.loads(path.read_text())
            value["prompt"] = secret
            value["download_url"] = "https://example.invalid/?Signature=" + secret
            value["stages_including_weight_loading"][0]["credential"] = secret
            path.write_text(json.dumps(value))
            with patch.object(export, "validate_artifact", return_value=metadata()):
                result = export.export(directory, directory / "public")
            self.assertEqual(result["status"], "completed")
            for path in (directory / "public").iterdir():
                self.assertNotIn(secret.encode(), path.read_bytes())
            value["gpu"] = secret
            with self.assertRaises(ValueError):
                export.public_runtime(value)

    def test_controller_absence_alone_cannot_publish_success(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            lease(directory, tuple(case for case, _, _ in CASES), "terminated")
            (directory / "guard-state.json").write_text(json.dumps({"absence_verified": True, "instance_id": 18}))
            with self.assertRaises(ValueError):
                export.export(directory, directory / "public")
            self.assertFalse((directory / "public").exists())

    def test_extended_scope_keeps_original_defaults_and_exact_duration_contract(self):
        self.assertEqual(cases_for(), CASES)
        self.assertEqual(cases_for(VAST_RUN_ID), CASES)
        for run_id in VAST_EXTENDED_RUN_IDS:
            with self.subTest(run_id=run_id):
                self.assertEqual(cases_for(run_id), (
                    ("BASE_WARMUP", "baseline", True), ("BASE_WARM_5S", "baseline", False),
                    ("BASE_WARM_20S", "baseline", False), ("REUSE_WARMUP", "resident", True),
                    ("REUSE_WARM_5S", "resident", False), ("REUSE_WARM_20S", "resident", False)))
                self.assertEqual(case_settings("BASE_WARM_20S", run_id),
                                 {"mode": "baseline", "warmup": False, "requested_seconds": 20, "frames": 481})
        for run_id, case in ((VAST_RUN_ID, "BASE_WARM_20S"), (VAST_RETRY_RUN_ID, "BASE_WARM"),
                             (VAST_RECOVERY_RUN_ID, "BASE_WARM")):
            with self.subTest(run_id=run_id), self.assertRaises(ValueError):
                output_id(case, run_id)

    def test_twenty_second_case_rejects_short_runtime_and_short_encoded_video(self):
        for run_id in VAST_EXTENDED_RUN_IDS:
            with self.subTest(run_id=run_id), tempfile.TemporaryDirectory() as directory:
                value = runtime("BASE_WARM_20S", run_id)
                with self.assertRaises(ValueError):
                    export.public_runtime(dict(value, frames=121), run_id=run_id)
                with self.assertRaises(ValueError):
                    export.public_runtime(dict(value, requested_video_seconds=5))
                path = Path(directory) / (output_id(value["case"], run_id) + ".mp4")
                path.write_bytes(PAYLOAD)
                with patch.object(export.subprocess, "check_output", return_value=json.dumps(probe())):
                    with self.assertRaises(ValueError):
                        export.validate_artifact(path, value, run_id=run_id)
                with patch.object(export.subprocess, "check_output",
                                  side_effect=[json.dumps(probe(481)), "SHA256=" + "a" * 64, "SHA256=" + "b" * 64]):
                    result = export.validate_artifact(path, value, run_id=run_id)
                self.assertEqual(result["frames"], 481)
                self.assertTrue(result["full_decode_verified"])
                self.assertAlmostEqual(result["duration_seconds"], 481 / FPS, places=5)

    def test_valid_other_attempt_is_rejected_before_artifact_access(self):
        for actual in VAST_RUN_IDS:
            for expected in VAST_RUN_IDS:
                if actual == expected:
                    continue
                with self.subTest(actual=actual, expected=expected), self.assertRaises(ValueError):
                    export.validate_artifact(Path("missing.mp4"), runtime("BASE_WARMUP", actual), run_id=expected)

    def test_extended_publication_normalizes_duration_and_preserves_all_earlier_files(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            original_dir, public = directory / "initial", directory / "public"
            original_dir.mkdir()
            lease(original_dir, tuple(case for case, _, _ in CASES), "terminated")
            with patch.object(export, "validate_artifact", side_effect=lambda video, value, run_id=None: metadata(value["frames"])):
                export.export(original_dir, public)
                for run_id, csv_name in (
                        (VAST_RETRY_RUN_ID, "VAST_LTX_REUSE_RETRY_MEASUREMENTS.csv"),
                        (VAST_RECOVERY_RUN_ID, "VAST_LTX_REUSE_RECOVERY_MEASUREMENTS.csv")):
                    with self.subTest(run_id=run_id):
                        earlier = {path.name: path.read_bytes() for path in public.iterdir()}
                        attempt_dir = directory / run_id
                        attempt_dir.mkdir()
                        lease(attempt_dir, tuple(case for case, _, _ in cases_for(run_id)), "terminated", run_id)
                        result = export.export(attempt_dir, public)
                        self.assertEqual(result["status"], "completed")
                        self.assertEqual(result["completed_output_count"], 6)
                        self.assertEqual(result["measured_output_count"], 4)
                        self.assertEqual(result["technical_warmup_count"], 2)
                        self.assertEqual(set(result["comparison_by_requested_seconds"]), {"5", "20"})
                        for case, _, _ in cases_for(run_id):
                            record = json.loads((public / (output_id(case, run_id) + ".json")).read_text())
                            seconds = case_settings(case, run_id)["requested_seconds"]
                            self.assertEqual(record["lease_run_id"], run_id)
                            self.assertEqual(record["run_id"], output_id(case, run_id))
                            self.assertAlmostEqual(record["cost"]["compute_usd_per_requested_video_second"], 30 * 3 / 3600 / seconds)
                            self.assertAlmostEqual(record["native_video_seconds"], (seconds * FPS + 1) / FPS)
                            self.assertEqual((public / (output_id(case, run_id) + ".mp4")).read_bytes(), PAYLOAD)
                        self.assertTrue((public / csv_name).is_file())
                        for name, contents in earlier.items():
                            self.assertEqual((public / name).read_bytes(), contents)
                        self.assertNotIn("BASE_WARM_20S", result["historical_runpod_decoded_streams_equal"])
                        with self.assertRaises(FileExistsError):
                            export.export(attempt_dir, public)

    def test_four_extended_outputs_cannot_claim_six_output_success(self):
        for run_id in VAST_EXTENDED_RUN_IDS:
            with self.subTest(run_id=run_id), tempfile.TemporaryDirectory() as directory:
                directory = Path(directory)
                cases = ("BASE_WARMUP", "BASE_WARM_5S", "REUSE_WARMUP", "REUSE_WARM_5S")
                lease(directory, cases, "terminated", run_id)
                with patch.object(export, "validate_artifact", return_value=metadata()):
                    result = export.export(directory, directory / "public")
                self.assertEqual(result["status"], "partial")
                self.assertEqual(result["completed_output_count"], 4)
                self.assertNotIn("20", result["comparison_by_requested_seconds"])

    def test_failed_long_artifact_preserves_completed_short_artifacts(self):
        for run_id in VAST_EXTENDED_RUN_IDS:
            with self.subTest(run_id=run_id), tempfile.TemporaryDirectory() as directory:
                directory = Path(directory)
                cases = ("BASE_WARMUP", "BASE_WARM_5S", "BASE_WARM_20S")
                lease(directory, cases, "failed", run_id)
                path = directory / (output_id("BASE_WARM_20S", run_id) + ".json")
                path.write_text(json.dumps(dict(runtime("BASE_WARM_20S", run_id), frames=121)))
                public = directory / "public"
                with patch.object(export, "validate_artifact", return_value=metadata()):
                    result = export.export(directory, public)
                self.assertEqual(result["status"], "failed")
                self.assertEqual(result["completed_output_count"], 2)
                self.assertEqual(result["cases"][2]["status"], "artifact_validation_failed")
                for case in cases[:2]:
                    self.assertEqual((public / (output_id(case, run_id) + ".mp4")).read_bytes(), PAYLOAD)
                self.assertFalse((public / (output_id(cases[2], run_id) + ".mp4")).exists())

    def test_cross_attempt_warmup_cannot_complete_extended_run(self):
        for run_id, foreign in ((VAST_RETRY_RUN_ID, VAST_RUN_ID), (VAST_RECOVERY_RUN_ID, VAST_RETRY_RUN_ID)):
            with self.subTest(run_id=run_id), tempfile.TemporaryDirectory() as directory:
                directory = Path(directory)
                cases = tuple(case for case, _, _ in cases_for(run_id))
                lease(directory, cases, "terminated", run_id)
                path = directory / (output_id("BASE_WARMUP", run_id) + ".json")
                path.write_text(json.dumps(runtime("BASE_WARMUP", foreign)))
                with patch.object(export, "validate_artifact", side_effect=lambda video, value, run_id=None: metadata(value["frames"])):
                    result = export.export(directory, directory / "public")
                self.assertEqual(result["status"], "partial")
                self.assertEqual(result["completed_output_count"], 5)
                self.assertEqual(result["cases"][0]["status"], "artifact_validation_failed")

    def test_cumulative_reported_cost_preserves_unknowns_and_never_turns_hold_into_bill(self):
        for previous, current in ((0.194, 1.25), (None, 1.25), (0.194, None)):
            with self.subTest(previous=previous, current=current), tempfile.TemporaryDirectory() as directory:
                directory = Path(directory)
                state = lease(directory, run_id=VAST_RETRY_RUN_ID)
                state["prior_attempt"]["reported_charge_usd"] = previous
                state["prior_attempt"]["private_token"] = "never-public"
                state["provider_actual_charge_usd"] = current
                state["transfer_observation"] = {"billable_source": "provider", "billable_inbound_gb": 1,
                                                 "billable_outbound_gb": 1, "billing_unit_bytes": 1_000_000_000}
                (directory / "state.json").write_text(json.dumps(state))
                result = export.export(directory, directory / "public")
                self.assertEqual(result["provider_actual_charge_usd"], current)
                self.assertEqual(result["prior_attempt"]["reported_charge_usd"], previous)
                self.assertEqual(result["prior_exposure_usd"], 0.65)
                self.assertNotIn("never-public", json.dumps(result))
                if previous is None or current is None:
                    self.assertIsNone(result["cumulative_stage_reported_usd"])
                    self.assertEqual(result["cumulative_stage_reported_status"], "pending")
                else:
                    self.assertAlmostEqual(result["cumulative_stage_reported_usd"], 1.444)
                    self.assertEqual(result["cumulative_stage_reported_status"], "reported_to_date_not_final")
                self.assertAlmostEqual(result["whole_experiment_usd_estimate"], 1.82)
                self.assertIsNone(result["cumulative_stage_usd_estimate"])

    def test_recovery_cumulative_charges_require_all_three_known_and_publish_only_sanitized_prior(self):
        for initial, retry, current in ((0.194, 0.267, 1.25), (None, 0.267, 1.25),
                                        (0.194, None, 1.25), (0.194, 0.267, None)):
            with self.subTest(initial=initial, retry=retry, current=current), tempfile.TemporaryDirectory() as directory:
                directory = Path(directory)
                state = lease(directory, run_id=VAST_RECOVERY_RUN_ID)
                state["prior_attempt"]["reported_charge_usd"] = initial
                state["additional_prior_attempts"][0]["reported_charge_usd"] = retry
                state["additional_prior_attempts"][0]["private_token"] = "never-public"
                state["provider_actual_charge_usd"] = current
                state["transfer_observation"] = {"billable_source": "provider", "billable_inbound_gb": 1,
                                                 "billable_outbound_gb": 1, "billing_unit_bytes": 1_000_000_000}
                (directory / "state.json").write_text(json.dumps(state))
                result = export.export(directory, directory / "public")
                self.assertEqual(result["provider_actual_charge_usd"], current)
                self.assertEqual(result["prior_attempt"]["reported_charge_usd"], initial)
                self.assertEqual(result["prior_attempt"]["exposure_hold_usd"], 0.65)
                self.assertEqual(result["additional_prior_attempts"], [{
                    "run_id": VAST_RETRY_RUN_ID, "instance_id": 51807213, "absence_verified": True,
                    "reported_charge_usd": retry, "observed_drawdown_usd": 0.266443223, "exposure_hold_usd": 0.75}])
                self.assertEqual(result["prior_exposure_usd"], 1.4)
                self.assertNotIn("never-public", json.dumps(result))
                if any(charge is None for charge in (initial, retry, current)):
                    self.assertIsNone(result["cumulative_stage_reported_usd"])
                    self.assertEqual(result["cumulative_stage_reported_status"], "pending")
                else:
                    self.assertAlmostEqual(result["cumulative_stage_reported_usd"], 1.711)
                    self.assertEqual(result["cumulative_stage_reported_status"], "reported_to_date_not_final")
                self.assertAlmostEqual(result["whole_experiment_usd_estimate"], 1.82)
                self.assertIsNone(result["cumulative_stage_usd_estimate"])
                self.assertAlmostEqual(result["cumulative_window_plus_admission_network_usd_bound"],
                                       1.4 + result["window_plus_admission_network_usd_bound"])

    def test_recovery_rejects_missing_duplicate_foreign_unclosed_and_inconsistent_prior_evidence(self):
        for defect in ("missing", "duplicate", "foreign_run", "foreign_instance", "unclosed",
                       "negative_charge", "insufficient_hold", "missing_additional_hold", "double_counted_hold"):
            with self.subTest(defect=defect), tempfile.TemporaryDirectory() as directory:
                directory = Path(directory)
                state = lease(directory, run_id=VAST_RECOVERY_RUN_ID)
                additional = state["additional_prior_attempts"]
                if defect == "missing":
                    del state["additional_prior_attempts"]
                elif defect == "duplicate":
                    additional.append(dict(additional[0]))
                elif defect == "foreign_run":
                    additional[0]["run_id"] = VAST_RUN_ID
                elif defect == "foreign_instance":
                    additional[0]["instance_id"] = 51778886
                elif defect == "unclosed":
                    additional[0]["absence_verified"] = False
                elif defect == "negative_charge":
                    additional[0]["reported_charge_usd"] = -0.037
                elif defect == "insufficient_hold":
                    additional[0]["exposure_hold_usd"] = "0.02"
                    state["prior_exposure_usd"] = "0.67"
                elif defect == "missing_additional_hold":
                    state["prior_exposure_usd"] = "0.65"
                else:
                    state["prior_exposure_usd"] = "2.05"
                (directory / "state.json").write_text(json.dumps(state))
                with self.assertRaises(ValueError):
                    export.export(directory, directory / "public")
                self.assertFalse((directory / "public").exists())

    def test_frozen_natten_requires_manifest_hash_for_the_exact_target_wheel(self):
        url = "https://github.com/SHI-Labs/NATTEN/releases/download/v0.21.7/natten-0.21.7%2Btorch2130cu132-cp312-cp312-linux_x86_64.whl"
        source = ('[[package]]\nname = "natten"\nversion = "0.21.7+torch2130cu132"\n'
                  'source = { registry = "https://whl.natten.org/" }\nwheels = [{url = "' + url + '"}]\n')
        with tempfile.TemporaryDirectory() as directory:
            lock = Path(directory) / "uv.lock"
            lock.write_text(source)
            manifest = {"name": "natten", "version": "0.21.7+torch2130cu132", "url": url, "size": 203625872}
            manifest_path = lock.parent / ".natten-wheel.json"
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                frozen_natten_requirement(lock)
            manifest["sha256"] = "a" * 64
            manifest_path.write_text(json.dumps(manifest))
            self.assertEqual(frozen_natten_requirement(lock), "natten @ " + url + " --hash=sha256:" + "a" * 64 + "\n")
            lock.write_text(source.replace("cp312-cp312", "cp311-cp311"))
            with self.assertRaises(ValueError):
                frozen_natten_requirement(lock)


if __name__ == "__main__":
    unittest.main()
