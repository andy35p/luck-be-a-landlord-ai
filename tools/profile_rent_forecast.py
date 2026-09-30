"""Latency probe on existing V117 seeds, not a new efficacy experiment."""
import cProfile
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import pstats
import statistics
import sys
import time
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from luck_agent.agents.rent_forecast_agent import RentForecastAgent
from luck_agent.evaluation.evaluator import evaluate
from luck_agent.env.game_env import EnvConfig


def main():
    root=Path(__file__).resolve().parents[1]
    output=root/'logs/v118-latency'
    output.mkdir(parents=True,exist_ok=False)
    manifest=json.loads((root/'logs/v117-rent-comparison-run1/source_hashes.json').read_text())
    for name,digest in manifest.items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=digest:raise ValueError('Source drift')
    expected={}
    for path in (root/'logs/v117-rent-comparison-run1').glob('forecast_rents-*.csv'):
        with path.open() as f:expected.update({int(r['seed']):r for r in csv.DictReader(f)})
    timings=[]
    class TimedAgent(RentForecastAgent):
        def choose(self,state,actions):
            start=time.perf_counter_ns()
            result=super().choose(state,actions)
            timings.append({'phase':state.decision_type,'deck':len(state.symbols),'actions':len(actions),
                            'milliseconds':(time.perf_counter_ns()-start)/1e6})
            return result
    config=EnvConfig(floor=1,rule_version='instance-magpie-v1')
    with patch('luck_agent.evaluation.evaluator.RentForecastAgent',TimedAgent):
        rows,elapsed=evaluate(3,'forecast_rents',6000,config)
    for row in rows:
        for key,value in row.items():
            if value!=float(expected[row['seed']][key]):raise ValueError('Replay drift')
    def summary(values):
        values=sorted(values)
        return {'count':len(values),'mean_ms':statistics.mean(values),'p50_ms':values[math.ceil(.5*len(values))-1],
                'p95_ms':values[math.ceil(.95*len(values))-1],'p99_ms':values[math.ceil(.99*len(values))-1],'max_ms':max(values)}
    result={'seeds':[6000,6001,6002],'replay_matches_v117':True,'elapsed_seconds':elapsed,
        'percentile_method':'nearest rank','phase_latency':{phase:summary([r['milliseconds'] for r in timings if r['phase']==phase]) for phase in sorted({r['phase'] for r in timings})},
        'source_hashes':manifest}
    (output/'latency.json').write_text(json.dumps(result,indent=2))
    with (output/'decisions.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(timings[0]));w.writeheader();w.writerows(timings)
    # Separate profiled run: do not mix profiler overhead into latency samples.
    profile=cProfile.Profile();profile.enable()
    profiled,_=evaluate(1,'forecast_rents',6000,config)
    profile.disable()
    if profiled[0]!=rows[0]:raise ValueError('Profile replay drift')
    profile.dump_stats(str(output/'cpu.prof'))
    stream=io.StringIO();pstats.Stats(profile,stream=stream).strip_dirs().sort_stats('tottime').print_stats(20)
    (output/'cpu.txt').write_text(stream.getvalue())
    print(json.dumps({k:v for k,v in result.items() if k!='source_hashes'},indent=2))
    print(stream.getvalue())


if __name__=='__main__':main()
