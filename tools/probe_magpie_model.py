"""Interface checks only: no optimizer, loss fitting, or model promotion."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import torch
from luck_agent.agents.magpie_model import MagpieCandidateModel,magpie_tensors,save_magpie_prototype,load_magpie_prototype
from luck_agent.agents.spatial_model import spatial_tensors,load_spatial_checkpoint
from luck_agent.evaluation.magpie_dataset import load_smoke_samples
from luck_agent.evaluation.magpie_batching import collate_magpie


def main():
    torch.manual_seed(123);torch.set_num_threads(1)
    out=Path('outputs/v123-magpie-prototype');out.mkdir(parents=True,exist_ok=False)
    model=MagpieCandidateModel().eval();path=out/'untrained.pt'
    save_magpie_prototype(path,model);loaded=load_magpie_prototype(path)
    counts={};checked_padding=0
    for split in ('train','validation','test'):
        samples=load_smoke_samples('logs/v121-magpie-smoke',split=split);counts[split]=len(samples)
        for offset in range(0,len(samples),64):
            batch=collate_magpie(samples[offset:offset+64]);tensors=magpie_tensors(batch)
            with torch.no_grad():a=model(tensors);b=loaded(tensors)
            mask=tensors['candidates_mask']
            assert torch.isfinite(a[mask]).all() and torch.isneginf(a[~mask]).all()
            assert torch.equal(a,b)
            assert mask.gather(1,a.argmax(1,keepdim=True)).all()
            checked_padding+=int((~mask).sum())
        try:spatial_tensors(batch)
        except ValueError:pass
        else:raise AssertionError('Old batch interface accepted new vocabulary')
    try:load_spatial_checkpoint(path,directory='logs/v121-magpie-smoke',policies=['forecast_rents'])
    except ValueError:pass
    else:raise AssertionError('Old checkpoint loader accepted prototype')
    result={'samples':counts,'padded_candidates_checked':checked_padding,'legal_logits_finite':True,
            'reload_logits_exact':True,'old_interface_rejects':True,'optimizer_updates':0,
            'checkpoint':str(path),'purpose':'raw-scalar untrained interface probe, not a deployable policy'}
    Path('reports/v123_magpie_model_probe.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
