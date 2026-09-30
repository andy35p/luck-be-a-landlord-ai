"""Leakage-guarded episode splits and data access for V148.

This module intentionally never opens the V128 manifest or a test shard.  It
uses shard digests already frozen by V147, opens only explicitly named files,
and separates training/selection access from post-lock validation access.
"""
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CORPUS=ROOT/'logs/v128-magpie-shards'
PINS=ROOT/'logs/v147-generalization/protected_hashes.json'
REGISTRY=ROOT/'logs/v147-generalization/experiment_registry.json'
TRAIN_EPISODES=tuple(range(9000,9032))
AUDIT_EPISODES=tuple(range(10000,10008))

from luck_agent.evaluation.dataset import read_episodes
from luck_agent.evaluation.magpie_batching import MagpieCandidateEncoder
from luck_agent.evaluation.preprocessing import scale_sample

def _read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def _digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def create_split_manifest(seed,selection_episode_count=8,*,name='primary-a',training_seeds=(123,456,789,24680,13579)):
    if type(seed) is not int or not 1<=selection_episode_count<len(TRAIN_EPISODES):raise ValueError('Invalid split request')
    ranked=sorted(TRAIN_EPISODES,key=lambda episode:hashlib.sha256(
        f'v148-episode-split-v1:{seed}:{episode}'.encode()).hexdigest())
    selection=sorted(ranked[:selection_episode_count]);fit=sorted(ranked[selection_episode_count:])
    pins=_read(PINS);registry=_read(REGISTRY);sources={}
    for role,episodes,prefix in (('fit',fit,'train'),('selection',selection,'train'),('audit',AUDIT_EPISODES,'validation')):
        for episode in episodes:
            rel=f'logs/v128-magpie-shards/{prefix}-{episode}.jsonl.gz'
            if rel not in pins:raise ValueError('Missing frozen shard digest: '+rel)
            sources[rel]=pins[rel]
    core={'version':'v148-derived-episode-split-v1','name':name,'seed':seed,
        'fit_episodes':fit,'selection_episodes':selection,'audit_episodes':list(AUDIT_EPISODES),
        'training_seeds':list(training_seeds),'source_manifest_sha256':registry['manifest_sha256'],
        'source_shards':sources,'test_access':'FORBIDDEN'}
    core['split_hash']=hashlib.sha256(json.dumps(core,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return core

def _path(role,episode):
    if role in ('fit','selection') and episode in TRAIN_EPISODES:return CORPUS/f'train-{episode}.jsonl.gz'
    if role=='audit' and episode in AUDIT_EPISODES:return CORPUS/f'validation-{episode}.jsonl.gz'
    raise ValueError('Refusing unregistered or test shard')

def _load_role(manifest,role):
    episodes=manifest[role+'_episodes'];encoder=MagpieCandidateEncoder();rows=[]
    for episode_id in episodes:
        path=_path(role,episode_id);rel=path.relative_to(ROOT).as_posix()
        if manifest['source_shards'].get(rel)!=_digest(path):raise ValueError('Shard digest changed: '+rel)
        loaded=list(read_episodes(path))
        if len(loaded)!=1:raise ValueError('Expected one episode per shard')
        header,records=loaded[0]
        if not records or any(r['episode_seed']!=episode_id for r in records):raise ValueError('Episode identity mismatch')
        for record in records:
            sample=encoder.encode(record,header['agent'])
            state=record['state'];sample['_coverage']={'episode':episode_id,'rent_stage':state['rent_stage'],
                'deck_size':len(state['symbols']),'candidate_count':len(record['legal_actions'])}
            rows.append(sample)
    return rows

def fit_scaler(fit_raw,manifest):
    fields=list(MagpieCandidateEncoder.scalar_fields);mean=[0.]*len(fields);m2=[0.]*len(fields);n=0
    for sample in fit_raw:
        n+=1
        for i,x in enumerate(sample['scalars']):
            if not math.isfinite(x):raise ValueError('Nonfinite FIT scalar')
            d=x-mean[i];mean[i]+=d/n;m2[i]+=d*(x-mean[i])
    if not n:raise ValueError('Empty FIT data')
    return {'version':'v148-fit-zscore-v1','encoder':MagpieCandidateEncoder.version,'split_hash':manifest['split_hash'],
        'fit_episodes':manifest['fit_episodes'],'samples':n,'fields':fields,'mean':mean,
        'scale':[math.sqrt(v/n) if v/n>1e-12 else 1. for v in m2],
        'selection_excluded':True,'audit_excluded':True,'test_excluded':True}

def _validate_scaler(scaler,manifest):
    if (scaler.get('version')!='v148-fit-zscore-v1' or scaler.get('encoder')!=MagpieCandidateEncoder.version
            or scaler.get('split_hash')!=manifest['split_hash'] or scaler.get('fit_episodes')!=manifest['fit_episodes']
            or not scaler.get('selection_excluded') or not scaler.get('audit_excluded') or not scaler.get('test_excluded')):
        raise ValueError('FIT scaler provenance mismatch')

def _decisions(rows,scaler):return [scale_sample(s,scaler) for s in rows if len(s['candidates'])>1]

def load_split_data(manifest,mode='train',*,scaler=None,lock_path=None):
    if manifest.get('test_access')!='FORBIDDEN':raise ValueError('Invalid test guard')
    if mode=='train':
        fit_raw=_load_role(manifest,'fit');selection_raw=_load_role(manifest,'selection')
        derived=fit_scaler(fit_raw,manifest)
        return {'fit_raw':fit_raw,'selection_raw':selection_raw,'fit':_decisions(fit_raw,derived),
            'selection':_decisions(selection_raw,derived),'scaler':derived}
    if mode!='audit' or scaler is None or lock_path is None:raise ValueError('Audit requires FIT scaler and choice lock')
    _validate_scaler(scaler,manifest);lock=_read(lock_path);record=lock.get('splits',{}).get(manifest['name'],{})
    if record.get('split_hash')!=manifest['split_hash'] or set(record.get('choices',{}))!=set(map(str,manifest['training_seeds'])):
        raise ValueError('Checkpoint choices not locked for this split')
    audit_raw=_load_role(manifest,'audit')
    return {'audit_raw':audit_raw,'audit':_decisions(audit_raw,scaler),'scaler':scaler}

def coverage(rows,*,bucket_map=None):
    bucket_map=bucket_map or {}
    decisions=Counter(s['metadata']['decision_type'] for s in rows);symbol=[s for s in rows if s['metadata']['decision_type']=='symbol']
    def label(s):
        a=s['metadata']['actions'][s['label']]
        return 'SKIP' if a['action_type'] in (1,3,8) else 'REROLL' if a['action_type']==5 else str(a['target_id'])
    def candidate(a):return 'SKIP' if a['action_type'] in (1,3,8) else 'REROLL' if a['action_type']==5 else str(a['target_id'])
    hist=lambda values:dict(sorted(Counter(values).items(),key=lambda x:str(x[0])))
    return {'samples':len(rows),'episodes':sorted({s['_coverage']['episode'] for s in rows}),
        'decision_counts':dict(decisions),'symbol_decisions':len(symbol),'symbol_target_frequency':hist(label(s) for s in symbol),
        'symbol_candidate_frequency':hist(candidate(a) for s in symbol for a in s['metadata']['actions']),
        'frequency_buckets':hist(bucket_map.get(label(s),'unseen') for s in symbol),
        'rent_stage':hist(s['_coverage']['rent_stage'] for s in rows),
        'deck_size':hist(s['_coverage']['deck_size'] for s in rows),
        'candidate_count':hist(s['_coverage']['candidate_count'] for s in rows)}
