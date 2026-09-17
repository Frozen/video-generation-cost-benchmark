import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from fal_reference import PARAMETERS, PromptParser, allowed_queue, curl, sha, validate_payload
import fal_reference


class FalReferenceTests(unittest.TestCase):
    def tearDown(self):
        fal_reference.select_profile("h3")

    def test_variants_have_isolated_markers_and_endpoints(self):
        directories, ids = set(), set()
        for variant in ("h3", "max", "turbo"):
            fal_reference.select_profile(variant)
            directories.add(fal_reference.PRIVATE)
            ids.add(fal_reference.RUN_ID)
            self.assertTrue(allowed_queue("https://queue.fal.run/" + fal_reference.ENDPOINT))
            for other, settings in fal_reference.PROFILES.items():
                if other != variant:
                    self.assertFalse(allowed_queue("https://queue.fal.run/" + settings[0]))
        self.assertEqual(len(directories), 3)
        self.assertEqual(len(ids), 3)

    def test_duplicate_submission_is_blocked_before_network(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "state.json").write_text('{}')
            with patch("fal_reference.PRIVATE", path), patch("fal_reference.curl") as request:
                with self.assertRaises(ValueError):
                    fal_reference.submit("fake-key")
                request.assert_not_called()

    def test_source_extraction_ignores_scripts_and_related_prompts(self):
        parser = PromptParser()
        parser.feed('<script>Copy prompt</script><button>Copy prompt</button><p>Original text.</p><h2>You Might Also Like</h2><p>Other text</p>')
        self.assertEqual("".join(parser.parts), "Original text.")

    def test_credentials_only_go_to_selected_queue(self):
        for url in ("https://evil.example/minimax/h3/", "http://queue.fal.run/minimax/h3/", "https://queue.fal.run@evil.example/minimax/h3/", "https://queue.fal.run/fal-ai/other/"):
            self.assertFalse(allowed_queue(url))
            with patch("fal_reference.subprocess.run") as run, self.assertRaises(ValueError):
                curl(url, key="fake-key")
            run.assert_not_called()
        self.assertTrue(allowed_queue("https://queue.fal.run/minimax/h3/requests/example/status"))

    def test_profile_and_hash_are_fixed(self):
        payload = json.dumps(dict(PARAMETERS, prompt="Fixture only")).encode()
        manifest = {"payload_sha256": sha(payload), "prompt_sha256": sha(b"Fixture only")}
        validate_payload(payload, manifest)
        with self.assertRaises(ValueError):
            validate_payload(payload + b" ", manifest)
        changed = json.loads(payload)
        changed["duration"] = 10
        with self.assertRaises(ValueError):
            validate_payload(json.dumps(changed).encode(), manifest)

    def test_post_is_single_and_disables_provider_retries(self):
        with patch("fal_reference.subprocess.run") as run:
            run.return_value.returncode = 0
            run.return_value.stdout = '{}\n200'
            curl("https://queue.fal.run/minimax/h3/text-to-video", key="fake-secret", payload=Path("fixture.json"))
            run.assert_called_once()
            command = run.call_args.args[0]
            self.assertNotIn("fake-secret", " ".join(command))
            self.assertIn("X-Fal-No-Retry: 1", command)
            self.assertNotIn("--retry", command)
            self.assertNotIn("--location", command)

    def test_transport_failure_does_not_resubmit(self):
        with patch("fal_reference.subprocess.run") as run:
            run.return_value.returncode = 28
            with self.assertRaises(RuntimeError):
                curl("https://queue.fal.run/minimax/h3/text-to-video", key="fake-key", payload=Path("fixture.json"))
            run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
