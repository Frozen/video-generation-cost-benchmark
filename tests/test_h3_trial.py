"""Offline request-contract tests; no prompt corpus or credentials committed."""

import hashlib
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import h3_trial


class PayloadTests(unittest.TestCase):
    def test_language_variant_preserves_native_request(self):
        original = "Offline test scene."
        digest = hashlib.sha256(original.encode()).hexdigest()
        with patch.object(h3_trial, "SOURCE_PROMPT_SHA256", digest):
            payload = h3_trial.payload_from(original)
        self.assertEqual(payload["prompt"], original + "\n\n" + h3_trial.ENGLISH)
        self.assertEqual(payload["target"], {"short_edge": 768, "aspect_ratio": "16:9", "duration_seconds": 5.0})
        self.assertEqual((payload["seconds"], payload["seed"], payload["num_inference_steps"]), (5, 42, 50))
        self.assertEqual(payload["quality"], "lossless")
        self.assertEqual(payload["conditions"], [])
        self.assertEqual(payload["num_outputs_per_prompt"], 1)

    def test_unrecognized_source_is_rejected(self):
        with self.assertRaises(ValueError):
            h3_trial.payload_from("Not the frozen source")

    def test_adapters_preserve_request_except_sigma_points(self):
        original = "Offline test scene."
        with patch.object(h3_trial, "SOURCE_PROMPT_SHA256", hashlib.sha256(original.encode()).hexdigest()):
            base = h3_trial.payload_from(original)
            for recipe, points in (("larry8", 9), ("light4", 5)):
                payload = h3_trial.payload_from(original, recipe)
                self.assertEqual(payload, dict(base, num_inference_steps=points))
                self.assertEqual(h3_trial.ADAPTERS[recipe]["evaluations"], points - 1)
        self.assertEqual(h3_trial.ADAPTERS["light4"]["alpha"], 8)
        self.assertNotEqual(h3_trial.ADAPTERS["larry8"]["repo"], h3_trial.ADAPTERS["light4"]["repo"])

    def test_adapter_downloads_are_pinned_and_checksummed(self):
        for adapter in h3_trial.ADAPTERS.values():
            self.assertRegex(adapter["revision"], r"^[a-f0-9]{40}$")
            self.assertRegex(adapter["sha256"], r"^[a-f0-9]{64}$")
            self.assertTrue(adapter["filename"].endswith(".safetensors"))
            self.assertGreater(adapter["bytes"], 0)


if __name__ == "__main__":
    unittest.main()
