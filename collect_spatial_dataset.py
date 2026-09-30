"""Collect a fixed development corpus and publish its manifest after validation."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from luck_agent.env.game_env import EnvConfig
from luck_agent.env.rule_revision import rule_identity
from luck_agent.evaluation.evaluator import evaluate
from luck_agent.evaluation.trajectory import TrajectoryWriter,replay
from luck_agent.evaluation.dataset import read_episodes,split_for_seed
from luck_agent.evaluation.spatial_batching import SpatialCandidateEncoder,collate_spatial


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def collect(config_path, output):
    spec=json.loads(Path(config_path).read_text(encoding='utf-8'))
    cfg=EnvConfig(**spec['environment']);enc=SpatialCandidateEncoder()
    if cfg.rule_version!='instance-goldfish-v1' or spec['policies']!=['random','heuristic']:
        raise ValueError('Fixed goldfish random/heuristic corpus required')
    if type(spec['games_per_policy']) is not int or spec['games_per_policy']<=0:
        raise ValueError('Positive game count required')
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    (out/'protocol.json').write_text(json.dumps(spec,indent=2),encoding='utf-8')
    vocabulary={'encoder_version':enc.version,'symbols':enc.symbols,'items':enc.items,
                'scalar_fields':enc.scalar_fields,
                'board_columns':['symbol_token','permanent_bonus','remaining_appearances_or_zero','has_timer','current_deck_pointer_plus_one_or_zero']}
    (out/'vocabulary.json').write_text(json.dumps(vocabulary,indent=2),encoding='utf-8')
    files={};index=[];coverage={}
    for policy in spec['policies']:
        path=out/(policy+'.jsonl.gz')
        with TrajectoryWriter(path,cfg,policy) as sink:
            rows,_=evaluate(spec['games_per_policy'],policy,spec['seed_start'],cfg,transition_sink=sink)
        if any(r['truncated'] for r in rows):raise ValueError('Truncated corpus rejected')
        (out/(policy+'_episodes.json')).write_text(json.dumps(rows,indent=2),encoding='utf-8')
        check=replay(path);counts=Counter();pending=[];observed=[]
        for header,episode in read_episodes(path):
            seed=episode[0]['episode_seed'];observed.append(seed)
            split=split_for_seed(seed,spec['split_salt'])
            index.append({'file':path.name,'policy':policy,'seed':seed,'split':split,'transitions':len(episode)})
            for record in episode:
                sample=enc.encode(record,policy)
                counts[split]+=1;counts['action_'+str(record['action']['action_type'])]+=1
                counts['multi_candidate']+=len(record['legal_actions'])>1
                pending.append(sample)
                if len(pending)==64:collate_spatial(pending);pending=[]
        if pending:collate_spatial(pending)
        if observed!=list(range(spec['seed_start'],spec['seed_start']+spec['games_per_policy'])):
            raise ValueError('Missing seed coverage')
        files[path.name]={'sha256':sha(path),'policy':policy,'replay':check}
        coverage[policy]=dict(counts)
        print(json.dumps({'policy':policy,**check,'coverage':dict(counts)}),flush=True)
    (out/'index.json').write_text(json.dumps(index,indent=2),encoding='utf-8')
    sources=sorted(Path('luck_agent').rglob('*.py'))
    manifest={'schema_version':1,'status':'validated','spec':spec,'rule_identity':rule_identity(cfg.rule_version),
              'encoder_version':enc.version,'vocabulary_sha256':sha(out/'vocabulary.json'),
              'index_sha256':sha(out/'index.json'),'protocol_sha256':sha(out/'protocol.json'),
              'collector_sha256':sha(__file__),
              'source_sha256':hashlib.sha256(b''.join(str(p).encode()+p.read_bytes() for p in sources)).hexdigest(),
              'files':files,'coverage':coverage,'training_steps':0}
    # No manifest exists until every policy has replayed and encoded successfully.
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return manifest


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',default='configs/v063_spatial_dataset.json')
    p.add_argument('--output',default='logs/spatial-dataset-v063');a=p.parse_args()
    collect(a.config,a.output)
