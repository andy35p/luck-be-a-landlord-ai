"""Frozen three-policy validation; writes manifest before any outcomes are seen."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
from luck_agent.agents.reroll_agent import RerollConfig
from luck_agent.env.game_env import EnvConfig
from luck_agent.evaluation.evaluator import evaluate
from luck_agent.evaluation.compare_reroll import paired_stats
from luck_agent.evaluation.metrics import summarize
from luck_agent.legacy.fast_env import DEFAULT_RENTS


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--config",default="configs/v022_frozen_validation.json")
    args=parser.parse_args()
    spec=json.loads(Path(args.config).read_text(encoding="utf-8"))
    if not spec["policy_frozen"] or spec["seed_start"]<20000:
        raise ValueError("Requires frozen policies and reserved validation range")
    out=Path("logs")/(spec["experiment_id"]+"-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    out.mkdir(parents=True)
    sources=sorted(Path("luck_agent").rglob("*.py"))+sorted(Path("luck_agent").rglob("*.json"))
    manifest={"config":spec,"python":platform.python_version(),"source_data_hash":hashlib.sha256(b"".join(str(p).encode()+p.read_bytes() for p in sources)).hexdigest(),"training_steps":0}
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    rows={}; summaries={}
    for name,policy in spec["policies"].items():
        print(f"Validating {name}: {spec['games']} games",flush=True)
        rows[name],seconds=evaluate(spec["games"],policy["mode"],spec["seed_start"],EnvConfig(**spec["environment"]),RerollConfig(**policy["reroll_config"]))
        summaries[name]=summarize(rows[name],seconds,len(DEFAULT_RENTS))
        summaries[name]["total_rerolls"]=sum(r["rerolls_used"] for r in rows[name])
        with (out/f"{name}.csv").open("w",newline="",encoding="utf-8") as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[name][0]));writer.writeheader();writer.writerows(rows[name])
        print(json.dumps({"policy":name,"summary":summaries[name]}),flush=True)
    comparisons={name:paired_stats(rows[name],rows["candidate"],spec["bootstrap_seed"],spec["bootstrap_samples"],spec["comparison_confidence"]) for name in ("no_reroll","conservative")}
    passed=all(r["promotable_on_development"] for r in comparisons.values())
    # Generic comparator's legacy field name is renamed for this actual validation.
    for stats in comparisons.values():
        stats["passes_comparison_gate"]=stats.pop("promotable_on_development")
    report={"output":str(out),"summaries":summaries,"comparisons":comparisons,
            "passes_frozen_validation":passed,"defaults_changed":False,
            "scope":"Approximate engine; rent-stage metric; no claim of original-game equivalence or win-rate improvement.",
            "seed_status":"20000-20999 consumed as V0.2.2 validation; do not treat as unseen after this run."}
    (out/"validation.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))


if __name__=="__main__":
    main()
