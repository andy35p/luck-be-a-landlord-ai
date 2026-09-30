"""Fixed-seed research comparison; never updates live or training defaults."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import statistics
import sys

if __package__ in (None,''):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from luck_agent.env.game_env import GameEnv,EnvConfig
from luck_agent.env.rule_revision import rule_identity
from luck_agent.agents.heuristic_agent import HeuristicAgent
from luck_agent.evaluation.evaluator import evaluate


def paired_difference(before,after,key):
    if [r['seed'] for r in before] != [r['seed'] for r in after]:
        raise ValueError('Seed order mismatch')
    differences=[b[key]-a[key] for a,b in zip(before,after)]
    mean=statistics.mean(differences)
    error=1.96*statistics.stdev(differences)/(len(differences)**0.5) if len(differences)>1 else None
    return {'mean':mean,'normal_95_interval':None if error is None else [mean-error,mean+error],
            'improved':sum(d>0 for d in differences),'equal':sum(d==0 for d in differences),
            'worse':sum(d<0 for d in differences)}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--seed-start',type=int,required=True)
    parser.add_argument('--games',type=int,default=1000)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    config=EnvConfig(floor=1,rule_version='instance-magpie-v1')
    baseline=HeuristicAgent(GameEnv(config).catalog)
    decisions={'all':0,'different':0,'symbol_choices':0,'different_symbol_choices':0}
    def observe(seed,index,state,actions,action,*rest):
        different=baseline.choose(state,actions)!=action
        decisions['all']+=1;decisions['different']+=different
        if state.decision_type in ('symbol','forced_symbol'):
            decisions['symbol_choices']+=1;decisions['different_symbol_choices']+=different
    old,old_seconds=evaluate(args.games,'heuristic',args.seed_start,config)
    new,new_seconds=evaluate(args.games,'heuristic_magpie_cycle',args.seed_start,config,transition_sink=observe)
    for name,rows in [('baseline',old),('cycle',new)]:
        with (args.output/(name+'.csv')).open('w',newline='',encoding='utf-8') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    root=Path(__file__).resolve().parents[1]
    hashes={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root/'luck_agent').rglob('*.py'))}
    result={'scope':'Restricted simulator research; fixed inventory score approximation, no live promotion',
            'rule_identity':rule_identity(config.rule_version),'seed_start':args.seed_start,'games':args.games,
            'stage_difference':paired_difference(old,new,'stage'),'win_difference':paired_difference(old,new,'won'),
            'baseline':{'stage':statistics.mean(r['stage'] for r in old),'win_rate':statistics.mean(r['won'] for r in old),'truncated':sum(r['truncated'] for r in old)},
            'cycle':{'stage':statistics.mean(r['stage'] for r in new),'win_rate':statistics.mean(r['won'] for r in new),'truncated':sum(r['truncated'] for r in new)},
            'candidate_state_disagreements':decisions,'seconds':[old_seconds,new_seconds],
            'interval_method':'Normal approximation on paired per-seed differences; exploratory, not a promotion guarantee',
            'source_hashes':hashes}
    (args.output/'comparison.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='source_hashes'},indent=2))


if __name__=='__main__':main()
