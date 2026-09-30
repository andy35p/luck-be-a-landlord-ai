"""Fail-closed reader for the explicitly experimental three-way smoke corpus."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from luck_agent.env.game_env import EnvConfig
from luck_agent.env.rule_revision import rule_identity
from luck_agent.evaluation.dataset import read_episodes,split_for_seed
from luck_agent.evaluation.magpie_batching import MagpieCandidateEncoder

POLICY={'trials':8,'seed':20270927,'horizon':30,
        'ranking':['first_rent_paid','rents_paid','cash'],'future_choices':'excluded'}


def load_smoke_samples(directory,*,split):
    if split not in ('train','validation','test'):raise ValueError('Explicit split required')
    root=Path(directory).resolve()
    def local(name):
        path=(root/name).resolve()
        if path.parent!=root:raise ValueError('Dataset path escapes root')
        return path
    manifest=json.loads(local('manifest.json').read_text())
    spec=manifest['spec'];encoder=MagpieCandidateEncoder()
    expected_vocab={'version':encoder.version,'symbols':encoder.symbols,'items':encoder.items,
                    'scalar_fields':list(encoder.scalar_fields)}
    identity=rule_identity('instance-magpie-v1')
    if (manifest['status']!='replayed_and_encoded_smoke_only' or manifest['rule_identity']!=identity
            or spec['teacher']!='forecast_rents' or spec['policy_config']!=POLICY or spec['training_steps']!=0
            or manifest['vocabulary']!=expected_vocab):raise ValueError('Incompatible smoke contract')
    if json.loads(local('protocol.json').read_text())!=spec:raise ValueError('Protocol mismatch')
    if json.loads(local('vocabulary.json').read_text())!=expected_vocab:raise ValueError('Vocabulary mismatch')
    seeds=spec['seeds']
    if (set(seeds)!= {'train','validation','test'} or len(set(seeds.values()))!=3
            or any(type(s) is not int or split_for_seed(s,spec['split_salt'])!=part for part,s in seeds.items())):
        raise ValueError('Invalid seed partition')
    config=asdict(EnvConfig(floor=1,rule_version='instance-magpie-v1'))
    selected=[];seen=set();files=set()
    # Validate every partition before returning any sample from the requested one.
    for entry in manifest['entries']:
        part=entry['split'];name=entry['file']
        if part not in seeds or part in seen or name in files or entry['seed']!=seeds[part]:raise ValueError('Duplicate or misplaced episode')
        seen.add(part);files.add(name);path=local(name)
        if hashlib.sha256(path.read_bytes()).hexdigest()!=entry['sha256']:raise ValueError('Trajectory hash mismatch')
        episodes=list(read_episodes(path))
        if len(episodes)!=1:raise ValueError('One smoke episode per partition required')
        header,records=episodes[0]
        if (header['rule_identity']!=identity or header['config']!=config or header['agent']!=spec['teacher']
                or header['policy_config']!=POLICY or records[0]['episode_seed']!=seeds[part]
                or len(records)!=entry['transitions'] or records[-1]['truncated']):
            raise ValueError('Episode provenance mismatch')
        samples=[encoder.encode(r,spec['teacher']) for r in records]
        for sample in samples:sample['metadata'].update(split=part,trajectory_sha256=entry['sha256'],policy_config=dict(POLICY))
        if part==split:selected=samples
    if seen!=set(seeds):raise ValueError('Missing partition')
    return selected
