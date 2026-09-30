"""Read-only source audit plus isolated corruption checks on temporary copies."""
import json
import hashlib
from pathlib import Path
import shutil
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from luck_agent.evaluation.magpie_dataset import load_smoke_samples


def main():
    source=Path('logs/v121-magpie-smoke')
    original={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir() if p.is_file()}
    counts={split:len(load_smoke_samples(source,split=split)) for split in ('train','validation','test')}
    def corrupt_hash(m):m['entries'][-1]['sha256']='0'*64
    def corrupt_teacher(m):m['spec']['policy_config']['horizon']=29
    def corrupt_rule(m):m['rule_identity']['revision']=999
    def duplicate_seed(m):m['spec']['seeds']['test']=m['spec']['seeds']['train']
    def escape_path(m):m['entries'][0]['file']='../outside.jsonl.gz'
    def omit_partition(m):m['entries'].pop()
    checks=[]
    for mutate in (corrupt_hash,corrupt_teacher,corrupt_rule,duplicate_seed,escape_path,omit_partition):
        with tempfile.TemporaryDirectory(prefix='magpie-audit-') as temporary:
            target=Path(temporary)/'corpus';shutil.copytree(source,target)
            path=target/'manifest.json';m=json.loads(path.read_text());mutate(m)
            path.write_text(json.dumps(m))
            (target/"protocol.json").write_text(json.dumps(m["spec"]))
            try:load_smoke_samples(target,split='train')
            except ValueError:checks.append(mutate.__name__)
            else:raise AssertionError('Corruption accepted: '+mutate.__name__)
    assert original=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir() if p.is_file()}
    result={'partition_counts':counts,'corruptions_rejected':checks,'source_unchanged':True}
    print(json.dumps(result,indent=2))
    Path('reports/v122_magpie_reader_checks.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
