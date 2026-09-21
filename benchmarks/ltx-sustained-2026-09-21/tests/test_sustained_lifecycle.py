import json
from decimal import Decimal
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from summarize_lifecycle import summarize


class LifecycleAccountingTests(unittest.TestCase):
    def fixture(self, root, status='terminated'):
        (root/'resident-delivery').mkdir()
        (root/'state.json').write_text(json.dumps({'status':status,'run_id':'fixture','pod_id':'fixture',
                                                   'verified_absent_at':7200}))
        allocation={'id':'fixture','name':'fixture','status':'RUNNING','startedAt':'1970-01-01T00:00:00Z',
                    'cost':2,'dataCenterId':'test','gpu':{},'ssh':{'private':'must not be exported'}}
        (root/'allocation-observation.json').write_text(json.dumps(allocation))
        events=[{'event':'window_started','epoch':600,'worker_elapsed_seconds':0},
                {'event':'window_finished','epoch':4200,'worker_elapsed_seconds':3600}]
        for index in range(6):
            events.extend([{'event':'request_started','request_id':str(index),'seed':index,
                            'worker_elapsed_seconds':index*600},
                           {'event':'artifact_ready','request_id':str(index),'processing_seconds':30,
                            'runtime':{'worker_pid':1,'transformer_calls':[0]*11,'resident_total_build_count':1}}])
        (root/'resident-delivery/events.jsonl').write_text('\n'.join(map(json.dumps,events))+'\n')
        return {'compute_hourly_usd':'2'}, {'gpu_plus_disk_hourly_usd':'2.5',
                  'requested_successful_output_seconds':30,'queue_seconds':3600}

    def test_full_lease_includes_preparation_and_export(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);plan,queue=self.fixture(root)
            lifecycle,variation=summarize(root,plan,queue)
        self.assertEqual(Decimal(lifecycle['full_lease_gpu_plus_disk_usd_estimate']),Decimal('5'))
        self.assertEqual(lifecycle['before_measured_queue_seconds'],600)
        self.assertEqual(lifecycle['after_measured_queue_seconds'],3000)
        self.assertIsNone(lifecycle['provider_actual_charge_usd'])
        self.assertNotIn('ssh',lifecycle['provider_allocation_observation'])
        self.assertEqual(variation['observed_distinct_primary_seeds'],6)
        self.assertEqual(variation['first_to_last_bin_mean_change_percent'],0)

    def test_running_lease_cannot_be_reported_as_final(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);plan,queue=self.fixture(root,status='created')
            with self.assertRaises(ValueError):summarize(root,plan,queue)


if __name__=='__main__':unittest.main()
