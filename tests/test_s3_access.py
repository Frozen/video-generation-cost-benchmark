from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from check_s3 import check


class S3AccessTests(unittest.TestCase):
    def test_read_only_auth_probe_hides_identity_and_secrets(self):
        run = Mock(return_value=SimpleNamespace(returncode=0,
            stdout="<ListAllMyBucketsResult><Owner><ID>private</ID></Owner><Buckets/></ListAllMyBucketsResult>\n200"))
        result = check("EUR-IS-1", {"access": "fake-user", "secret": "fake-secret"}, run)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["bucket_count"], 0)
        self.assertNotIn("private", str(result))
        command = run.call_args.args[0]
        self.assertNotIn("fake-secret", " ".join(command))
        self.assertNotIn("--location", command)
        self.assertNotIn("--upload-file", command)
        self.assertIn("fake-secret", run.call_args.kwargs["input"])

    def test_reflected_error_body_is_not_returned(self):
        run = Mock(return_value=SimpleNamespace(returncode=0, stdout="fake-secret\n403"))
        result = check("EUR-IS-1", {"access": "fake-user", "secret": "fake-secret"}, run)
        self.assertEqual(result, {"status": "access_not_verified", "http": 403})

    def test_invalid_keys_or_destination_do_not_send_credentials(self):
        run = Mock()
        self.assertEqual(check("EUR-IS-1", {"access": "", "secret": "fake"}, run)["status"], "missing_or_invalid_credentials")
        with self.assertRaises(ValueError):
            check("untrusted.example", {"access": "fake", "secret": "fake"}, run)
        run.assert_not_called()
