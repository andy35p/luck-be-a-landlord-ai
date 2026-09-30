"""Real-corpus read/scaler checks and isolated manifest corruption tests."""
import json
import math
from pathlib import Path
import shutil
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from luck_agent.evaluation.magpie_corpus import load_corpus_samples,validate_corpus
from luck_agent.evaluation.magpie_corpus_preprocessing import fit_corpus_scaler,scale_corpus_sample


def main():
    source=Path('logs/v128-magpie-shards');samples=load_corpus_samples(source,split='train')
    assert {s['metadata']['seed'] for s in samples}==set(range(9000,9032))
    assert all(s['metadata']['split']=='train' for s in samples)
    scaler=fit_corpus_scaler(source);scaled=[scale_corpus_sample(s,scaler) for s in samples]
    means=[sum(s['scalars'][i] for s in scaled)/len(scaled) for i in range(8)]
    assert max(abs(x) for x in means)<1e-10
    assert scaler['samples']==11755
    checks=[]
    for mode in ('overlap','missing','nontrain_hash'):
        with tempfile.TemporaryDirectory(prefix='magpie-corpus-') as tmp:
            target=Path(tmp)/'corpus';shutil.copytree(source,target)
            path=target/'manifest.json';m=json.loads(path.read_text())
            if mode=='overlap':m['spec']['seeds']['test'][0]=m['spec']['seeds']['train'][0]
            if mode=='missing':m['entries'].pop()
            if mode=='nontrain_hash':m['entries'][-1]['sha256']='0'*64
            path.write_text(json.dumps(m));(target/'protocol.json').write_text(json.dumps(m['spec']))
            try:load_corpus_samples(target,split='train')
            except ValueError:checks.append(mode)
            else:raise AssertionError('Bad corpus accepted')
    out=Path('outputs/v129-magpie-corpus');out.mkdir(parents=True,exist_ok=False)
    (out/'train_scaler.json').write_text(json.dumps(scaler,indent=2))
    result={'train_samples':len(samples),'train_seeds':32,'max_abs_normalized_mean':max(abs(x) for x in means),
            'corruptions_rejected':checks,'training_updates':0,'test_metrics_used':False}
    Path('reports/v129_corpus_reader_checks.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))


if __name__=='__main__':main()
