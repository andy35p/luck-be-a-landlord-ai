"""Frozen model rollout comparison, no fitting or holdout selection."""
import csv
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import torch
from luck_agent.agents.magpie_corpus_agent import MagpieCorpusAgent
from luck_agent.agents.magpie_model import MagpieCandidateModel
from luck_agent.env.game_env import GameEnv,EnvConfig
from luck_agent.evaluation.evaluator import evaluate_parallel
from tools.compare_forecast import paired_difference


def main():
    spec=json.loads(Path('configs/v131_model_rollout.json').read_text())
    checkpoint=Path(spec['model_checkpoint'])
    if hashlib.sha256(checkpoint.read_bytes()).hexdigest()!=spec['model_sha256']:raise ValueError('Checkpoint drift')
    out=Path('logs/v131-model-rollouts');out.mkdir(parents=True,exist_ok=False)
    (out/'protocol.json').write_text(json.dumps(spec,indent=2))
    def hashes():return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path('luck_agent').rglob('*.py'))}
    before=hashes();torch.set_num_threads(1)
    agent=MagpieCorpusAgent(checkpoint,directory='logs/v128-magpie-shards',rule_version=spec['rule_version'])
    trained=agent.model;torch.manual_seed(spec['initialization_seed']);untrained=MagpieCandidateModel().eval()
    config=EnvConfig(floor=1,rule_version=spec['rule_version']);results={};times={}
    for name,model in [('untrained',untrained),('trained',trained)]:
        agent.model=model;rows=[];start=time.perf_counter()
        for seed in range(spec['seed_start'],spec['seed_start']+spec['games']):
            env=GameEnv(config);state=env.reset(seed);steps=0
            while not(state.is_terminal or state.is_truncated):
                actions=env.legal_actions();action=agent.choose(state,actions)
                if action not in actions:raise ValueError('Illegal model action')
                state,*_=env.step(action);steps+=1
            rows.append({'seed':seed,'stage':state.rent_stage,'won':int(state.won),'truncated':int(state.is_truncated),
                         'spins':state.spin_count,'coins':state.coins,'decisions':steps})
        results[name]=rows;times[name]=time.perf_counter()-start
        (out/(name+'.json')).write_text(json.dumps(rows,indent=2));print(name+' complete',flush=True)
    teacher,elapsed=evaluate_parallel(spec['games'],spec['teacher'],spec['seed_start'],config,workers=2)
    results['teacher']=teacher;times['teacher']=elapsed
    (out/'teacher.json').write_text(json.dumps(teacher,indent=2))
    if hashes()!=before:raise ValueError('Source drift during rollout')
    report={'spec':spec,'summary':{name:{'stage':statistics.mean(r['stage'] for r in rows),
            'win_rate':statistics.mean(r['won'] for r in rows),'truncated':sum(r['truncated'] for r in rows)} for name,rows in results.items()},
            'trained_minus_untrained_stage':paired_difference(results['untrained'],results['trained'],'stage'),
            'trained_minus_teacher_stage':paired_difference(teacher,results['trained'],'stage'),'seconds':times,'source_hashes':before}
    (out/'comparison.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k!='source_hashes'},indent=2),flush=True)


if __name__=='__main__':main()
