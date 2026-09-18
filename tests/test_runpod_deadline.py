"""Offline tests; no paid requests."""

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import runpod_deadline


class DeadlineTests(unittest.TestCase):
    def test_only_exact_created_identity(self):
        self.assertTrue(runpod_deadline.owns({"id": "abcdef", "name": "our-trial"}, "abcdef", "our-trial"))
        self.assertFalse(runpod_deadline.owns({"id": "abcdef", "name": "other"}, "abcdef", "our-trial"))
        self.assertFalse(runpod_deadline.owns({"id": "other", "name": "our-trial"}, "abcdef", "our-trial"))

    @patch("runpod_deadline.request")
    def test_refuses_mismatched_pod(self, request):
        request.return_value = (200, {"id": "abcdef", "name": "other"})
        with self.assertRaises(RuntimeError):
            runpod_deadline.terminate("abcdef", "our-trial", "not-a-real-key")
        request.assert_called_once_with("GET", "abcdef", "not-a-real-key")

    @patch("runpod_deadline.request")
    def test_acceptance_is_not_verified_deletion(self, request):
        own = {"id": "abcdef", "name": "our-trial"}
        request.side_effect = [(200, own), (204, {}), (200, own)]
        self.assertFalse(runpod_deadline.terminate("abcdef", "our-trial", "not-a-real-key"))

    @patch("runpod_deadline.request")
    def test_verified_delete(self, request):
        request.side_effect = [(200, {"id": "abcdef", "name": "our-trial"}), (204, {}), (404, {})]
        self.assertTrue(runpod_deadline.terminate("abcdef", "our-trial", "not-a-real-key"))

    @patch("runpod_deadline.request")
    def test_already_absent_is_safe(self, request):
        request.return_value = (404, {})
        self.assertTrue(runpod_deadline.terminate("abcdef", "our-trial", "not-a-real-key"))
        self.assertEqual(request.call_count, 1)

    def test_invalid_id_rejected_before_network(self):
        with self.assertRaises(ValueError):
            runpod_deadline.request("DELETE", "../other", "not-a-real-key")


if __name__ == "__main__":
    unittest.main()
