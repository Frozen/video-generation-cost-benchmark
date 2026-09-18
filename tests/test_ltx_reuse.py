"""GPU-free lifecycle tests for the narrowly scoped residency experiment."""

from contextlib import nullcontext
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from ltx_reuse import ResidentTransformer
from ltx_reuse_config import CASES, WARMUP_STAGE_1, WARMUP_STAGE_2, output_id


class ReuseTests(unittest.TestCase):
    def stage(self):
        model = SimpleNamespace(dispose=Mock())
        return SimpleNamespace(_is_streaming=False, _compilation_config=None, _quantization=None,
                               _transformer_ctx=lambda **kwargs: nullcontext(model),
                               _build_transformer=Mock(return_value=model)), model

    def test_two_stages_and_second_request_share_weights_only(self):
        stage, model = self.stage()
        cache = ResidentTransformer(stage)
        for shape in ("low", "high", "low", "high"):
            with stage._transformer_ctx(video_tools=shape) as actual:
                self.assertIs(actual, model)
        self.assertEqual(cache.build_count, 1)
        self.assertEqual(stage._build_transformer.call_count, 1)
        model.dispose.assert_not_called()
        cache.close()
        model.dispose.assert_called_once()
        cache.close()
        model.dispose.assert_called_once()

    def test_restore_original_context(self):
        stage, _ = self.stage()
        original = stage._transformer_ctx
        cache = ResidentTransformer(stage)
        cache.close()
        self.assertIs(stage._transformer_ctx, original)

    def test_streaming_or_compiled_modes_are_refused(self):
        for field in ("_is_streaming", "_compilation_config", "_quantization"):
            stage, _ = self.stage()
            setattr(stage, field, True)
            with self.assertRaises(ValueError):
                ResidentTransformer(stage)

    def test_no_concurrent_or_closed_use(self):
        stage, _ = self.stage()
        cache = ResidentTransformer(stage)
        with cache.context():
            with self.assertRaises(RuntimeError):
                with cache.context():
                    pass
            with self.assertRaises(RuntimeError):
                cache.close()
        cache.close()
        with self.assertRaises(RuntimeError):
            with cache.context():
                pass

    def test_failure_does_not_rebuild_or_leave_context_active(self):
        stage, _ = self.stage()
        cache = ResidentTransformer(stage)
        with self.assertRaises(ValueError):
            with cache.context():
                raise ValueError("mock inference failure")
        self.assertFalse(cache.active)
        self.assertEqual(cache.build_count, 1)
        cache.close()

    def test_two_short_warmups_and_two_measurements_have_unique_ids(self):
        self.assertEqual(len(CASES), 4)
        self.assertEqual(sum(case[2] for case in CASES), 2)
        self.assertEqual(len({output_id(case[0]) for case in CASES}), 4)
        with self.assertRaises(ValueError):
            output_id("unapproved")
        self.assertEqual(len(WARMUP_STAGE_1) - 1, 2)
        self.assertEqual(len(WARMUP_STAGE_2) - 1, 2)
        self.assertEqual(WARMUP_STAGE_1[-1], 0)
        self.assertEqual(WARMUP_STAGE_2[-1], 0)
