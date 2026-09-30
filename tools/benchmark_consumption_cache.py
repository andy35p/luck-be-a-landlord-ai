"""Paired timing and full transition digests, same policy and random seeds."""
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from luck_agent.evaluation.evaluator import evaluate
from luck_agent.env.game_env import EnvConfig
from luck_agent.env.instance_milk_engine import InstanceMilkEngine


def main():
    output=Path('reports/v119_cache_benchmark.json')
    if output.exists():raise ValueError('Output already exists')
    original=InstanceMilkEngine._plan_for_spin
    rows=[]
    for seed,order in [(6000,('uncached','cached')),(6001,('cached','uncached'))]:
        pair={}
        for mode in order:
            digest=hashlib.sha256()
            def sink(*transition):digest.update(repr(transition).encode('utf-8'))
            method=original if mode=='cached' else lambda self,shown:self.consumption_plan(shown)
            with patch.object(InstanceMilkEngine,'_plan_for_spin',method):
                episodes,seconds=evaluate(1,'forecast_rents',seed,EnvConfig(floor=1,rule_version='instance-magpie-v1'),transition_sink=sink)
            pair[mode]={'episode':episodes[0],'seconds':seconds,'transition_sha256':digest.hexdigest()}
        if pair['cached']['transition_sha256']!=pair['uncached']['transition_sha256']:raise ValueError('Transition mismatch')
        if pair['cached']['episode']!=pair['uncached']['episode']:raise ValueError('Episode mismatch')
        rows.append({'seed':seed,**pair})
    output.write_text(json.dumps({'same_transitions':True,'runs':rows},indent=2)+'\n')
    print(output.read_text())


if __name__=='__main__':main()
