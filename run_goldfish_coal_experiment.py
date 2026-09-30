"""One fixed coal adjustment on the complete goldfish development range."""
import csv
import hashlib
import json
import multiprocessing
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from pathlib import Path
from compare_baselines import compare, load_run
from luck_agent.env.game_env import EnvConfig
from luck_agent.env.rule_revision import rule_identity
from luck_agent.evaluation.evaluator import evaluate
from luck_agent.evaluation.metrics import summarize


def main():
    spec_path=Path('configs/v059_goldfish_coal.json')
    spec=json.loads(spec_path.read_text(encoding='utf-8'))
    baseline, original=load_run(spec['baseline_run'])
    cfg=EnvConfig(**spec['environment'])
    sources=sorted(Path('luck_agent').rglob('*.py'))
    digest=hashlib.sha256(b''.join(str(p).encode()+p.read_bytes() for p in sources)).hexdigest()
    if (baseline['source_hash']!=digest or baseline['effective_env_config']!=asdict(cfg)
            or baseline['seed_start']!=spec['seed_start'] or baseline['games']!=spec['games']
            or baseline['agent']!='heuristic' or baseline.get('policy_config') is not None
            or baseline['rule_identity']!=rule_identity(cfg.rule_version)):
        raise ValueError('Frozen baseline source/config/policy mismatch')
    out=Path('logs/goldfish-coal-v059');out.mkdir(exist_ok=False)
    (out/'protocol.json').write_text(json.dumps(spec,indent=2),encoding='utf-8')
    # Capture the exact driver and protocol before any candidate outcomes.
    (out/'driver.py').write_bytes(Path(__file__).read_bytes())
    start=time.perf_counter()
    with ProcessPoolExecutor(max_workers=spec['workers'],mp_context=multiprocessing.get_context('spawn')) as pool:
        jobs=[];offset=spec['seed_start']
        size,remainder=divmod(spec['games'],spec['workers'])
        for i in range(spec['workers']):
            count=size+(i<remainder)
            jobs.append(pool.submit(evaluate,count,'heuristic',offset,cfg,
                                    coal_score_adjustment=spec['candidate_coal_adjustment']))
            offset+=count
        rows=[]
        for job in jobs:
            batch,_=job.result();rows.extend(batch)
    elapsed=time.perf_counter()-start
    if [r['seed'] for r in rows]!=[r['seed'] for r in original]:
        raise ValueError('Incomplete seed coverage')
    with (out/'episodes.csv').open('x',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    manifest={**baseline,'policy_config':{'coal_score_adjustment':spec['candidate_coal_adjustment']},
              'workers_requested':spec['workers'],'workers_effective':spec['workers'],
              'timing_scope':'pool_startup_evaluation_shutdown','training_steps':0,
              'experiment_protocol_sha256':hashlib.sha256(spec_path.read_bytes()).hexdigest()}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    (out/'summary.json').write_text(json.dumps(summarize(rows,elapsed,13),indent=2),encoding='utf-8')
    result=compare(spec['baseline_run'],out,samples=spec['bootstrap_samples'])
    result['spec']=spec
    Path('reports/v059_comparison.json').open('x',encoding='utf-8').write(json.dumps(result,indent=2))
    print(json.dumps({'paired':result['paired'],'candidate':result['summaries']['experiment']},indent=2))


if __name__=='__main__':
    main()
