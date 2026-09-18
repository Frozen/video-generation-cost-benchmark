"""Opt-in, source-pinned workaround for H3's LoRA MXFP8 capability probe.

The wrapper's ordinary forward path remains intact. Do not unwrap it and pass
the base layer to an optimized kernel, which could bypass the adapter.
"""

import argparse
import ast
import hashlib
from pathlib import Path
import types

SOURCE_SHA256 = "2a61d5c8b0418eed72fd3443cc47b6a06ed8512f6c834b608aa4e3e55e7489fa"
OLD = """def _accepts_mxfp8_input(linear: nn.Module) -> bool:
    return linear.quant_method is not None and linear.quant_method.accepts_mxfp8_input(
        linear
    )
"""
NEW = """def _accepts_mxfp8_input(linear: nn.Module) -> bool:
    # LoRA wrappers do not expose quant_method. Keep their normal forward path.
    quant_method = getattr(linear, "quant_method", None)
    return quant_method is not None and quant_method.accepts_mxfp8_input(linear)
"""


def digest(source):
    return hashlib.sha256(source.encode()).hexdigest()


def patched_source(source):
    if digest(source) != SOURCE_SHA256 or source.count(OLD) != 1:
        raise ValueError("Unexpected upstream source; refusing compatibility patch")
    return source.replace(OLD, NEW, 1)


def extract_probe(source):
    node = next(node for node in ast.parse(source).body
                if isinstance(node, ast.FunctionDef) and node.name == "_accepts_mxfp8_input")
    namespace = {"nn": types.SimpleNamespace(Module=object)}
    exec(compile(ast.Module(body=[node], type_ignores=[]), "<capability-probe>", "exec"), namespace)
    return namespace["_accepts_mxfp8_input"]


def apply_to(path):
    """Apply a mechanical remote-runtime patch only to the verified source."""
    source = path.read_text()
    # Permit the second adapter in the same container to reuse this exact patch.
    original = source.replace(NEW, OLD, 1) if source.count(NEW) == 1 else source
    replacement = patched_source(original)
    if source not in (original, replacement):
        raise ValueError("Unexpected already-patched source")
    if source != replacement:
        path.write_text(replacement)
    return {"id": "h3-lora-mxfp8-capability-v1", "upstream_sha256": digest(original),
            "patched_sha256": digest(replacement), "gpu_validation": "pending"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-source", type=Path, required=True,
                        help="Verify and reproduce the bug locally; never modifies this file")
    args = parser.parse_args()
    original = args.check_source.read_text()
    replacement = patched_source(original)
    wrapped = types.SimpleNamespace(base_layer=types.SimpleNamespace(quant_method=object()))
    try:
        extract_probe(original)(wrapped)
    except AttributeError:
        pass
    else:
        raise RuntimeError("Pinned bug did not reproduce")
    if extract_probe(replacement)(wrapped) is not False:
        raise RuntimeError("Wrapper must retain its non-MXFP8 path")
    print("Pinned source verified; original AttributeError reproduced; patched probe passes.")
    print("Patched SHA-256: " + digest(replacement))
    print("CPU-only capability test; this command does not run GPU generation.")


if __name__ == "__main__":
    main()
