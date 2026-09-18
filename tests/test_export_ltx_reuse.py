"""Offline safety checks for the warm comparison exporter."""

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import export_ltx_reuse as export


class ReuseExportTests(unittest.TestCase):
    def test_refuses_open_lease(self):
        with patch.object(export, "read", return_value={"status": "created"}):
            with self.assertRaises(ValueError):
                export.main()

    def test_refuses_incomplete_request_set(self):
        with patch.object(export, "read", return_value={"status": "terminated", "decode_verified": True, "generation_submissions": 3}):
            with self.assertRaises(ValueError):
                export.main()

    def test_decoded_hash_uses_full_stream_and_error_check(self):
        with patch.object(export.subprocess, "check_output", return_value="SHA256=" + "a" * 64 + "\n") as run:
            self.assertEqual(export.decoded_hash(Path("fixture.mp4"), "0:v:0"), "a" * 64)
            args = run.call_args.args[0]
            self.assertIn("-xerror", args)
            self.assertIn("0:v:0", args)

    def test_missing_decoded_hash_is_refused(self):
        with patch.object(export.subprocess, "check_output", return_value="unavailable"):
            with self.assertRaises(ValueError):
                export.decoded_hash(Path("fixture.mp4"), "0:a:0")
