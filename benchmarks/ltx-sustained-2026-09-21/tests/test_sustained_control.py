import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from ltx_sustained_trial import hour_complete
import fal_sustained as fal


class ControlTests(unittest.TestCase):
    def test_short_run_is_never_complete(self):
        self.assertFalse(hour_complete([dict(event='window_finished', worker_window_seconds=3599,
                                            stop_reason='target_duration_reached')]))
        self.assertFalse(hour_complete([]))

    def test_failure_after_hour_is_not_success(self):
        rows = [dict(event='window_finished', worker_window_seconds=3612, stop_reason='target_duration_reached')]
        self.assertTrue(hour_complete(rows))
        self.assertFalse(hour_complete(rows + [dict(event='worker_failed')]))

    def test_uncertain_submission_marker_never_posts_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / 'state.json').write_text(json.dumps(dict(status='submission_started_do_not_replay')))
            with patch.object(fal, 'request') as network:
                with self.assertRaises(RuntimeError):
                    fal.collect(folder, 'dummy')
                network.assert_not_called()

    def test_completed_request_never_posts_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / 'state.json').write_text(json.dumps(dict(status='download_complete')))
            with patch.object(fal, 'request') as network:
                self.assertEqual(fal.collect(folder, 'dummy')['status'], 'download_complete')
                network.assert_not_called()


if __name__ == '__main__':
    unittest.main()
