"""Scoped transformer residency for the pinned single-GPU, uncompiled LTX pipeline."""

from contextlib import contextmanager
import time


class ResidentTransformer:
    """Reuse weights, never generated latents, text embeddings or output videos."""

    def __init__(self, stage):
        if stage._is_streaming or stage._compilation_config is not None or stage._quantization is not None:
            raise ValueError("Residency test requires the pinned non-streaming BF16 eager stage")
        self.stage = stage
        self.original = stage._transformer_ctx
        self.model = None
        self.active = False
        self.closed = False
        self.build_count = 0
        self.build_seconds = 0.0
        stage._transformer_ctx = self.context

    @contextmanager
    def context(self, **kwargs):
        if self.closed or self.active:
            raise RuntimeError("Closed or concurrently used resident transformer")
        if set(kwargs) - {"video_tools"}:
            raise ValueError("Unreviewed builder options")
        self.active = True
        try:
            if self.model is None:
                start = time.monotonic()
                self.model = self.stage._build_transformer(**kwargs)
                self.build_seconds += time.monotonic() - start
                self.build_count += 1
            yield self.model
        finally:
            self.active = False

    def close(self):
        if self.active:
            raise RuntimeError("Cannot dispose an active transformer")
        if self.closed:
            return
        self.stage._transformer_ctx = self.original
        if self.model is not None:
            self.model.dispose()
            self.model = None
        self.closed = True
