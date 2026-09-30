"""Small paired throughput check; reuse existing seeds, no efficacy claims."""
import hashlib
import json
from pathlib import Path
import platform
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from luck_agent.env.game_env import EnvConfig
from luck_agent.evaluation.evaluator import evaluate_parallel


def main():
    root=Path(__file__).resolve().parents[1]
    output=root/'reports/v120_parallel_forecast.json'
    if output.exists():raise ValueError('Output already exists')
    config=EnvConfig(floor=1,rule_version='instance-magpie-v1')
    runs=[]
    # Alternate order across two disjoint blocks to limit warmup/order bias.
    for seed,order in [(6000,(1,2)),(6004,(2,1))]:
        pair={}
        for workers in order:
            start=time.perf_counter()
            rows,_=evaluate_parallel(4,'forecast_rents',seed,config,workers=workers)
            elapsed=time.perf_counter()-start
            pair[str(workers)]={'seconds':elapsed,'episodes':rows}
            print(json.dumps({'seed':seed,'workers':workers,'seconds':elapsed}),flush=True)
        if pair['1']['episodes']!=pair['2']['episodes']:raise ValueError('Parallel result drift')
        if any(r['truncated'] for r in pair['1']['episodes']):raise ValueError('Unexpected truncation')
        runs.append({'seed_start':seed,'runs':pair})
    result={'scope':'8 existing seeds twice, all episode fields identical; not a win-rate experiment',
            'timing':'outer wall clock including setup and pool lifecycle for both modes',
            'python':platform.python_version(),'runs':runs,
            'source_hashes':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root/'luck_agent').rglob('*.py'))}}
    output.write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
