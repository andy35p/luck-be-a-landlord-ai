"""Frozen spatial BC audit on teacher traces and the model's own states."""
from collections import Counter,defaultdict
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import torch
from luck_agent.agents.spatial_model import load_spatial_checkpoint,SpatialTorchScorer
from luck_agent.agents.spatial_agent import SpatialCandidateAgent
from luck_agent.agents.heuristic_agent import HeuristicAgent
from luck_agent.env.game_env import GameEnv,EnvConfig
from luck_agent.evaluation.dataset import read_episodes,split_for_seed
from luck_agent.evaluation.spatial_batching import SpatialCandidateEncoder
from luck_agent.evaluation.spatial_preprocessing import scale_spatial_sample
from luck_agent.evaluation.trajectory import TrajectoryWriter,normalized,replay


def classify(state,expected,predicted,teacher):
    if expected==predicted:return 'exact'
    a,b=expected['action_type'],predicted['action_type']
    if a==b==0:
        view=SimpleNamespace(catalog=teacher.catalog,deck=[s['symbol_id'] for s in state['symbols']],
                             coins=state['coins'],items=state['items'],state=lambda:{'rent':state['current_rent']})
        gap=teacher.prior.score_symbol(view,expected['target_id'])-teacher.prior.score_symbol(view,predicted['target_id'])
        return 'equal_teacher_score' if abs(gap)<1e-9 else 'lower_teacher_score' if gap>0 else 'higher_teacher_score'
    if a==0 and b==1:return 'model_skips_teacher_pick'
    if a==1 and b==0:return 'model_picks_teacher_skip'
    if a==4 and b==8:return 'model_misses_removal'
    if a==8 and b==4:return 'model_adds_removal'
    if a==b==4:return 'different_removal_target'
    if a==b==2:return 'different_item'
    return 'other'


class Audit:
    def __init__(self):self.phase=defaultdict(Counter);self.stage=defaultdict(Counter);self.examples=[]
    def add(self,state,expected,predicted,teacher,seed,step):
        category=classify(state,expected,predicted,teacher)
        self.phase[state['decision_type']][category]+=1
        self.stage[str(state['rent_stage'])][category]+=1
        if category!='exact' and len(self.examples)<30:
            self.examples.append({'seed':seed,'step':step,'phase':state['decision_type'],
                'stage':state['rent_stage'],'deck_size':len(state['symbols']),'category':category,
                'teacher':expected,'model':predicted})
    def result(self):
        return {'by_phase':{k:dict(v) for k,v in self.phase.items()},
                'by_stage':{k:dict(v) for k,v in self.stage.items()},'first_30_disagreements':self.examples}


def main():
    torch.set_num_threads(1)
    run=Path('logs/spatial-bc-v066');results=json.loads((run/'results.json').read_text());spec=results['spec']
    checkpoint=run/'final.pt';digest=hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    if digest!=results['final_checkpoint_sha256']:raise ValueError('Frozen checkpoint changed')
    model,scaler=load_spatial_checkpoint(checkpoint,directory=spec['dataset'],policies=spec['policies'])
    scorer=SpatialTorchScorer(model);encoder=SpatialCandidateEncoder();cfg=EnvConfig(floor=1,rule_version='instance-goldfish-v1')
    teacher=HeuristicAgent(GameEnv(cfg).catalog)
    offline=Audit();online=Audit()
    for _,episode in read_episodes(Path(spec['dataset'])/'heuristic.jsonl.gz'):
        if split_for_seed(episode[0]['episode_seed'])!='test':continue
        for r in episode:
            if len(r['legal_actions'])<=1:continue
            sample=scale_spatial_sample(encoder.encode(r,'heuristic'),scaler)
            scores=scorer(encoder.features(sample));prediction=r['legal_actions'][max(range(len(scores)),key=scores.__getitem__)]
            offline.add(r['state'],r['action'],prediction,teacher,r['episode_seed'],r['step'])
    agent=SpatialCandidateAgent(scorer,rule_version=cfg.rule_version,scaler=scaler,directory=spec['dataset'],policies=spec['policies'])
    out=Path('logs/spatial-diagnosis-v067');out.mkdir(exist_ok=False);path=out/'model_with_teacher.jsonl.gz'
    expected_rows={r['seed']:r for r in results['online_rows']['trained']};rows=[]
    with TrajectoryWriter(path,cfg,'spatial_bc_v066',policy_config={'checkpoint_sha256':digest,'teacher':'heuristic'}) as writer:
        for seed,expected in expected_rows.items():
            env=GameEnv(cfg);state=env.reset(seed);step=0;total=0
            while not(state.is_terminal or state.is_truncated):
                actions=env.legal_actions();chosen=agent.choose(state,actions);label=teacher.choose(state,actions)
                if len(actions)>1:online.add(normalized(state),normalized(label),normalized(chosen),teacher,seed,step)
                after,reward,term,trunc,info=env.step(chosen)
                writer(seed,step,state,actions,chosen,reward,after,term,trunc,info,teacher_action=label)
                total+=reward;step+=1;state=after
            row={'seed':seed,'stage':state.rent_stage,'spins':state.spin_count,'coins':state.coins,
                 'won':int(state.won),'truncated':int(state.is_truncated),'reward':total,'decisions':step}
            if row!=expected:raise ValueError('Frozen online run did not reproduce')
            rows.append(row)
    check=replay(path)
    if hashlib.sha256(checkpoint.read_bytes()).hexdigest()!=digest:raise ValueError('Weights mutated')
    report={'checkpoint_sha256':digest,'offline_test':offline.result(),'online_own_states':online.result(),
            'replay':check,'online_rows_exact':True,'trajectory':str(path),
            'trajectory_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'training_updates':0,
            'limits':'Heuristic scores are preferences, not action values; own-state labels are diagnostic development data, not automatically training data.'}
    with Path('reports/v067_spatial_diagnosis.json').open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
    print(json.dumps({'offline':report['offline_test']['by_phase'],'online':report['online_own_states']['by_phase'],'replay':check},indent=2))


if __name__=='__main__':main()
