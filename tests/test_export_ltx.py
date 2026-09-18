"""Offline export integrity and accounting checks; no GPU or network access."""

import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import export_ltx as export


class ExportLTXTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "results").mkdir()
        self.lease = self.root / "private"
        self.lease.mkdir()
        self.state = {"status": "terminated", "decode_verified": True,
                      "generation_submissions": 1, "verified_absent_at": 1000,
                      "end_to_end_seconds": 20}
        self.runtime = {"phase": "completed", "run_id": export.RUN_ID,
                        "model_revision": export.REVISION, "source_revision": export.SOURCE,
                        "output_sha256": hashlib.sha256(b"fixture").hexdigest(),
                        "processing_seconds": 10}
        self.preparation = {"download_seconds": 100, "verified_files": [], "ready_at": 500, "started_at": 100}
        self.allocation = {"startedAt": "1970-01-01T00:00:00Z", "cost": export.HOURLY}
        (self.lease / (export.RUN_ID + ".mp4")).write_bytes(b"fixture")
        (self.lease / "gpu-samples.csv").write_text("memory.used [MiB]\n100 MiB\n")
        self.probe = {"streams": [{"codec_type": "video", "width": export.WIDTH,
                     "height": export.HEIGHT, "nb_frames": str(export.FRAMES),
                     "r_frame_rate": str(export.FPS) + "/1", "duration": "5.041667"}]}

    def execute(self):
        records = {"state.json": self.state, "generation-status.json": self.runtime,
                   "prepare-status.json": self.preparation, "allocation-observation.json": self.allocation}
        with patch.object(export, "ROOT", self.root), patch.object(export, "LEASE", self.lease), \
                patch.object(export, "read", side_effect=records.__getitem__), \
                patch.object(export.subprocess, "check_output", return_value=json.dumps(self.probe)), \
                patch.object(export.subprocess, "run"), contextlib.redirect_stdout(io.StringIO()):
            export.main()
        return json.loads((self.root / "results" / (export.RUN_ID + ".json")).read_text())

    def test_cost_boundaries_are_separate_and_requested_duration_is_used(self):
        record = self.execute()
        self.assertAlmostEqual(record["cost"]["processing_gpu_usd_per_requested_video_second"], 10 * export.HOURLY / 3600 / 5)
        self.assertAlmostEqual(record["cost"]["lease_window_gpu_usd_estimate"], 1000 * export.HOURLY / 3600)
        self.assertIsNone(record["cost"]["provider_actual_charge_usd"])
        self.assertFalse(record["latency_target_pass"])

    def test_live_pod_is_refused(self):
        self.state["status"] = "created"
        with self.assertRaises(ValueError):
            self.execute()

    def test_truncated_sample_is_excluded_and_disclosed(self):
        (self.lease / "gpu-samples.csv").write_text("timestamp,memory.used [MiB]\nfull,100 MiB\npartial")
        record = self.execute()
        self.assertEqual(record["incomplete_gpu_samples_excluded"], 1)
        self.assertEqual(record["gpu_sample_count"], 1)

    def test_hash_mismatch_is_refused(self):
        self.runtime["output_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            self.execute()

    def test_wrong_frames_are_refused(self):
        self.probe["streams"][0]["nb_frames"] = "120"
        with self.assertRaises(ValueError):
            self.execute()
