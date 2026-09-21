"""Render standalone figures from the public measurements."""

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

matplotlib.rcParams['svg.hashsalt'] = 'ltx-sustained-2026-09-21'


def save(fig, root, name):
    fig.savefig(root / (name + '.png'), dpi=180)
    svg = root / (name + '.svg')
    fig.savefig(svg, metadata={'Date': None})
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines()) + '\n')
    plt.close(fig)


def render(root):
    fal = json.loads((root / 'fal-attempts.json').read_text())
    rows = [r for r in fal if r['timing_clock'] == 'monotonic' and r['status'] == 'download_complete']
    fig, ax = plt.subplots(figsize=(9, 4.6))
    x = [int(r['pair_id'][1:]) for r in rows]
    ax.plot(x, [r['submit_to_completion_seconds'] for r in rows], marker='o', label='Client submit → completion observed')
    ax.plot(x, [r['submit_to_download_seconds'] for r in rows], marker='o', label='Client submit → downloaded')
    ax.axhline(15, color='#b44', linestyle='--', label='15-second reference')
    ax.set(xlabel='Preregistered pair number', ylabel='Seconds', ylim=(0, 16),
           title='fal H3 Max Turbo · five-second native-audio clips')
    ax.set_xticks([2,5,10,15,20]); ax.grid(alpha=.2); ax.legend(fontsize=8)
    fig.text(.1, .012, '19 uninterrupted observations; two-second status polling. Pair 1 excluded after a client polling error.', fontsize=8)
    fig.tight_layout(rect=(0,.045,1,1)); save(fig,root,'fal-client-latency')
    summary_path = root / 'ltx-summary.json'
    attempts_path = root / 'ltx-attempts.csv'
    if not summary_path.exists() or not attempts_path.exists():
        return
    import csv
    summary=json.loads(summary_path.read_text())
    with attempts_path.open() as f: attempts=list(csv.DictReader(f))
    fig,axes=plt.subplots(2,1,figsize=(10,7),gridspec_kw={'height_ratios':[1,1.2]})
    values=[float(r['processing_seconds']) for r in attempts if r['processing_seconds']]
    axes[0].plot(range(1,len(values)+1),values,lw=.8,marker='.',markersize=3)
    axes[0].set(xlabel='Attempt in the continuously backlogged queue',ylabel='Processing seconds',
                title='LTX · actual one-hour request sequence',ylim=(0,max(values)*1.2));axes[0].grid(alpha=.2)
    scenes=summary['per_scene']; labels=list(scenes)
    means=[scenes[k]['processing_seconds'].get('mean',0) for k in labels]
    axes[1].bar(range(len(labels)),means,color='#3266a8');axes[1].set_xticks(range(len(labels)),[k.removeprefix('P_') for k in labels],rotation=60,ha='right',fontsize=8)
    axes[1].set(ylabel='Mean processing seconds',title='Variation across the twenty fixed scenes');axes[1].grid(axis='y',alpha=.2)
    fig.tight_layout();save(fig,root,'ltx-hour-variation')
    fs=json.loads((root/'fal-summary.json').read_text())
    ltx=float(summary['cost_usd_per_technically_delivered_requested_second'])
    fal_cost=float(fs['provider_reported_cost_usd'])/(fs['downloaded']*5)
    fig,ax=plt.subplots(figsize=(7,4.5));bars=ax.bar(['Self-hosted LTX\nGPU + disk, measured queue','fal H3 Max Turbo\nprovider-reported units'],[ltx,fal_cost],color=['#3266a8','#c87621'])
    for bar,value in zip(bars,[ltx,fal_cost]):ax.text(bar.get_x()+bar.get_width()/2,value,f'${value:.5f}',ha='center',va='bottom')
    ax.set(ylabel='USD / requested output second',title='Different models · technical delivery cost',ylim=(0,max(ltx,fal_cost)*1.3));ax.grid(axis='y',alpha=.2)
    fig.text(.08,.012,'No quality parity established. LTX excludes service overhead; fal price is promotional through Sep 30.',fontsize=8)
    fig.tight_layout(rect=(0,.06,1,1));save(fig,root,'cross-model-cost')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('results',type=Path)
    render(parser.parse_args().results)
