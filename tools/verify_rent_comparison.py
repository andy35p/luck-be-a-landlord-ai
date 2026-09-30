"""Read-only verification of completed V117 batches and reported statistics."""
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys


def verify(directory,root):
    report=json.loads((directory/'comparison.json').read_text())
    protocol=json.loads((directory/'protocol.json').read_text())
    if report['protocol']!=protocol:raise ValueError('Protocol mismatch')
    hashes=json.loads((directory/'source_hashes.json').read_text())
    if hashes!=report['source_hashes']:raise ValueError('Source manifest mismatch')
    for name,digest in hashes.items():
        path=(root/name).resolve()
        if not path.is_relative_to(root) or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            raise ValueError('Source drift: '+name)
    records={}
    for mode in (protocol['baseline'],protocol['candidate']):
        batch_paths=[directory/f'{mode}-{offset:04}.csv' for offset in range(0,protocol['games'],protocol['batch_size'])]
        if set(directory.glob(mode+'-*.csv'))!=set(batch_paths):raise ValueError('Unexpected batches')
        rows=[]
        for path in batch_paths:
            with path.open() as f:rows.extend({k:float(v) for k,v in r.items()} for r in csv.DictReader(f))
        if [r['seed'] for r in rows]!=list(range(protocol['seed_start'],protocol['seed_start']+protocol['games'])):
            raise ValueError('Missing, duplicate or reordered seeds')
        if any(not math.isfinite(v) for r in rows for v in r.values()):raise ValueError('Nonfinite episode')
        if any(r['won'] not in (0,1) or r['truncated'] not in (0,1) for r in rows):raise ValueError('Invalid flags')
        summary={'win_rate':statistics.mean(r['won'] for r in rows),'stage':statistics.mean(r['stage'] for r in rows),'truncated':sum(r['truncated'] for r in rows)}
        if summary!=report['summary'][mode]:raise ValueError('Summary mismatch')
        records[mode]=rows
    for key,label in [('won','win_difference'),('stage','stage_difference')]:
        delta=[b[key]-a[key] for a,b in zip(records[protocol['baseline']],records[protocol['candidate']])]
        mean=statistics.mean(delta);error=1.96*statistics.stdev(delta)/math.sqrt(len(delta))
        expected={'mean':mean,'normal_95_interval':[mean-error,mean+error],
                  'improved':sum(d>0 for d in delta),'equal':sum(d==0 for d in delta),'worse':sum(d<0 for d in delta)}
        if expected!=report[label]:raise ValueError('Paired statistics mismatch')
    gate=(report['win_difference']['normal_95_interval'][0]>0 and report['stage_difference']['mean']>=0
          and all(s['truncated']==0 for s in report['summary'].values()))
    if report['research_gate_passed']!=gate:raise ValueError('Gate mismatch')
    return {'verified':True,'games_per_policy':protocol['games'],'research_gate_passed':gate}


if __name__=='__main__':
    root=Path(__file__).resolve().parents[1]
    print(json.dumps(verify(root/'logs/v117-rent-comparison-run1',root),indent=2))
