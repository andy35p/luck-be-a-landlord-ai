"""Compare completed evaluation runs with matching rules and seed ranges."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from luck_agent.evaluation.compare_reroll import paired_stats
from luck_agent.evaluation.metrics import summarize


def load_run(directory):
    directory = Path(directory)
    manifest = json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    integer_fields={'seed','episode_id','won','stage','final_stage','spins','decisions','truncated',
                    'invalid_actions','rerolls_used','removals_used'}
    float_fields={'coins','final_coins','reward','final_reward'}
    with (directory/'episodes.csv').open(newline='',encoding='utf-8') as stream:
        rows = [{k:(float(v) if k in float_fields else int(v) if k in integer_fields else v)
                 for k,v in row.items()} for row in csv.DictReader(stream)]
    expected = list(range(manifest['seed_start'],manifest['seed_start']+manifest['games']))
    if not rows or [r['seed'] for r in rows] != expected:
        raise ValueError('Missing, duplicated, reordered or unexpected seeds')
    if any(not all(math.isfinite(r[k]) for k in integer_fields|float_fields if k in r) for r in rows):
        raise ValueError('Nonfinite episode metrics')
    if any(r['won'] not in (0,1) or r['truncated'] != 0 for r in rows):
        raise ValueError('Invalid win flag or truncated evaluation')
    return manifest, rows


def compare(baseline, experiment, samples=2000):
    a, left = load_run(baseline); b, right = load_run(experiment)
    for key in ('effective_env_config','rule_identity','source_hash','effective_catalog_hash','seed_start','games'):
        if key not in a or key not in b or a[key] != b[key]:
            raise ValueError(f'Incompatible evaluation: {key}')
    stats = paired_stats(left,right,57,samples)
    stats.pop('promotable_on_development')  # A baseline audit is not a promotion gate.
    summaries = {}
    for name, rows in [('baseline',left),('experiment',right)]:
        summary=summarize(rows,1,13)
        for k in ('seconds','episodes_per_second','decisions_per_second'): summary.pop(k)
        summaries[name]=summary
    failures=[{'seed':r['seed'],'stage':r['stage'],'spins':r['spins'],'coins':r['coins']}
              for r in right if not r['won']]
    sources={}
    for name,path in [('baseline',baseline),('experiment',experiment)]:
        sources[name]={'directory':str(path),'agent':(a if name=='baseline' else b)['agent'],
                       'sha256':{f:hashlib.sha256((Path(path)/f).read_bytes()).hexdigest()
                                 for f in ('manifest.json','episodes.csv')}}
    return {'sources':sources,'rule_identity':a['rule_identity'],'paired':stats,'summaries':summaries,
            'bootstrap':{'seed':57,'samples':samples,'unit':'paired episode seed'},
            'failure_seeds':failures,'training_steps':0,
            'limitations':'Development seeds; approximate restricted simulator; no policy promotion or causal failure diagnosis.'}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--baseline',required=True)
    parser.add_argument('--experiment',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    report=compare(args.baseline,args.experiment)
    with Path(args.output).open('x',encoding='utf-8') as stream:
        json.dump(report,stream,indent=2)
    print(json.dumps({'paired':report['paired'],'summaries':report['summaries']},indent=2))


if __name__ == '__main__':
    main()
