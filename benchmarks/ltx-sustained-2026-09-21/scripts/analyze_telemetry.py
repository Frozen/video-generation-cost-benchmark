"""Summarize measured-window nvidia-smi samples, preserving the original CSV."""

import argparse
import csv
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import statistics


def summarize(path, events):
    starts=[e for e in events if e['event']=='window_started']
    ends=[e for e in events if e['event']=='window_finished']
    if len(starts)!=1 or len(ends)!=1:
        raise ValueError('A closed measured window is required')
    start,end=starts[0]['epoch'],ends[0]['epoch']
    raw=path.read_text();incomplete_final_record=int(not raw.endswith('\n'))
    if incomplete_final_record:raw=raw[:raw.rfind('\n')+1]
    measured=[]
    for original in csv.DictReader(io.StringIO(raw)):
        row={k.strip():v.strip() for k,v in original.items()}
        at=datetime.strptime(row['timestamp'],'%Y/%m/%d %H:%M:%S.%f').replace(tzinfo=timezone.utc).timestamp()
        if start<=at<=end:
            measured.append(dict(epoch=at,utilization=float(row['utilization.gpu [%]'].split()[0]),
                                 memory_mib=float(row['memory.used [MiB]'].split()[0]),
                                 power_watts=float(row['power.draw [W]'].split()[0])))
    if not measured:raise ValueError('No measured-window samples')
    summary={'timestamp_zone':'UTC, verified on the measured container','samples':len(measured),
             'incomplete_final_csv_record_excluded':incomplete_final_record,
             'first_sample_epoch':measured[0]['epoch'],'last_sample_epoch':measured[-1]['epoch'],
             'interpretation':'nvidia-smi one-second samples; continuously backlogged queue does not imply 100% GPU utilization'}
    for key in ('utilization','memory_mib','power_watts'):
        values=[r[key] for r in measured]
        summary[key]={'mean':statistics.mean(values),'min':min(values),'max':max(values)}
    gaps=[b['epoch']-a['epoch'] for a,b in zip(measured,measured[1:])]
    summary['sampling_gap_seconds']={'mean':statistics.mean(gaps),'max':max(gaps)} if gaps else None
    return summary,measured


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv',type=Path,required=True);parser.add_argument('--events',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();events=[json.loads(x) for x in args.events.read_text().splitlines()]
    result,rows=summarize(args.csv,events);args.output.mkdir(exist_ok=True,parents=True)
    (args.output/'gpu-telemetry-summary.json').write_text(json.dumps(result,indent=2)+'\n')
    with (args.output/'gpu-measured-samples.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
    print(json.dumps(result,indent=2))
