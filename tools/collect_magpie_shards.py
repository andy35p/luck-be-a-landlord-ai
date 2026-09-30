"""Fixed disjoint seed shards; manifest appears only after every replay passes."""
from concurrent.futures import ProcessPoolExecutor
from collections import Counter
from dataclasses import asdict
import hashlib
import json
import multiprocessing
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from luck_agent.env.game_env import EnvConfig
from luck_agent.env.rule_revision import rule_identity
from luck_agent.evaluation.trajectory import TrajectoryWriter,replay
from luck_agent.evaluation.dataset import read_episodes
from luck_agent.evaluation.magpie_batching import MagpieCandidateEncoder,collate_magpie
from luck_agent.evaluation.magpie_dataset import POLICY
from luck_agent.evaluation.evaluator import evaluate


def collect_one(task):
    out,split,seed=task;path=Path(out)/f'{split}-{seed}.jsonl.gz'
    cfg=EnvConfig(floor=1,rule_version='instance-magpie-v1')
    with TrajectoryWriter(path,cfg,'forecast_rents',policy_config=POLICY) as sink:
        rows,_=evaluate(1,'forecast_rents',seed,cfg,transition_sink=sink)
    if rows[0]['truncated']:raise ValueError('Truncated shard')
    check=replay(path);encoder=MagpieCandidateEncoder();phases=Counter()
    for header,episode in read_episodes(path):
        if header['config']!=asdict(cfg) or header['policy_config']!=POLICY:raise ValueError('Header mismatch')
        samples=[encoder.encode(r,'forecast_rents') for r in episode]
        for offset in range(0,len(samples),64):collate_magpie(samples[offset:offset+64])
        phases.update(s['metadata']['decision_type'] for s in samples if len(s['candidates'])>1)
    return {'file':path.name,'split':split,'seed':seed,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'replay':check,'decision_phases':dict(phases),'outcome':rows[0]}


def main():
    root=Path(__file__).resolve().parents[1];protocol=root/'configs/v128_magpie_corpus.json'
    spec=json.loads(protocol.read_text());all_seeds=[s for values in spec['seeds'].values() for s in values]
    if (spec['schema']!='magpie-shards-v1' or spec['rule_version']!='instance-magpie-v1'
            or spec['floor']!=1 or spec['teacher']!='forecast_rents' or spec['policy_config']!=POLICY
            or set(spec['seeds'])!={'train','validation','test'} or not all(type(s) is int for s in all_seeds)
            or len(set(all_seeds))!=len(all_seeds) or any(not v for v in spec['seeds'].values())):
        raise ValueError('Invalid frozen protocol')
    out=root/'logs/v128-magpie-shards';out.mkdir(parents=True,exist_ok=False)
    (out/'protocol.json').write_bytes(protocol.read_bytes())
    def hashes():
        paths=sorted((root/'luck_agent').rglob('*.py'))+[root/'luck_agent/legacy/catalog.json',Path(__file__),protocol]
        return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    before=hashes();(out/'source_hashes.json').write_text(json.dumps(before,indent=2))
    tasks=[(str(out),split,seed) for split,seeds in spec['seeds'].items() for seed in seeds]
    entries=[]
    with ProcessPoolExecutor(max_workers=spec['workers'],mp_context=multiprocessing.get_context('spawn')) as pool:
        for entry in pool.map(collect_one,tasks):
            if hashes()!=before:raise ValueError('Source drift during collection')
            entries.append(entry)
            with (out/'progress.jsonl').open('a') as f:f.write(json.dumps(entry)+'\n')
            print(json.dumps({'completed':len(entries),'total':len(tasks),'split':entry['split']}),flush=True)
    if {(x['split'],x['seed']) for x in entries}!={(s,k) for _,s,k in tasks}:raise ValueError('Incomplete seed coverage')
    encoder=MagpieCandidateEncoder()
    manifest={'schema':'magpie-shards-v1','status':'replayed_and_encoded','spec':spec,
              'environment':asdict(EnvConfig(floor=1,rule_version='instance-magpie-v1')),
              'rule_identity':rule_identity(spec['rule_version']),'encoder_version':encoder.version,
              'symbols':encoder.symbols,'items':encoder.items,'scalar_fields':list(encoder.scalar_fields),
              'source_hashes':before,'entries':entries,'training_updates':0}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'complete':True,'episodes':len(entries),'transitions':sum(x['replay']['transitions'] for x in entries)}),flush=True)


if __name__=='__main__':main()
