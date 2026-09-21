import copy
from decimal import Decimal
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from summarize_sustained import analyze


def fixture():
    requests=[dict(request_id='R1',scene_id='S1',seed=1,prompt_sha256='a'*64,requested_video_seconds=5),
              dict(request_id='R2',scene_id='S2',seed=2,prompt_sha256='b'*64,requested_video_seconds=5)]
    retry=dict(requests[1],request_id='R2_retry1',retry_of='R2')
    manifest=dict(run_id='TEST',requests=requests,retry_requests=[retry])
    runtime=dict(transformer_calls=[{}]*11,resident_total_build_count=1,transformer_builds_this_request=0)
    rows=[]
    def event(kind,when,**fields):
        rows.append(dict(event=kind,sequence=len(rows),run_id='TEST',worker_elapsed_seconds=when,**fields))
    event('window_started',0)
    event('request_started',0,**requests[0])
    event('artifact_ready',1000,request_id='R1',processing_seconds=1000,runtime=runtime,artifact_sha256='c'*64)
    event('request_started',1000,**requests[1])
    event('request_failed',1600,request_id='R2',processing_seconds=600)
    event('request_started',1600,**retry)
    event('artifact_ready',3600,request_id='R2_retry1',processing_seconds=2000,runtime=runtime,artifact_sha256='d'*64)
    event('window_finished',3600,worker_window_seconds=3600,stop_reason='target_duration_reached')
    delivery=dict(controller_complete=True,window_seconds=3605,receipts=[dict(request_id=rid,decode_verified=True,
                  output_contract_pass=True,artifact_sha256=h*64) for rid,h in [('R1','c'),('R2_retry1','d')]])
    plan=dict(compute_hourly_usd='3.00',disk_gb=0,disk_monthly_usd_per_gb='0.10')
    return manifest,rows,delivery,plan


class AccountingTests(unittest.TestCase):
    def test_failed_work_costs_time_but_adds_no_output(self):
        stats,rows=analyze(*fixture())
        self.assertEqual(stats['attempted'],3)
        self.assertEqual(stats['failed'],1)
        self.assertEqual(stats['retries'],1)
        self.assertEqual(stats['requested_successful_output_seconds'],10)
        self.assertEqual(Decimal(stats['queue_cost_usd']),Decimal('3.00'))
        self.assertEqual(Decimal(stats['cost_usd_per_technically_delivered_requested_second']),Decimal('0.30'))
        self.assertIsNone(stats['quality_adjusted_unit_cost_usd'])

    def test_failed_validation_cannot_count_as_delivered_output(self):
        manifest,rows,delivery,plan=fixture();delivery['receipts'][0]['decode_verified']=False
        stats,_=analyze(manifest,rows,delivery,plan)
        self.assertEqual(stats['encoded_but_not_validated_delivery'],1)
        self.assertEqual(stats['requested_successful_output_seconds'],5)
        self.assertEqual(Decimal(stats['cost_usd_per_technically_delivered_requested_second']),Decimal('0.60'))

    def test_duplicate_submission_is_rejected(self):
        manifest,rows,delivery,plan=fixture();rows[3].update(request_id='R1')
        with self.assertRaises(ValueError):analyze(manifest,rows,delivery,plan)

    def test_changed_input_seed_is_rejected(self):
        manifest,rows,delivery,plan=fixture();rows[1]['seed']=42
        with self.assertRaises(ValueError):analyze(manifest,rows,delivery,plan)


if __name__=='__main__':unittest.main()
