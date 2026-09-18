from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import h3_lora_compat as compat
from h3_trial import require_successful_warmup


class CompatibilityTests(unittest.TestCase):
    def test_missing_quant_method_reproduces_and_is_fixed(self):
        wrapped = types.SimpleNamespace(base_layer=types.SimpleNamespace(quant_method=object()))
        with self.assertRaises(AttributeError):
            compat.extract_probe(compat.OLD)(wrapped)
        self.assertFalse(compat.extract_probe(compat.NEW)(wrapped))

    def test_plain_and_quantized_paths_preserved(self):
        probe = compat.extract_probe(compat.NEW)
        self.assertFalse(probe(types.SimpleNamespace(quant_method=None)))
        for answer in (True, False):
            seen = []
            layer = types.SimpleNamespace(quant_method=types.SimpleNamespace(
                accepts_mxfp8_input=lambda original: seen.append(original) or answer))
            self.assertEqual(probe(layer), answer)
            self.assertEqual(seen, [layer])

    def test_patch_is_pinned_idempotent_and_rejects_unknown_source(self):
        with self.assertRaises(ValueError):
            compat.patched_source(compat.OLD)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.py"
            path.write_text(compat.OLD)
            with patch.object(compat, "SOURCE_SHA256", compat.digest(compat.OLD)):
                first = compat.apply_to(path)
                self.assertEqual(path.read_text(), compat.NEW)
                self.assertEqual(first, compat.apply_to(path))
                path.write_text(compat.NEW + "\n# unexpected\n")
                with self.assertRaises(ValueError):
                    compat.apply_to(path)

    def test_warmup_failure_overrides_ready_message(self):
        with self.assertRaises(RuntimeError):
            require_successful_warmup("Synthetic server warmup failed; continuing startup\nThe server is fired up and ready to roll!")
        with self.assertRaises(RuntimeError):
            require_successful_warmup("GET /health 200 OK")
        require_successful_warmup("server warmup req (1344x768x124f, 2/50 steps), last=46.74s")
