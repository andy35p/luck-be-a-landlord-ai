"""Small isolated teacher corpus. No optimizer or checkpoint promotion."""
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from luck_agent.env.game_env import EnvConfig
from luck_agent.env.rule_revision import rule_identity
from luck_agent.evaluation.trajectory import TrajectoryWriter,replay
from luck_agent.evaluation.dataset import read_episodes,split_for_seed
from luck_agent.evaluation.magpie_batching import MagpieCandidateEncoder,collate_magpie
from luck_agent.evaluation.evaluator import evaluate


def main():
    root=Path(__file__).resolve().parents[1];out=root/'logs/v121-magpie-smoke'
    out.mkdir(parents=True,exist_ok=False)
    salt='magpie-forecast-teacher-v1';seeds={}
    for seed in range(7000,7100):
        seeds.setdefault(split_for_seed(seed,salt),seed)
        if len(seeds)==3:break
    policy={'trials':8,'seed':20270927,'horizon':30,'ranking':['first_rent_paid','rents_paid','cash'],'future_choices':'excluded'}
    spec={'seeds':seeds,'split_salt':salt,'teacher':'forecast_rents','policy_config':policy,'training_steps':0}
    (out/'protocol.json').write_text(json.dumps(spec,indent=2))
    config=EnvConfig(floor=1,rule_version='instance-magpie-v1');encoder=MagpieCandidateEncoder()
    entries=[]
    for split,seed in seeds.items():
        path=out/(split+'.jsonl.gz')
        with TrajectoryWriter(path,config,'forecast_rents',policy_config=policy) as sink:
            rows,_=evaluate(1,'forecast_rents',seed,config,transition_sink=sink)
        if rows[0]['truncated']:raise ValueError('Truncated smoke rejected')
        checked=replay(path);count=0
        for header,episode in read_episodes(path):
            if header['rule_identity']!=rule_identity(config.rule_version) or header['policy_config']!=policy:raise ValueError('Header mismatch')
            samples=[encoder.encode(r,'forecast_rents') for r in episode]
            for offset in range(0,len(samples),64):collate_magpie(samples[offset:offset+64])
            count+=len(samples)
        entries.append({'file':path.name,'seed':seed,'split':split,'transitions':count,'replay':checked,
                        'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'outcome':rows[0]})
    vocabulary={'version':encoder.version,'symbols':encoder.symbols,'items':encoder.items,'scalar_fields':encoder.scalar_fields}
    (out/'vocabulary.json').write_text(json.dumps(vocabulary,indent=2))
    manifest={'status':'replayed_and_encoded_smoke_only','spec':spec,'rule_identity':rule_identity(config.rule_version),
              'vocabulary':vocabulary,'entries':entries,'source_hashes':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root/'luck_agent').rglob('*.py'))}}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    print(json.dumps({'seeds':seeds,'entries':entries},indent=2))


if __name__=='__main__':main()
