import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from h3_metrics import cost_estimate, gpu_summary, stage_metrics


class H3MetricsTests(unittest.TestCase):
    def test_cost_denominator_is_requested_video_time(self):
        result = cost_estimate(30, 12, 5)
        self.assertEqual(result["total_usd"], "0.1")
        self.assertEqual(result["usd_per_requested_video_second"], "0.02")

    def test_rejects_missing_or_invalid_cost_basis(self):
        for values in ((-1, 12, 5), (1, -1, 5), (1, 12, 0), ("NaN", 12, 5)):
            with self.assertRaises(ValueError):
                cost_estimate(*values)

    def test_stages_and_warmup_are_separate(self):
        log = ("[MiniMaxH3DenoisingStage] finished in 4.0 seconds\n"
               "server warmup req (1344x768x124f, 2/50 steps), last=40.0s\n"
               "[MiniMaxH3DenoisingStage] finished in 12.5 seconds\n")
        result = stage_metrics(log)
        self.assertEqual(result["last_completed_stages_seconds"]["MiniMaxH3DenoisingStage"], 12.5)
        self.assertEqual(result["builtin_warmup_last_seconds"], 40.0)
        self.assertIsNone(stage_metrics("")["builtin_warmup_last_seconds"])

    def test_samples_are_windowed_per_gpu_with_missing_power_allowed(self):
        text = ("timestamp, index, memory.used [MiB], utilization.gpu [%], power.draw [W]\n"
                "1970/01/01 00:00:01.000, 0, 999 MiB, 100 %, 400 W\n"
                "1970/01/01 00:00:02.000, 0, 100 MiB, 50 %, 200 W\n"
                "1970/01/01 00:00:03.000, 0, 200 MiB, 100 %, 300 W\n"
                "1970/01/01 00:00:03.000, 1, 300 MiB, 100 %, [N/A]\n")
        result = gpu_summary(text, 2, 3)
        self.assertEqual(result["0"]["sample_count"], 2)
        self.assertEqual(result["0"]["used_mib_sampled_max"], 200)
        self.assertEqual(result["0"]["utilization_percent_sampled_mean"], 75)
        self.assertIsNone(result["1"]["power_w_sampled_max"])
        self.assertEqual(gpu_summary(text, 10, 20), {})
        self.assertEqual(gpu_summary(text + "1970/01/01 00:00:0", 2, 3), result)
        with self.assertRaises(ValueError):
            gpu_summary(text + "1970/01/01 00:00:0\n" + text.splitlines()[1] + "\n", 2, 3)


if __name__ == "__main__":
    unittest.main()
