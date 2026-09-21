import copy
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from sustained_queue import run_queue, validate_sustained


class Clock:
    def __init__(self): self.value = 1000.0
    def __call__(self): return self.value


class Journal:
    def __init__(self): self.rows = []
    def write(self, event, **fields): self.rows.append(dict(event=event, **fields))


def manifest():
    prompt = 'A person opens a red umbrella.'
    requests = [dict(request_id=f'R{i:04}', scene_id=f'S{i%20:02}', source_url='https://example.org',
                     prompt=prompt, prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),
                     seed=i, requested_video_seconds=5) for i in range(500)]
    return dict(version=1, run_id='TEST', quality_contract=dict(audio_required=True, criteria_sha256='a'*64),
                profile=dict(width=1344,height=768,frames=121,fps=24,requested_video_seconds=5,audio=True),
                batch_size=1,concurrency=1,limits=dict(max_requests=500,target_queue_seconds=3600,
                shutdown_deadline_epoch=6400,admission_deadline_epoch=6070,export_reserve_seconds=240,
                request_bound_seconds=90),requests=requests,
                retry_requests=[dict(r,request_id=r['request_id']+'_retry1',retry_of=r['request_id']) for r in requests])


class QueueTests(unittest.TestCase):
    def run_case(self, behavior, seconds=28):
        clock, journal = Clock(), Journal()
        def generate(request, path):
            clock.value += seconds
            behavior(request, path)
            return {}
        with tempfile.TemporaryDirectory() as folder:
            result = run_queue(manifest(), generate, Path(folder), journal, wall=clock, monotonic=clock)
        return result,journal.rows

    def test_actual_hour_includes_whole_last_request(self):
        result, rows = self.run_case(lambda r,p:p.write_bytes(b'video'))
        self.assertEqual(result['stop_reason'],'target_duration_reached')
        self.assertEqual(result['submitted'],129)
        self.assertEqual(result['worker_window_seconds'],3612)
        self.assertEqual(result['retry_attempts'],0)

    def test_known_failure_is_timed_and_one_retry_retains_inputs(self):
        seen=[]
        def behavior(r,p):
            seen.append(r)
            if len(seen)==1: raise ValueError('known failure')
            p.write_bytes(b'video')
        result,rows=self.run_case(behavior)
        self.assertEqual(result['failed'],1)
        self.assertEqual(result['retry_attempts'],1)
        self.assertEqual(seen[1]['retry_of'],seen[0]['request_id'])
        self.assertEqual(seen[1]['seed'],seen[0]['seed'])
        self.assertEqual(result['worker_window_seconds'],3612)

    def test_uncertain_timeout_never_resubmits(self):
        def behavior(r,p): raise TimeoutError()
        result,rows=self.run_case(behavior)
        self.assertEqual(result['submitted'],1)
        self.assertEqual(result['unresolved'],1)
        self.assertEqual(result['retry_attempts'],0)

    def test_failed_retry_stops_without_looping(self):
        def behavior(r,p): raise ValueError()
        result,rows=self.run_case(behavior)
        self.assertEqual(result['submitted'],2)
        self.assertEqual(result['failed'],2)
        self.assertEqual(result['retry_attempts'],1)

    def test_empty_output_stops_without_retry(self):
        result,rows=self.run_case(lambda r,p:None)
        self.assertEqual(result['submitted'],1)
        self.assertEqual(result['stop_reason'],'fatal_or_consecutive_failures')

    def test_retry_input_change_is_rejected(self):
        plan=manifest();plan['retry_requests'][0]['seed']+=1
        with self.assertRaises(ValueError):validate_sustained(plan)


if __name__=='__main__':unittest.main()
