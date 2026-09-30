"""Replay fixed diagnostic cases from V113, without policy tuning."""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from luck_agent.env.game_env import EnvConfig
from luck_agent.env.action import ActionType as T
from luck_agent.evaluation.evaluator import evaluate

root=Path(__file__).resolve().parents[1]
source=root/'logs/v113-forecast'
output=root/'reports/v114_forecast_diagnosis.json'
if output.exists(): raise ValueError('Output already exists')
manifest=json.loads((source/'comparison.json').read_text())
for name,digest in manifest['source_hashes'].items():
    path=(root/name).resolve()
    if not path.is_relative_to(root) or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
        raise ValueError('Experiment source drift: '+name)
def rows(name):
    with (source/(name+'.csv')).open() as f:
        return {int(r['seed']):r for r in csv.DictReader(f)}
old,new=rows('baseline'),rows('forecast')
if set(old)!=set(new):raise ValueError('Unpaired seeds')
# Select before replay: three deepest forecast failures; three largest losses.
late=sorted((s for s in new if not int(new[s]['won'])),key=lambda s:(-int(new[s]['stage']),s))[:3]
loss=sorted((s for s in new if int(new[s]['stage'])<int(old[s]['stage'])),
            key=lambda s:(int(new[s]['stage'])-int(old[s]['stage']),s))[:3]
cases=[]
for seed in dict.fromkeys(late+loss):
    runs={}
    for mode,expected in [('heuristic',old[seed]),('forecast',new[seed])]:
        choices=[];rents=[];final={}
        def observe(seed,index,before,actions,action,reward,after,terminated,truncated,info):
            if action.action_type in (T.PICK_SYMBOL,T.SKIP_SYMBOL):
                choices.append({'spin':before.spin_count,'stage':before.rent_stage,
                    'horizon':before.spins_until_rent,'candidates':before.candidates,
                    'action':[action.action_type.name,action.target_id],
                    'deck_size':len(before.symbols)})
            if after.rent_stage!=before.rent_stage or terminated:
                rents.append({'from_stage':before.rent_stage,'to_stage':after.rent_stage,
                    'rent':before.current_rent,'cash_after':after.coins,'income':after.last_spin_income})
            if terminated or truncated:
                final.update(coins=after.coins,rent=after.current_rent,
                    shortfall=max(0,after.current_rent-after.coins) if not after.won else 0,
                    deck=dict(Counter(s.symbol_id for s in after.symbols)),
                    recent_income=after.recent_income,items=after.items)
        actual,_=evaluate(1,mode,seed,EnvConfig(floor=1,rule_version='instance-magpie-v1'),transition_sink=observe)
        for key,value in actual[0].items():
            if abs(value-float(expected[key]))>1e-9:raise ValueError(f'Replay drift {seed} {key}')
        runs[mode]={'outcome':actual[0],'final':final,'rent_events':rents,'choices':choices}
    cases.append({'seed':seed,'selected_late':seed in late,'selected_loss':seed in loss,'runs':runs})
result={'scope':'Selected diagnostic cases; not causal or population estimates',
    'source_hashes_match':True,'all_replays_match':True,
    'all_forecast_failure_stages':dict(sorted(Counter(int(r['stage']) for r in new.values() if not int(r['won'])).items())),
    'all_baseline_failure_stages':dict(sorted(Counter(int(r['stage']) for r in old.values() if not int(r['won'])).items())),
    'cases':cases}
output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({**{k:v for k,v in result.items() if k!='cases'},'cases':[{'seed':c['seed'],
    'forecast_final':c['runs']['forecast']['final'],'stages':[c['runs'][m]['outcome']['stage'] for m in ('heuristic','forecast')]} for c in cases]},indent=2))
