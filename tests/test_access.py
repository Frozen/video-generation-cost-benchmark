import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from check_access import CHECKS, ENDPOINT, check, load_keys


class AccessTests(unittest.TestCase):
    def load(self, content):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env.local"
            path.write_text(content)
            return load_keys(path)

    def reply(self, body, http=200):
        return Mock(return_value=SimpleNamespace(returncode=0, stdout=json.dumps(body) + "\n" + str(http)))

    def test_aliases_quotes_comments_and_export(self):
        self.assertEqual(self.load("export FAL_API='fake-fal' # comment\nRUNPOD_API=\"fake-runpod\"\n"),
                         {"fal": "fake-fal", "runpod": "fake-runpod"})

    def test_no_shell_expansion(self):
        self.assertEqual(self.load("FAL_KEY='$(false)'\n")["fal"], "$(false)")

    def test_duplicate_and_conflicting_aliases(self):
        for value in ("FAL_API=a\nFAL_API=b", "FAL_API=a\nFAL_KEY=b", "FAL_API=a b", "FAL_API='a"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.load(value)

    def test_empty_key_does_not_send_request(self):
        run = Mock()
        self.assertEqual(check("fal_pricing", "", run)["status"], "missing_key")
        run.assert_not_called()

    def test_control_characters_do_not_send_request(self):
        for key in ("secret\ninjection", "secret\rinjection", "secret with-space", "secret\x00"):
            run = Mock()
            self.assertEqual(check("runpod_pods", key, run)["status"], "invalid_key_format")
            run.assert_not_called()

    def test_fixed_read_only_destinations(self):
        self.assertEqual(len(CHECKS), 3)
        for name in CHECKS:
            run = self.reply([], 401)
            check(name, "fake-secret", run)
            args, kwargs = run.call_args
            command = args[0]
            self.assertNotIn("fake-secret", " ".join(command))
            self.assertNotIn("--location", command)
            self.assertNotIn("--retry", command)
            self.assertNotIn("--data", command)
            self.assertEqual(command[1], "-q")
            self.assertIn("fake-secret", kwargs["input"])
            self.assertTrue(command[-1].startswith(("https://api.fal.ai/", "https://api.runpod.io/")))

    def test_curl_config_escaping(self):
        run = self.reply([], 401)
        key = 'fake"\\secret'
        check("runpod_pods", key, run)
        config = run.call_args.kwargs["input"]
        self.assertEqual(json.loads(config.removeprefix("header = ")), "Authorization: Bearer " + key)

    def test_error_bodies_and_identity_are_not_printed(self):
        for http in (401, 403, 500):
            result = check("runpod_pods", "fake-secret", self.reply({"detail": "fake-secret", "email": "private@example.test"}, http))
            self.assertNotIn("fake-secret", json.dumps(result))
            self.assertNotIn("private@example.test", json.dumps(result))
            self.assertEqual(result["http"], http)
        result = check("runpod_pods", "fake-secret", self.reply([{"id": "private-pod-id"}]))
        self.assertNotIn("private-pod-id", json.dumps(result))

    def test_scope_denial_not_invalid_key(self):
        result = check("fal_balance", "fake-secret", self.reply({}, 403))
        self.assertEqual(result["status"], "access_denied")

    def test_price_allowlist_and_base_price_warning(self):
        run = self.reply({"prices": [{"endpoint_id": ENDPOINT, "unit_price": 0.05, "unit": "seconds", "currency": "USD", "private": "omit"}]})
        result = check("fal_pricing", "fake-secret", run)
        self.assertEqual(result["status"], "ok")
        self.assertNotIn("omit", json.dumps(result))
        self.assertIn("not a resolution-specific quote", result["pricing_note"])

    def test_reflected_key_suppressed(self):
        run = self.reply({"prices": [{"endpoint_id": ENDPOINT, "unit_price": 0.05, "unit": "fake-secret", "currency": "USD"}]})
        self.assertEqual(check("fal_pricing", "fake-secret", run)["status"], "unsafe_response_suppressed")

    def test_transport_error_suppressed(self):
        run = Mock(side_effect=subprocess.TimeoutExpired("fake-secret", 35))
        self.assertEqual(check("runpod_pods", "fake-secret", run)["status"], "transport_error")

    def test_invalid_payload(self):
        for data in ({}, None, "invalid"):
            self.assertEqual(check("fal_pricing", "fake-secret", self.reply(data))["status"], "invalid_response")


if __name__ == "__main__":
    unittest.main()
