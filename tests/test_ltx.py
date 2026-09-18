"""Offline contract checks; these do not establish successful GPU execution."""
import hashlib
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ltx_config as config
import ltx_trial


class LTXTests(unittest.TestCase):
    def test_duration_and_canvas_are_native_valid(self):
        self.assertEqual(config.FRAMES % 8, 1)
        self.assertEqual(config.WIDTH % 64, 0)
        self.assertEqual(config.HEIGHT % 64, 0)
        self.assertAlmostEqual(config.FRAMES / config.FPS, 5.0416666667)

    def test_six_files_are_content_pinned(self):
        self.assertEqual(len(config.FILES), 6)
        for name, (size, sha) in config.FILES.items():
            self.assertTrue(name.endswith('.safetensors'))
            self.assertGreater(size, 0)
            self.assertRegex(sha, r'^[0-9a-f]{64}$')
        self.assertEqual(len(config.SOURCE), 40)

    def test_h100_bound_does_not_need_four_cards(self):
        # 200 GB temporary disk at USD .10/GB-month; conservative 30-day month.
        bound = (config.HOURLY + 200 * .10 / (30 * 24)) * config.MAX_LEASE_SECONDS / 3600
        self.assertLess(bound, float(config.RESERVATION))
        self.assertEqual(config.MAX_LEASE_SECONDS, 3600)

    def test_wrong_prompt_is_refused(self):
        with self.assertRaises(ValueError):
            config.validate_prompt('different prompt')

    def test_ssh_endpoint_validation(self):
        with self.assertRaises(ValueError):
            ltx_trial.ssh_args({'host': 'bad; command', 'port': 22})

    def test_user_hf_alias_is_recognized(self):
        self.assertIn('FACE_API', config.HF_ALIASES['hf'])

    def test_new_identity_does_not_reuse_h3(self):
        self.assertIn('LTX25', config.RUN_ID)
        self.assertNotIn('h100x4', str(ltx_trial.LEASE))

    def test_download_links_are_file_scoped_without_account_token(self):
        def reply(command, **kwargs):
            name = command[-1].split(config.REVISION + '/', 1)[1]
            size, sha = config.FILES[name]
            self.assertIn('Authorization: Bearer hf_test_only', kwargs['input'])
            self.assertNotIn('hf_test_only', ' '.join(command))
            url = 'https://us.aws.cdn.hf.co/object?Signature=test&Expires=' + str(int(time.time()) + 3600)
            return SimpleNamespace(returncode=0, stdout='HTTP/2 302\nlocation: '+url+'\nx-linked-size: '+str(size)+'\nx-linked-etag: "'+sha+'"\n')
        with patch.object(ltx_trial, 'load_keys', return_value={'hf': 'hf_test_only'}), \
                patch.object(ltx_trial.subprocess, 'run', side_effect=reply):
            links = ltx_trial.download_links(Path('/not/read'))
        self.assertEqual(set(links), set(config.FILES))
        self.assertNotIn('hf_test_only', str(links))

    def test_untrusted_download_redirect_is_refused(self):
        with patch.object(ltx_trial, 'load_keys', return_value={'hf': 'hf_test_only'}), \
                patch.object(ltx_trial.subprocess, 'run', return_value=SimpleNamespace(
                    returncode=0, stdout='HTTP/2 302\nlocation: https://untrusted.example/file\n')):
            with self.assertRaises(ValueError):
                ltx_trial.download_links(Path('/not/read'))
