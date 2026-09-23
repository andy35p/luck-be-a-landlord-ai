"""Compare frozen baseline and count-feature development runs."""
import argparse
import csv
import json
from pathlib import Path
from luck_agent.evaluation.compare_reroll import paired_stats


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--candidate",required=True)
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    base=Path("logs/bc-smoke-20260922T132337693785Z");candidate=Path(args.candidate)
    def rows(path):
        with (path/"trained.csv").open() as f:
            return [{**{k:int(v) for k,v in r.items()},"rerolls_used":0} for r in csv.DictReader(f)]
    a,b=rows(base),rows(candidate)
    stats=paired_stats(a,b,39,5000)
    for pair in stats["worst_pairs"]:pair.pop("rerolls_used")
    controls={name:(base/(name+".csv")).read_bytes()==(candidate/(name+".csv")).read_bytes() for name in ("initial","teacher")}
    if not all(controls.values()):raise ValueError("Control changed")
    old=json.loads((base/"results.json").read_text());new=json.loads((candidate/"results.json").read_text())
    old_diag=json.loads(Path("reports/v038_bc_diagnosis.json").read_text())
    new_diag=json.loads(Path("reports/v039_bc_diagnosis.json").read_text())
    selected={r["seed"] for r in old_diag["worst_pairs"]}
    failure_pairs=[dict(seed=x["seed"],baseline_stage=x["stage"],candidate_stage=y["stage"]) for x,y in zip(a,b) if x["seed"] in selected]
    report={"baseline":str(base),"candidate":str(candidate),"controls_identical":controls,"paired":stats,
        "baseline_offline":old["final_test"],"candidate_offline":new["final_test"],
        "baseline_online":old["online"]["trained"],"candidate_online":new["online"]["trained"],
        "baseline_disagreements":old_diag["offline_test_symbol_counts"],"candidate_disagreements":new_diag["offline_test_symbol_counts"],
        "previous_worst_five":failure_pairs,"purpose":"development comparison only; not independent validation"}
    with Path(args.output).open("x") as f:json.dump(report,f,indent=2)
    print(json.dumps({k:v for k,v in report.items() if k not in ("baseline_offline","candidate_offline")},indent=2))


if __name__=="__main__":main()
