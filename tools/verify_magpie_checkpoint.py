"""Zero-update round trip and deliberate mismatch checks."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import torch
from luck_agent.agents.magpie_model import MagpieCandidateModel,magpie_tensors
from luck_agent.agents.magpie_checkpoint import save_magpie_checkpoint,load_magpie_checkpoint
from luck_agent.evaluation.magpie_batching import collate_magpie
from luck_agent.evaluation.magpie_dataset import load_smoke_samples
from luck_agent.evaluation.magpie_preprocessing import fit_magpie_scaler,scale_magpie_sample


def main():
    torch.manual_seed(123);torch.set_num_threads(1)
    directory='logs/v121-magpie-smoke';scaler=fit_magpie_scaler(directory)
    model=MagpieCandidateModel().eval();out=Path('outputs/v125-magpie-checkpoint');out.mkdir(parents=True,exist_ok=False)
    path=out/'research-zero-updates.pt'
    save_magpie_checkpoint(path,model,scaler,directory=directory,training_updates=0)
    loaded,reloaded_scaler,updates=load_magpie_checkpoint(path,directory=directory)
    assert updates==0 and scaler==reloaded_scaler
    samples=load_smoke_samples(directory,split='train');checked=0
    for offset in range(0,len(samples),64):
        batch=magpie_tensors(collate_magpie([scale_magpie_sample(s,scaler) for s in samples[offset:offset+64]]))
        with torch.no_grad():assert torch.equal(model(batch),loaded(batch))
        checked+=len(batch['scalars'])
    payload=torch.load(path,weights_only=True);rejected=[]
    def wrong_rule(p):p['rule_identity']['revision']=999
    def wrong_teacher(p):p['teacher_config']['horizon']=29
    def wrong_vocab(p):p['symbols']['magpie']=999
    def wrong_stats(p):p['scaler']['mean'][0]+=1
    def wrong_data(p):p['scaler']['manifest_sha256']='0'*64
    def nonfinite(p):next(iter(p['state_dict'].values())).view(-1)[0]=float('nan')
    with tempfile.TemporaryDirectory(prefix='magpie-checkpoint-') as tmp:
        for mutate in (wrong_rule,wrong_teacher,wrong_vocab,wrong_stats,wrong_data,nonfinite):
            bad=deepcopy(payload);mutate(bad);bad_path=Path(tmp)/(mutate.__name__+'.pt');torch.save(bad,bad_path)
            try:load_magpie_checkpoint(bad_path,directory=directory)
            except ValueError:rejected.append(mutate.__name__)
            else:raise AssertionError('Accepted mismatch')
    try:load_magpie_checkpoint('outputs/v123-magpie-prototype/untrained.pt',directory=directory)
    except ValueError:rejected.append('raw_prototype')
    else:raise AssertionError('Accepted raw probe')
    result={'roundtrip_samples':checked,'logits_exact':True,'training_updates':0,'rejections':rejected}
    Path('reports/v125_checkpoint_checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
