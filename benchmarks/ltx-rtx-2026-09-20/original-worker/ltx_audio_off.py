"""Narrow audio-modality ablation of the pinned upstream distilled call.

The shared prompt encoder and resident joint weights are retained. This removes
audio latent sampling, cross-modal transformer work and audio decoding, not every
audio-related parameter or text projection. Video RNG draws can differ after
audio draws disappear; equal seeds do not promise equal pictures.
"""

import ast
import copy
import hashlib
from pathlib import Path

DISTILLED_SHA256 = "feb52574ea5f892a8f6887159bc9ea3d5c9c6493dec0d88d7594b9558fd5e57f"


def audio_off_method(source):
    """Change only the two modality inputs/denoisers and the audio decode call."""
    if hashlib.sha256(source).hexdigest() != DISTILLED_SHA256:
        raise ValueError("Audio ablation requires the exact reviewed distilled source")
    tree = ast.parse(source)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "DistilledPipeline")
    method = copy.deepcopy(next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "__call__"))
    changed = {"stage": 0, "denoiser": 0, "decode": 0}
    for node in ast.walk(method):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "self" and node.func.attr == "stage":
                audio = next(k for k in node.keywords if k.arg == "audio")
                if not isinstance(audio.value, ast.Call) or not isinstance(audio.value.func, ast.Name) or audio.value.func.id != "ModalitySpec":
                    raise ValueError("Unexpected audio modality construction")
                audio.value = ast.Constant(None)
                changed["stage"] += 1
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "SimpleDenoiser":
            if len(node.args) != 2 or not isinstance(node.args[1], ast.Name) or node.args[1].id != "audio_context":
                raise ValueError("Unexpected denoiser context")
            node.args[1] = ast.Constant(None)
            changed["denoiser"] += 1
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id == "decoded_audio":
            if not isinstance(node.value, ast.Call) or not isinstance(node.value.func, ast.Attribute) or node.value.func.attr != "audio_decoder":
                raise ValueError("Unexpected audio decoder")
            node.value = ast.Constant(None)
            changed["decode"] += 1
    if changed != {"stage": 2, "denoiser": 2, "decode": 1}:
        raise ValueError("Incomplete audio ablation")
    if any(isinstance(n, ast.Name) and n.id == "audio_state" and isinstance(n.ctx, ast.Load) for n in ast.walk(method)):
        raise ValueError("A removed audio state is still used")
    return ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[]))


def pipeline_class():
    """Create a scoped subclass; never mutate upstream files or the native class."""
    import ltx_pipelines.distilled as native
    source = Path(native.__file__).read_bytes()
    namespace = dict(vars(native))
    exec(compile(audio_off_method(source), "<pinned-ltx-audio-off>", "exec"), namespace)
    return type("VideoOnlyDistilledPipeline", (native.DistilledPipeline,), {"__call__": namespace["__call__"]})


class AuditedDenoiser:
    """Observe actual transformer calls and reject the wrong modality at runtime."""

    def __init__(self, denoiser, audio, calls):
        self.denoiser, self.audio, self.calls = denoiser, audio, calls

    def __call__(self, transformer, video_state, audio_state, *args, **kwargs):
        if video_state is None or (audio_state is not None) != self.audio:
            raise RuntimeError("Unexpected sampled modality")

        def forward(*positional, **named):
            if positional or named.get("video") is None or (named.get("audio") is not None) != self.audio:
                raise RuntimeError("Unexpected transformer modality")
            result = transformer(**named)
            self.calls.append({"video": True, "audio": self.audio})
            return result

        return self.denoiser(forward, video_state, audio_state, *args, **kwargs)
