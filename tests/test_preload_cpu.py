import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from preload_cpu import verify_file


class PreloadTests(unittest.TestCase):
    def test_manifest_contains_only_frozen_partition_and_two_adapters(self):
        manifest = json.loads((ROOT / "preload-manifest.json").read_text())
        self.assertEqual(len(manifest["files"]), 81)
        self.assertTrue(all(entry["path"].startswith("FL2VA/") for entry in manifest["files"]))
        self.assertEqual(sum(entry["bytes"] for entry in manifest["files"]), manifest["base_bytes"])
        self.assertEqual(set(manifest["adapters"]), {"larry8", "light4"})
        total = manifest["base_bytes"] + sum(a["bytes"] for a in manifest["adapters"].values())
        self.assertLess(total, 200_000_000_000)

    def test_checksums_cover_content_not_only_size(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture"
            path.write_bytes(b"abc")
            for kind, checksum in (("sha256", hashlib.sha256(b"abc").hexdigest()),
                                   ("git_blob_sha1", hashlib.sha1(b"blob 3\0abc").hexdigest())):
                entry = {"bytes": 3, "hash_kind": kind, "hash": checksum}
                verify_file(path, entry)
                with self.assertRaises(ValueError):
                    verify_file(path, dict(entry, hash="0" * len(checksum)))
            with self.assertRaises(ValueError):
                verify_file(path, {"bytes": 4})
