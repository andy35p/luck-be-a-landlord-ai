"""Frozen 200-update development experiment, never a generalization claim."""
import hashlib
import json
from pathlib import Path
from random import Random
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import torch
from luck_agent.agents.magpie_model import MagpieCandidateModel,magpie_tensors
from luck_agent.agents.magpie_corpus_checkpoint import save_corpus_checkpoint,load_corpus_checkpoint
from luck_agent.evaluation.magpie_corpus import load_corpus_samples
from luck_agent.evaluation.magpie_corpus_preprocessing import fit_corpus_scaler,scale_corpus_sample
from luck_agent.evaluation.magpie_batching import collate_magpie


def main():
    out=Path('outputs/v130-magpie-corpus-training');out.mkdir(parents=True,exist_ok=False)
    protocol={'updates':200,'batch_size':64,'learning_rate':0.001,'seed':123,'optimizer':'Adam',
              'clip_grad_norm':1.0,'decision_only':True,'model_width':16,'scope':'32 training episodes; fixed development run, test metrics sealed'}
    (out/'protocol.json').write_text(json.dumps(protocol,indent=2))
    directory='logs/v128-magpie-shards';torch.manual_seed(123);torch.set_num_threads(1)
    scaler=fit_corpus_scaler(directory)
    train=[scale_corpus_sample(s,scaler) for s in load_corpus_samples(directory,split='train') if len(s['candidates'])>1]
    model=MagpieCandidateModel().eval()
    def metrics(samples):
        total=correct=0;loss=0.
        with torch.no_grad():
            for offset in range(0,len(samples),64):
                batch=collate_magpie(samples[offset:offset+64]);logits=model(magpie_tensors(batch));labels=torch.tensor(batch['label'])
                loss+=float(torch.nn.functional.cross_entropy(logits,labels,reduction='sum'))
                correct+=int((logits.argmax(1)==labels).sum());total+=len(labels)
        return {'decisions':total,'nll':loss/total,'accuracy':correct/total}
    before=metrics(train);print('Training data validated',flush=True);optimizer=torch.optim.Adam(model.parameters(),lr=protocol['learning_rate'])
    rng=Random(123);history=[];order=[]
    for step in range(protocol['updates']):
        chosen=[]
        for _ in range(protocol['batch_size']):
            if not order:order=list(range(len(train)));rng.shuffle(order)
            chosen.append(train[order.pop()])
        batch=collate_magpie(chosen);optimizer.zero_grad();logits=model(magpie_tensors(batch))
        loss=torch.nn.functional.cross_entropy(logits,torch.tensor(batch['label']))
        if not torch.isfinite(loss):raise ValueError('Nonfinite loss')
        loss.backward()
        if any(p.grad is not None and not torch.isfinite(p.grad).all() for p in model.parameters()):raise ValueError('Nonfinite gradient')
        norm=torch.nn.utils.clip_grad_norm_(model.parameters(),1.0);optimizer.step()
        history.append({'step':step+1,'loss':float(loss.detach()),'gradient_norm_before_clip':float(norm)})
    print('200 updates complete',flush=True)
    after={'train':metrics(train)}
    after_phases={'train':{p:metrics([s for s in train if s['metadata']['decision_type']==p]) for p in sorted({s['metadata']['decision_type'] for s in train})}}
    # No early stopping or parameter selection from either engineering holdout.
    for split in ('validation',):
        samples=[scale_corpus_sample(s,scaler) for s in load_corpus_samples(directory,split=split) if len(s['candidates'])>1]
        after[split]=metrics(samples)
        after_phases[split]={p:metrics([s for s in samples if s["metadata"]["decision_type"]==p]) for p in sorted({s["metadata"]["decision_type"] for s in samples})}
    checkpoint=out/'research-200-updates.pt'
    save_corpus_checkpoint(checkpoint,model,scaler,directory=directory,training_updates=200)
    loaded,_,updates=load_corpus_checkpoint(checkpoint,directory=directory)
    for offset in range(0,len(train),64):
        tensors=magpie_tensors(collate_magpie(train[offset:offset+64]))
        with torch.no_grad():assert torch.equal(model(tensors),loaded(tensors))
    result={'protocol':protocol,'before_train':before,'after':after,'phase_metrics':after_phases,'history':history,
        'all_gradients_finite':True,'reload_logits_exact':True,'training_updates':updates,
        'checkpoint_sha256':hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        'source_hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path('luck_agent').rglob('*.py'))}}
    (out/'result.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k not in ('history','source_hashes')},indent=2))


if __name__=='__main__':main()
