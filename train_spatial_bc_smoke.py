"""Fixed-budget spatial BC smoke run, with matched closed-loop evaluation."""
import hashlib
import json
import math
from pathlib import Path
from random import Random
import torch
from luck_agent.agents.spatial_model import load_spatial_checkpoint,save_spatial_checkpoint,spatial_tensors,SpatialTorchScorer
from luck_agent.agents.spatial_agent import SpatialCandidateAgent
from luck_agent.agents.candidate_model import masked_bc_loss
from luck_agent.evaluation.spatial_dataset import iter_corpus
from luck_agent.evaluation.spatial_batching import collate_spatial
from luck_agent.evaluation.spatial_preprocessing import scale_spatial_sample
from luck_agent.evaluation.evaluator import evaluate
from luck_agent.env.game_env import GameEnv,EnvConfig


def offline(model,samples,batch_size):
    model.eval();n=correct=forced=0;loss_sum=0.0
    with torch.no_grad():
        for start in range(0,len(samples),batch_size):
            batch=collate_spatial(samples[start:start+batch_size]);b=spatial_tensors(batch)
            logits=model(b);labels=torch.tensor(batch['label']);mask=b['candidates_mask']
            decisions=mask.sum(1)>1;count=int(decisions.sum());forced+=len(labels)-count
            loss=masked_bc_loss(logits,labels,mask)
            if loss is not None:loss_sum+=loss.item()*count
            correct+=int(((logits.argmax(1)==labels)&decisions).sum());n+=count
    return {'multi_candidate_decisions':n,'forced_decisions':forced,'mean_nll':loss_sum/n if n else None,
            'accuracy':correct/n if n else None}


def online(model,scaler,spec):
    model.eval();agent=SpatialCandidateAgent(SpatialTorchScorer(model),rule_version='instance-goldfish-v1',
        scaler=scaler,directory=spec['dataset'],policies=spec['policies'])
    env=GameEnv(EnvConfig(floor=1,rule_version='instance-goldfish-v1'));rows=[]
    for seed in range(spec['online_seed_start'],spec['online_seed_start']+spec['online_games']):
        state=env.reset(seed);reward_sum=0;decisions=0
        while not(state.is_terminal or state.is_truncated):
            actions=env.legal_actions();action=agent.choose(state,actions)
            if action not in actions:raise ValueError('Illegal model action')
            state,reward,*_=env.step(action);reward_sum+=reward;decisions+=1
        rows.append({'seed':seed,'stage':state.rent_stage,'spins':state.spin_count,'coins':state.coins,
                     'won':int(state.won),'truncated':int(state.is_truncated),'reward':reward_sum,'decisions':decisions})
    return rows


def main():
    spec_path=Path('configs/v066_spatial_bc.json');spec=json.loads(spec_path.read_text())
    initial=Path(spec['initial_checkpoint'])
    if hashlib.sha256(initial.read_bytes()).hexdigest()!=spec['initial_checkpoint_sha256']:
        raise ValueError('Initial weights changed')
    out=Path('logs/spatial-bc-v066');out.mkdir(exist_ok=False)
    (out/'protocol.json').write_bytes(spec_path.read_bytes());(out/'driver.py').write_bytes(Path(__file__).read_bytes())
    torch.set_num_threads(1);torch.manual_seed(spec['shuffle_seed'])
    model,scaler=load_spatial_checkpoint(initial,directory=spec['dataset'],policies=spec['policies'])
    if scaler!=json.loads(Path(spec['scaler']).read_text()):raise ValueError('Frozen scaler changed')
    source_files=sorted(Path('luck_agent').rglob('*.py'))
    (out/'provenance.json').write_text(json.dumps({'source_sha256':hashlib.sha256(b''.join(str(p).encode()+p.read_bytes() for p in source_files)).hexdigest(),
        'dataset_manifest_sha256':hashlib.sha256((Path(spec['dataset'])/'manifest.json').read_bytes()).hexdigest(),
        'scaler_sha256':hashlib.sha256(Path(spec['scaler']).read_bytes()).hexdigest()},indent=2))
    def samples(split):return [scale_spatial_sample(s,scaler) for s in iter_corpus(spec['dataset'],split=split,policies=spec['policies'])]
    train=[s for s in samples('train') if len(s['candidates'])>1];validation=samples('validation')
    if not train:raise ValueError('No training decisions')
    initial_metrics=offline(model,validation,spec['batch_size'])
    optimizer=torch.optim.Adam(model.parameters(),lr=spec['learning_rate']);history=[];updates=0
    for epoch in range(spec['epochs']):
        order=list(range(len(train)));Random(spec['shuffle_seed']+epoch).shuffle(order)
        model.train();total=0.0;count=0
        for start in range(0,len(order),spec['batch_size']):
            batch=collate_spatial([train[i] for i in order[start:start+spec['batch_size']]])
            b=spatial_tensors(batch);optimizer.zero_grad(set_to_none=True)
            loss=masked_bc_loss(model(b),torch.tensor(batch['label']),b['candidates_mask'])
            if loss is None or not torch.isfinite(loss):raise ValueError('Invalid training loss')
            loss.backward();norm=torch.nn.utils.clip_grad_norm_(model.parameters(),spec['gradient_clip'])
            if not torch.isfinite(norm):raise ValueError('Nonfinite gradient')
            optimizer.step();updates+=1;total+=loss.item()*len(batch['label']);count+=len(batch['label'])
        item={'epoch':epoch+1,'updates':updates,'train_nll':total/count,'validation':offline(model,validation,spec['batch_size'])}
        history.append(item);print(json.dumps(item),flush=True)
    path=out/'final.pt';save_spatial_checkpoint(path,model,scaler,directory=spec['dataset'],policies=spec['policies'],training_updates=updates)
    restored,_=load_spatial_checkpoint(path,directory=spec['dataset'],policies=spec['policies'])
    probe=spatial_tensors(collate_spatial(validation[:64]))
    with torch.no_grad():assert torch.equal(model(probe),restored(probe))
    test_metrics=offline(restored,samples('test'),spec['batch_size'])
    untrained,_=load_spatial_checkpoint(initial,directory=spec['dataset'],policies=spec['policies'])
    runs={'initial':online(untrained,scaler,spec),'trained':online(restored,scaler,spec)}
    runs['teacher'],_=evaluate(spec['online_games'],'heuristic',spec['online_seed_start'],EnvConfig(floor=1,rule_version='instance-goldfish-v1'))
    summary={k:{'mean_stage':sum(r['stage'] for r in rows)/len(rows),'wins':sum(r['won'] for r in rows),
                'truncated':sum(r['truncated'] for r in rows)} for k,rows in runs.items()}
    result={'spec':spec,'training_decisions':len(train),'training_updates':updates,'initial_validation':initial_metrics,
            'epochs':history,'final_test':test_metrics,'reload_exact':True,'online_summary':summary,'online_rows':runs,
            'final_checkpoint_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'default_policy_changed':False}
    (out/'results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'final_test':test_metrics,'online':summary,'updates':updates}),flush=True)


if __name__=='__main__':main()
