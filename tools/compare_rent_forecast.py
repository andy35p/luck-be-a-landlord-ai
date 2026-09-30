"""Frozen V117 comparison with durable batches and source drift detection."""
import csv
import hashlib
import json
from pathlib import Path
import statistics
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.compare_forecast import paired_difference
from luck_agent.evaluation.evaluator import evaluate
from luck_agent.env.game_env import EnvConfig
from luck_agent.env.rule_revision import rule_identity


def main():
    root=Path(__file__).resolve().parents[1]
    protocol_path=root/'configs/v117_rent_comparison.json'
    protocol_bytes=protocol_path.read_bytes()
    protocol=json.loads(protocol_bytes)
    output=root/'logs/v117-rent-comparison-run1'
    output.mkdir(parents=True,exist_ok=False)
    (output/'protocol.json').write_bytes(protocol_bytes)
    def hashes():
        paths=sorted((root/'luck_agent').rglob('*.py'))+[Path(__file__),root/'tools/compare_forecast.py',root/'luck_agent/legacy/catalog.json',protocol_path]
        return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    original=hashes()
    (output/'source_hashes.json').write_text(json.dumps(original,indent=2))
    config=EnvConfig(floor=protocol['floor'],rule_version=protocol['rule_version'])
    results={};timings={}
    for mode in (protocol['baseline'],protocol['candidate']):
        results[mode]=[];timings[mode]=0
        for offset in range(0,protocol['games'],protocol['batch_size']):
            if hashes()!=original:raise ValueError('Source drift before batch')
            count=min(protocol['batch_size'],protocol['games']-offset)
            rows,elapsed=evaluate(count,mode,protocol['seed_start']+offset,config)
            if hashes()!=original:raise ValueError('Source drift during batch')
            results[mode].extend(rows);timings[mode]+=elapsed
            with (output/f'{mode}-{offset:04}.csv').open('x',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
            print(json.dumps({'mode':mode,'completed':len(results[mode]),'total':protocol['games']}),flush=True)
    old,new=(results[protocol[k]] for k in ('baseline','candidate'))
    win=paired_difference(old,new,'won');stage=paired_difference(old,new,'stage')
    summary={m:{'win_rate':statistics.mean(r['won'] for r in rows),'stage':statistics.mean(r['stage'] for r in rows),'truncated':sum(r['truncated'] for r in rows)} for m,rows in results.items()}
    passed=win['normal_95_interval'][0]>0 and stage['mean']>=0 and all(s['truncated']==0 for s in summary.values())
    report={'protocol':protocol,'source_hashes':original,'rule_identity':rule_identity(config.rule_version),
            'summary':summary,'seconds':timings,'win_difference':win,'stage_difference':stage,'research_gate_passed':passed}
    (output/'comparison.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='source_hashes'},indent=2),flush=True)


if __name__=='__main__':main()
