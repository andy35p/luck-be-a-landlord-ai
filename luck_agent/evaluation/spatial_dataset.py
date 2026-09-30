"""Manifest-checked reader for the spatial development corpus."""
import hashlib
import json
from pathlib import Path
from luck_agent.env.rule_revision import rule_identity
from luck_agent.evaluation.dataset import read_episodes,split_for_seed
from luck_agent.evaluation.spatial_batching import SpatialCandidateEncoder


def iter_corpus(directory, *, split, policies):
    if split not in {'train','validation','test'} or not policies or len(set(policies))!=len(policies):
        raise ValueError('Explicit split and unique policies required')
    root=Path(directory).resolve();manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    enc=SpatialCandidateEncoder();spec=manifest['spec']
    if (manifest.get('schema_version')!=1 or manifest.get('status')!='validated'
            or manifest['encoder_version']!=enc.version
            or manifest['rule_identity']!=rule_identity('instance-goldfish-v1')
            or spec['environment']['rule_version']!='instance-goldfish-v1'
            or set(policies)-set(spec['policies'])):
        raise ValueError('Incompatible spatial corpus')
    def checked(name,digest):
        path=(root/name).resolve()
        if path.parent!=root or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            raise ValueError('Corpus path or hash mismatch')
        return path
    vocab=json.loads(checked('vocabulary.json',manifest['vocabulary_sha256']).read_text())
    if (vocab['symbols']!=enc.symbols or vocab['items']!=enc.items
            or vocab['encoder_version']!=enc.version or vocab['scalar_fields']!=list(enc.scalar_fields)):
        raise ValueError('Vocabulary contract mismatch')
    if json.loads(checked('protocol.json',manifest['protocol_sha256']).read_text())!=spec:
        raise ValueError('Protocol mismatch')
    entries=json.loads(checked('index.json',manifest['index_sha256']).read_text())
    indexed={}
    for row in entries:
        key=(row['policy'],row['seed'])
        if key in indexed or row['split']!=split_for_seed(row['seed'],spec['split_salt']):
            raise ValueError('Invalid seed partition index')
        indexed[key]=row
    expected={(p,s) for p in spec['policies'] for s in range(spec['seed_start'],spec['seed_start']+spec['games_per_policy'])}
    if set(indexed)!=expected:raise ValueError('Incomplete corpus seed coverage')
    seen=set()
    for name,info in manifest['files'].items():
        path=checked(name,info['sha256'])
        if info['policy'] not in policies:continue
        for header,episode in read_episodes(path):
            key=(header['agent'],episode[0]['episode_seed']);entry=indexed.get(key)
            if (key in seen or entry is None or entry['file']!=name or entry['transitions']!=len(episode)
                    or header['agent']!=info['policy'] or header['config']!=spec['environment']
                    or header.get('policy_config',{})!={} or episode[-1]['truncated']):
                raise ValueError('Episode manifest mismatch')
            seen.add(key)
            if entry['split']==split:
                for record in episode:yield enc.encode(record,header['agent'])
    if seen!={k for k in expected if k[0] in policies}:
        raise ValueError('Missing policy episodes')
