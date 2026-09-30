"""Teacher labels on selected learner trajectories; diagnostics only."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import torch
from luck_agent.agents.magpie_corpus_agent import MagpieCorpusAgent
from luck_agent.agents.rent_forecast_agent import RentForecastAgent
from luck_agent.env.game_env import GameEnv,EnvConfig


def main():
    root=Path(__file__).resolve().parents[1];source=root/'logs/v131-model-rollouts'
    report=json.loads((source/'comparison.json').read_text());spec=report['spec']
    for name,digest in report['source_hashes'].items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=digest:raise ValueError('Source drift')
    checkpoint=root/spec['model_checkpoint']
    if hashlib.sha256(checkpoint.read_bytes()).hexdigest()!=spec['model_sha256']:raise ValueError('Checkpoint drift')
    model_rows={r['seed']:r for r in json.loads((source/'trained.json').read_text())}
    teacher_rows={r['seed']:r for r in json.loads((source/'teacher.json').read_text())}
    selected=sorted(model_rows,key=lambda s:(model_rows[s]['stage']-teacher_rows[s]['stage'],s))[:3]
    output=root/'reports/v132_learner_state_diagnosis.json'
    if output.exists():raise ValueError('Output already exists')
    torch.set_num_threads(1)
    learner=MagpieCorpusAgent(checkpoint,directory=root/'logs/v128-magpie-shards',rule_version=spec['rule_version'])
    cases=[]
    for seed in selected:
        env=GameEnv(EnvConfig(floor=1,rule_version=spec['rule_version']));state=env.reset(seed)
        teacher=RentForecastAgent(env.catalog);steps=0;decisions=[];counts=Counter();errors=Counter()
        while not(state.is_terminal or state.is_truncated):
            actions=env.legal_actions();action=learner.choose(state,actions)
            if len(actions)>1:
                recommended=teacher.choose(state,actions);phase=state.decision_type
                counts[phase]+=1;errors[phase]+=action!=recommended
                if action!=recommended:
                    decisions.append({'step':steps,'stage':state.rent_stage,'spin':state.spin_count,
                        'coins':state.coins,'rent':state.current_rent,'remaining_spins':state.spins_until_rent,
                        'phase':phase,'candidates':state.candidates,'deck':dict(Counter(s.symbol_id for s in state.symbols)),
                        'model':[action.action_type.name,action.target_id],
                        'teacher':[recommended.action_type.name,recommended.target_id]})
            state,*_=env.step(action);steps+=1
        actual={'seed':seed,'stage':state.rent_stage,'won':int(state.won),'truncated':int(state.is_truncated),
                'spins':state.spin_count,'coins':state.coins,'decisions':steps}
        if actual!=model_rows[seed]:raise ValueError('Learner replay drift')
        cases.append({'seed':seed,'model_outcome':actual,'teacher_original_outcome':teacher_rows[seed],
            'rent_shortfall':max(0,state.current_rent-state.coins),'decisions_by_phase':dict(counts),
            'disagreements_by_phase':dict(errors),'disagreements':decisions})
        print(json.dumps({'seed':seed,'counts':dict(counts),'errors':dict(errors),'shortfall':cases[-1]['rent_shortfall']}),flush=True)
    result={'scope':'Three largest stage deficits, tie by seed; selected diagnostics, not causal or population estimate',
        'checkpoint_sha256':spec['model_sha256'],'source_hashes_verified':True,'learner_replays_exact':True,
        'teacher_labels_executed':False,'training_updates_added':0,'cases':cases}
    output.write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
