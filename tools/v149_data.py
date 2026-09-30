"""V149 train/validation reader that cannot address a test shard or V128 manifest."""
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CORPUS=ROOT/'logs/v128-magpie-shards'
PINS=ROOT/'logs/v148-checkpoint-selection/protected_hashes.json'
V147_REGISTRY=ROOT/'logs/v147-generalization/experiment_registry.json'
TRAIN_EPISODES=tuple(range(9000,9032))
VALIDATION_EPISODES=tuple(range(10000,10008))

from luck_agent.evaluation.dataset import read_episodes
from luck_agent.evaluation.magpie_batching import MagpieCandidateEncoder
from luck_agent.evaluation.magpie_corpus_preprocessing import scale_corpus_sample

def _read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def _digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def _path(split,episode):
    allowed=TRAIN_EPISODES if split=='train' else VALIDATION_EPISODES if split=='validation' else ()
    if episode not in allowed:raise ValueError('Refusing unregistered or test shard')
    return CORPUS/f'{split}-{episode}.jsonl.gz'

def _load(split):
    episodes=TRAIN_EPISODES if split=='train' else VALIDATION_EPISODES if split=='validation' else ()
    if not episodes:raise ValueError('Only train and development validation are available')
    pins=_read(PINS);encoder=MagpieCandidateEncoder();rows=[];opened=[]
    for episode in episodes:
        path=_path(split,episode);rel=path.relative_to(ROOT).as_posix()
        if pins.get(rel)!=_digest(path):raise ValueError('Frozen shard changed: '+rel)
        opened.append(path.name);loaded=list(read_episodes(path))
        if len(loaded)!=1:raise ValueError('Expected one episode per shard')
        header,records=loaded[0]
        if not records or any(r['episode_seed']!=episode for r in records):raise ValueError('Episode identity mismatch')
        for record in records:
            sample=encoder.encode(record,header['agent'])
            if sample['metadata'].get('seed')!=episode:raise ValueError('Encoded identity mismatch')
            rows.append(sample)
    return rows,opened

def fit_full_train_scaler(rows):
    fields=list(MagpieCandidateEncoder.scalar_fields);mean=[0.]*len(fields);m2=[0.]*len(fields);n=0
    for sample in rows:
        n+=1
        for i,x in enumerate(sample['scalars']):
            if not math.isfinite(x):raise ValueError('Nonfinite train scalar')
            delta=x-mean[i];mean[i]+=delta/n;m2[i]+=delta*(x-mean[i])
    manifest_hash=_read(V147_REGISTRY)['manifest_sha256']
    return {'version':'magpie-corpus-zscore-v1','encoder':MagpieCandidateEncoder.version,
        'manifest_sha256':manifest_hash,'fit_split':'train','samples':n,'fields':fields,'mean':mean,
        'scale':[math.sqrt(v/n) if v/n>1e-12 else 1. for v in m2]}

def load_v149_data():
    train_raw,train_opened=_load('train');validation_raw,validation_opened=_load('validation')
    scaler=fit_full_train_scaler(train_raw)
    decisions=lambda rows:[scale_corpus_sample(x,scaler) for x in rows if len(x['candidates'])>1]
    return {'train_raw':train_raw,'validation_raw':validation_raw,'train':decisions(train_raw),
        'validation':decisions(validation_raw),'scaler':scaler,
        'opened':train_opened+validation_opened,'test_opened':False,'manifest_opened':False}
