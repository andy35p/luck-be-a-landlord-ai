"""Selected-case replay diagnosis, never a causal claim or policy tuner."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys

if __package__ in (None,''):sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from luck_agent.env.game_env import EnvConfig
from luck_agent.env.action import ActionType
from luck_agent.agents.magpie_cycle_agent import fresh_magpie_score
from luck_agent.evaluation.evaluator import evaluate


def read_rows(path):
    with path.open(encoding='utf-8') as stream:
        return {int(r['seed']):r for r in csv.DictReader(stream)}


def replay_case(seed,mode,expected):
    steps=[];magpies={}
    def collect(seed,index,before,actions,action,reward,after,terminated,truncated,info):
        old={s.instance_id:s for s in before.symbols}
        new={s.instance_id:s for s in after.symbols}
        steps.append({'index':index,'spin':before.spin_count,'coins':before.coins,
                      'rent':before.current_rent,'spins_until_rent':before.spins_until_rent,
                      'phase':before.decision_type,'candidates':list(before.candidates),
                      'action':[action.action_type.name,action.target_id],
                      'magpie_score':fresh_magpie_score(before.spins_until_rent,len(before.symbols))})
        for uid,s in new.items():
            if s.symbol_id=='magpie' and uid not in old:
                magpies[uid]={'acquired_spin':before.spin_count,'acquired_decision':index,
                             'appearances':0,'symbol_payout':0.0,'cycle_resets':0,'removed':False}
        for event in info['instance_events']:
            uid=event.get('instance_id')
            if uid not in magpies:continue
            if event['type']=='payout':
                magpies[uid]['appearances']+=1;magpies[uid]['symbol_payout']+=event['amount']
            if event['type']=='cycle_reset':magpies[uid]['cycle_resets']+=1
        if action.action_type==ActionType.REMOVE_SYMBOL and action.target_id in magpies:
            magpies[action.target_id].update(removed=True,removed_spin=before.spin_count,
                                            remaining_at_removal=old[action.target_id].remaining_appearances)
    rows,_=evaluate(1,mode,seed,EnvConfig(floor=1,rule_version='instance-magpie-v1'),transition_sink=collect)
    actual=rows[0]
    for key in ('stage','spins','coins','reward','decisions','won','truncated'):
        if abs(actual[key]-float(expected[key]))>1e-9:raise ValueError(f'Replay drift seed={seed} key={key}')
    return actual,steps,magpies


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if args.output.exists():raise ValueError('Output already exists')
    manifest=json.loads((args.input/'comparison.json').read_text(encoding='utf-8'))
    root=Path(__file__).resolve().parents[1]
    if manifest.get('rule_identity') != {'rule_version':'instance-magpie-v1','revision':1}:
        raise ValueError('Unexpected experiment rule identity')
    for name,digest in manifest['source_hashes'].items():
        source=(root/name).resolve()
        if not source.is_relative_to(root) or hashlib.sha256(source.read_bytes()).hexdigest()!=digest:
            raise ValueError(f'Experiment source drift: {name}')
    baseline=read_rows(args.input/'baseline.csv');cycle=read_rows(args.input/'cycle.csv')
    if set(baseline)!=set(cycle):raise ValueError('Unpaired seed sets')
    delta=lambda seed:int(cycle[seed]['stage'])-int(baseline[seed]['stage'])
    worst=sorted((s for s in baseline if delta(s)<0),key=lambda s:(delta(s),s))[:3]
    best=sorted((s for s in baseline if delta(s)>0),key=lambda s:(-delta(s),s))[:3]
    cases=[]
    for seed in worst+best:
        old,old_steps,old_magpies=replay_case(seed,'heuristic',baseline[seed])
        new,new_steps,new_magpies=replay_case(seed,'heuristic_magpie_cycle',cycle[seed])
        first=next(((a,b) for a,b in zip(old_steps,new_steps) if a['action']!=b['action']),None)
        if first is None:raise ValueError('Outcome changed without an observed action divergence')
        a,b=first
        comparable=('index','spin','coins','rent','spins_until_rent','phase','candidates')
        if any(a[k]!=b[k] for k in comparable):raise ValueError('First divergence context mismatch')
        cases.append({'seed':seed,'selection':'worst' if seed in worst else 'best','stage_delta':delta(seed),
                      'baseline':old,'cycle':new,'first_divergence':{'baseline':a,'cycle':b},
                      'baseline_magpies':old_magpies,'cycle_magpies':new_magpies})
    result={'scope':'Three worst and three best stage deltas, selected after holdout. Diagnostic only; no tuning or new test set.',
            'source_hashes_match_experiment':True,'replay_matches_saved_outcomes':True,'cases':cases}
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps([{'seed':c['seed'],'stage_delta':c['stage_delta'],
                      'first_actions':[c['first_divergence'][k]['action'] for k in ('baseline','cycle')],
                      'magpies':list(c['cycle_magpies'].values())} for c in cases],indent=2))


if __name__=='__main__':main()
