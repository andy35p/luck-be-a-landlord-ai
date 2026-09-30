"""Frozen smoke model diagnostics, not policy selection or further training."""
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import torch
from luck_agent.agents.magpie_agent import MagpieModelAgent
from luck_agent.agents.magpie_model import magpie_tensors
from luck_agent.evaluation.magpie_batching import collate_magpie
from luck_agent.evaluation.magpie_dataset import load_smoke_samples
from luck_agent.evaluation.magpie_preprocessing import scale_magpie_sample
from luck_agent.env.game_env import GameEnv,EnvConfig


def main():
    torch.set_num_threads(1)
    checkpoint='outputs/v126-magpie-training-smoke/research-20-updates.pt'
    agent=MagpieModelAgent(checkpoint,directory='logs/v121-magpie-smoke',rule_version='instance-magpie-v1')
    phases={}
    for split in ('train','validation','test'):
        samples=[scale_magpie_sample(s,agent.scaler) for s in load_smoke_samples('logs/v121-magpie-smoke',split=split) if len(s['candidates'])>1]
        counts=defaultdict(lambda:{'total':0,'correct':0})
        for offset in range(0,len(samples),64):
            chunk=samples[offset:offset+64]
            with torch.no_grad():pred=agent.model(magpie_tensors(collate_magpie(chunk))).argmax(1).tolist()
            for sample,index in zip(chunk,pred):
                row=counts[sample['metadata']['decision_type']];row['total']+=1;row['correct']+=index==sample['label']
        phases[split]=dict(counts)
    outcomes=[]
    for seed in range(8000,8010):
        env=GameEnv(EnvConfig(floor=1,rule_version='instance-magpie-v1'));state=env.reset(seed);steps=0
        while not(state.is_terminal or state.is_truncated):
            actions=env.legal_actions();action=agent.choose(state,actions)
            if action not in actions:raise ValueError('Illegal model action')
            state,*_=env.step(action);steps+=1
        outcomes.append({'seed':seed,'stage':state.rent_stage,'spins':state.spin_count,'coins':state.coins,'won':state.won,'truncated':state.is_truncated,'decisions':steps})
    result={'scope':'10 new diagnostic seeds, no teacher comparison or tuning','phase_counts':phases,
        'outcomes':outcomes,'checkpoint_sha256':hashlib.sha256(Path(checkpoint).read_bytes()).hexdigest()}
    path=Path('reports/v127_magpie_model_diagnosis.json')
    with path.open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
