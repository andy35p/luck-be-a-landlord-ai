"""Four frozen training-seed learner episodes with separate teacher labels."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import torch
from luck_agent.agents.magpie_corpus_agent import MagpieCorpusAgent
from luck_agent.agents.rent_forecast_agent import RentForecastAgent
from luck_agent.env.game_env import GameEnv,EnvConfig
from luck_agent.evaluation.trajectory import TrajectoryWriter,replay
from luck_agent.evaluation.dataset import read_episodes
from luck_agent.evaluation.magpie_dataset import POLICY


def main():
    torch.set_num_threads(1)
    source=Path('logs/v128-magpie-shards/manifest.json');raw=source.read_bytes();manifest=json.loads(raw)
    seeds=sorted(manifest['spec']['seeds']['train'])[:4]
    excluded=set(manifest['spec']['seeds']['validation']+manifest['spec']['seeds']['test'])
    if set(seeds)&excluded:raise ValueError('Training partition leak')
    checkpoint=Path('outputs/v130-magpie-corpus-training/research-200-updates.pt')
    digest=hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    if digest!='e6bcd874deb2650628810d6cb4afff443cc08db2436608442c60a21e5ab9c64e':raise ValueError('Learner changed')
    out=Path('logs/v133-magpie-corrections');out.mkdir(parents=True,exist_ok=False)
    spec={'seeds':seeds,'split':'train','checkpoint_sha256':digest,'source_manifest_sha256':hashlib.sha256(raw).hexdigest(),
          'teacher':'forecast_rents','teacher_config':POLICY,'executed_action_field':'action','supervision_field':'teacher_action','training_updates':0}
    (out/'protocol.json').write_text(json.dumps(spec,indent=2))
    learner=MagpieCorpusAgent(checkpoint,directory=source.parent,rule_version='instance-magpie-v1')
    env=GameEnv(EnvConfig(floor=1,rule_version='instance-magpie-v1'));teacher=RentForecastAgent(env.catalog)
    entries=[];counts=Counter();errors=Counter()
    for seed in seeds:
        state=env.reset(seed);step=0;path=out/f'learner-{seed}.jsonl.gz'
        with TrajectoryWriter(path,env.config,'magpie_corpus_bc',policy_config=spec) as sink:
            while not(state.is_terminal or state.is_truncated):
                actions=env.legal_actions();rng=env._engine.rng.getstate()
                executed=learner.choose(state,actions);label=teacher.choose(state,actions)
                if env._engine.rng.getstate()!=rng:raise ValueError('Labeling changed live RNG')
                after,reward,terminated,truncated,info=env.step(executed)
                sink(seed,step,state,actions,executed,reward,after,terminated,truncated,info,teacher_action=label)
                if len(actions)>1:counts[state.decision_type]+=1;errors[state.decision_type]+=executed!=label
                state=after;step+=1
        if state.is_truncated:raise ValueError('Truncated annotation')
        check=replay(path)
        for header,episode in read_episodes(path):
            if any(r.get('teacher_action') not in r['legal_actions'] for r in episode):raise ValueError('Missing legal label')
        entries.append({'file':path.name,'seed':seed,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'replay':check})
        print(json.dumps({'completed_seed':seed,'transitions':step}),flush=True)
    if source.read_bytes()!=raw or hashlib.sha256(checkpoint.read_bytes()).hexdigest()!=digest:raise ValueError('Input drift')
    result={'status':'replayed_annotations','spec':spec,'entries':entries,'decisions_by_phase':dict(counts),
            'disagreements_by_phase':dict(errors),'training_updates':0}
    (out/'manifest.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
