"""Frozen BC error rates by synergy count, score margin and deck threshold."""
from collections import Counter,defaultdict
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import torch
from diagnose_spatial_bc import classify
from luck_agent.agents.spatial_model import load_spatial_checkpoint,SpatialTorchScorer
from luck_agent.agents.heuristic_agent import HeuristicAgent
from luck_agent.env.game_env import GameEnv,EnvConfig
from luck_agent.evaluation.dataset import read_episodes,split_for_seed
from luck_agent.evaluation.spatial_batching import SpatialCandidateEncoder
from luck_agent.evaluation.spatial_preprocessing import scale_spatial_sample


def deck_band(n):
    return '<18' if n<18 else '18-19' if n<20 else '20-24' if n<25 else '25+'


def partner_band(n):return '0' if n==0 else '1' if n==1 else '2-3' if n<4 else '4+'


def groups_for(state,expected,teacher):
    deck=Counter(s['symbol_id'] for s in state['symbols'])
    groups=[('deck',deck_band(len(state['symbols']))),
            ('stage','0-5' if state['rent_stage']<6 else '6+'),
            ('teacher_action','pick' if expected['action_type']==0 else 'skip')]
    if expected['action_type']==0 and expected['target_id'] in ('mouse','cheese'):
        target=expected['target_id'];partner='cheese' if target=='mouse' else 'mouse'
        groups.append(('synergy',target+':'+partner_band(deck[partner])))
        view=SimpleNamespace(catalog=teacher.catalog,deck=list(deck.elements()),items=state['items'],
                             coins=state['coins'],state=lambda:{'rent':state['current_rent']})
        expected_score=teacher.prior.score_symbol(view,target)
        other=[teacher.prior.score_symbol(view,c) for c in state['candidates'] if c!=target]
        margin=expected_score-max(other) if other else 0
        groups.append(('synergy_margin','tie' if abs(margin)<1e-9 else '(0,1]' if margin<=1 else '>1'))
    return groups


def main():
    torch.set_num_threads(1)
    result=json.loads(Path('logs/spatial-bc-v066/results.json').read_text());spec=result['spec']
    checkpoint=Path('logs/spatial-bc-v066/final.pt');digest=hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    if digest!=result['final_checkpoint_sha256']:raise ValueError('Frozen weights changed')
    model,scaler=load_spatial_checkpoint(checkpoint,directory=spec['dataset'],policies=['heuristic'])
    scorer=SpatialTorchScorer(model);encoder=SpatialCandidateEncoder()
    teacher=HeuristicAgent(GameEnv(EnvConfig(floor=1,rule_version='instance-goldfish-v1')).catalog)
    counts=defaultdict(lambda:defaultdict(lambda:defaultdict(Counter)))
    paths={'teacher':Path(spec['dataset'])/'heuristic.jsonl.gz',
           'own':Path('logs/spatial-diagnosis-v067/model_with_teacher.jsonl.gz')}
    for source,path in paths.items():
        for _,episode in read_episodes(path):
            partition=split_for_seed(episode[0]['episode_seed']) if source=='teacher' else 'own_development'
            for r in episode:
                if r['state']['decision_type']!='symbol' or len(r['legal_actions'])<=1:continue
                expected=r['action'] if source=='teacher' else r['teacher_action']
                if source=='own':prediction=r['action']
                else:
                    sample=scale_spatial_sample(encoder.encode_observation(r['state'],r['legal_actions']),scaler)
                    scores=scorer(encoder.features(sample));prediction=r['legal_actions'][max(range(len(scores)),key=scores.__getitem__)]
                category=classify(r['state'],expected,prediction,teacher)
                for dimension,group in groups_for(r['state'],expected,teacher):
                    bucket=counts[partition][dimension][group];bucket['decisions']+=1;bucket[category]+=1
    serial={part:{dim:{group:dict(v) for group,v in groups.items()} for dim,groups in dims.items()}
            for part,dims in counts.items()}
    if hashlib.sha256(checkpoint.read_bytes()).hexdigest()!=digest:raise ValueError('Weights mutated')
    report={'checkpoint_sha256':digest,'sources':{k:{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for k,p in paths.items()},
            'groups':serial,'training_updates':0,
            'limits':'Observed feature coverage and descriptive error rates, not causal proof or an independent holdout.'}
    with Path('reports/v068_coverage.json').open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
    for part in ('train','test','own_development'):
        print(json.dumps({part:{k:serial[part][k] for k in ('synergy','synergy_margin','deck')}},indent=2))


if __name__=='__main__':main()
