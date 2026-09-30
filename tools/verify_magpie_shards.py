"""Independent complete-corpus audit; reports counts, not held-out outcomes."""
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from luck_agent.env.game_env import EnvConfig
from luck_agent.env.rule_revision import rule_identity
from luck_agent.evaluation.dataset import read_episodes
from luck_agent.evaluation.magpie_dataset import POLICY
from luck_agent.evaluation.magpie_batching import MagpieCandidateEncoder


def verify(directory,source_root):
    root=Path(directory).resolve();manifest=json.loads((root/'manifest.json').read_text())
    spec=json.loads((root/'protocol.json').read_text());enc=MagpieCandidateEncoder()
    config=asdict(EnvConfig(floor=1,rule_version='instance-magpie-v1'))
    if (manifest['schema']!='magpie-shards-v1' or manifest['status']!='replayed_and_encoded'
            or manifest['spec']!=spec or spec['policy_config']!=POLICY or spec['teacher']!='forecast_rents'
            or spec['rule_version']!='instance-magpie-v1' or spec['floor']!=1
            or manifest['environment']!=config or manifest['rule_identity']!=rule_identity(config['rule_version'])
            or manifest['encoder_version']!=enc.version or manifest['symbols']!=enc.symbols
            or manifest['items']!=enc.items or manifest['scalar_fields']!=list(enc.scalar_fields)):
        raise ValueError('Corpus contract mismatch')
    if set(spec['seeds'])!={'train','validation','test'}:raise ValueError('Invalid partitions')
    pairs=[(part,seed) for part,seeds in spec['seeds'].items() for seed in seeds]
    if any(type(s) is not int for _,s in pairs) or len({s for _,s in pairs})!=len(pairs):raise ValueError('Seed overlap')
    seen=set();names=set();counts=Counter();phases=Counter()
    for entry in manifest['entries']:
        key=entry['split'],entry['seed'];name=entry['file'];path=(root/name).resolve()
        if key in seen or key not in pairs or name in names or path.parent!=root:raise ValueError('Duplicate or escaped shard')
        seen.add(key);names.add(name)
        if hashlib.sha256(path.read_bytes()).hexdigest()!=entry['sha256']:raise ValueError('Shard hash mismatch')
        episodes=list(read_episodes(path))
        if len(episodes)!=1:raise ValueError('Expected one episode per shard')
        header,records=episodes[0]
        if (header['config']!=config or header['rule_identity']!=manifest['rule_identity']
                or header['agent']!=spec['teacher'] or header['policy_config']!=POLICY
                or records[0]['episode_seed']!=key[1] or records[-1]['truncated']
                or entry['replay']!={'episodes':1,'transitions':len(records),'exact_replay':True}):
            raise ValueError('Shard provenance mismatch')
        actual=Counter()
        for record in records:
            sample=enc.encode(record,spec['teacher'])
            if len(sample['candidates'])>1:actual[sample['metadata']['decision_type']]+=1
        if dict(actual)!=entry['decision_phases']:raise ValueError('Coverage mismatch')
        counts[key[0]]+=len(records)
        if key[0]=='train':phases.update(actual)
    if seen!=set(pairs) or {p.name for p in root.glob('*.jsonl.gz')}!=names:raise ValueError('Missing or extra shards')
    for name,digest in manifest['source_hashes'].items():
        path=(source_root/name).resolve()
        if not path.is_relative_to(source_root) or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError('Source drift')
    return {'verified':True,'episodes':len(seen),'transitions_by_split':dict(counts),'train_decisions_by_phase':dict(phases),'test_outcomes_inspected':False}


if __name__=='__main__':
    base=Path(__file__).resolve().parents[1]
    result=verify(base/'logs/v128-magpie-shards',base)
    (base/'reports/v128_shard_verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
