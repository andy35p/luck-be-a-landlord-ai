"""Single-variable paired development experiment; never changes defaults."""
import argparse
import csv
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from random import Random
import statistics
import subprocess
import platform
from luck_agent.agents.reroll_agent import RerollConfig
from luck_agent.env.game_env import EnvConfig
from luck_agent.evaluation.evaluator import evaluate
from luck_agent.evaluation.metrics import summarize
from luck_agent.legacy.fast_env import DEFAULT_RENTS


def paired_stats(baseline: list[dict], experiment: list[dict], seed: int, samples: int,
                 confidence: float = .95) -> dict:
    if not baseline or len(baseline) != len(experiment):
        raise ValueError("Need nonempty paired rows")
    if [x["seed"] for x in baseline] != [x["seed"] for x in experiment]:
        raise ValueError("Seed pairs do not match")
    if samples < 2:
        raise ValueError("Need at least two bootstrap samples")
    if not 0 < confidence < 1:
        raise ValueError("Confidence must be between zero and one")
    deltas = [b["stage"]-a["stage"] for a,b in zip(baseline, experiment)]
    rng = Random(seed)
    boot = sorted(statistics.mean(rng.choices(deltas, k=len(deltas))) for _ in range(samples))
    tail = (1-confidence)/2
    interval = [boot[int(tail*(samples-1))], boot[int((1-tail)*(samples-1))]]
    return {"mean_stage_delta": statistics.mean(deltas), "paired_bootstrap_interval": interval,
            "confidence":confidence, **({"paired_bootstrap_95":interval} if confidence == .95 else {}),
            "improved": sum(d>0 for d in deltas), "unchanged": deltas.count(0), "worse": sum(d<0 for d in deltas),
            "promotable_on_development": interval[0] > 0 and not any(r["truncated"] for r in baseline+experiment),
            "worst_pairs": sorted([{"seed": a["seed"], "baseline_stage": a["stage"],
                                     "experiment_stage": b["stage"], "delta": b["stage"]-a["stage"],
                                     "rerolls_used": b["rerolls_used"]} for a,b in zip(baseline,experiment)], key=lambda r:r["delta"])[:5]}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="configs/v02_reroll_experiment.json")
    args = p.parse_args()
    spec = json.loads(Path(args.config).read_text(encoding="utf-8"))
    agent_configs = {role: RerollConfig(**spec.get(f"{role}_reroll_config", {})) for role in ("baseline", "experiment")}
    used = set(range(spec["seed_start"], spec["seed_start"]+spec["games"]))
    held = set(range(spec["held_out_seed_start"], spec["held_out_seed_start"]+spec["held_out_games"]))
    if used & held:
        raise ValueError("Development and held-out seeds overlap")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    out = Path("logs")/f"{spec['experiment_id']}-{stamp}"
    out.mkdir(parents=True)
    source_files = sorted(Path("luck_agent").rglob("*.py")) + sorted(Path("luck_agent").rglob("*.json"))
    digest = hashlib.sha256(b"".join(str(p).encode()+p.read_bytes() for p in source_files)).hexdigest()
    git = subprocess.run(["git","rev-parse","HEAD"],capture_output=True,text=True)
    manifest = {"config": spec, "reroll_configs": {k:asdict(v) for k,v in agent_configs.items()}, "source_and_data_hash": digest,
                "git_commit": git.stdout.strip() if git.returncode == 0 else None,
                "python": platform.python_version(), "training_steps": 0}
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    rows, summaries = {}, {}
    for role in ("baseline", "experiment"):
        mode = spec[role]
        print(f"Running {role}: {mode}, {spec['games']} games", flush=True)
        rows[role], seconds = evaluate(spec["games"], mode, spec["seed_start"], EnvConfig(**spec["environment"]), agent_configs[role])
        summaries[role] = summarize(rows[role], seconds, len(DEFAULT_RENTS))
        summaries[role]["mean_rerolls_used"] = statistics.mean(r["rerolls_used"] for r in rows[role])
        with (out/f"{role}.csv").open("w",newline="",encoding="utf-8") as stream:
            writer=csv.DictWriter(stream,fieldnames=list(rows[role][0]))
            writer.writeheader()
            writer.writerows(rows[role])
    paired = paired_stats(rows["baseline"],rows["experiment"],spec["bootstrap_seed"],spec["bootstrap_samples"])
    report = {"output": str(out), "summaries":summaries, "paired":paired,
              "decision":"Eligible for held-out validation; default unchanged" if paired["promotable_on_development"] else "Do not promote; retain original heuristic",
              "limitations":"Approximate rules; development seeds; bootstrap uncertainty excludes simulator bias and policy search."}
    (out/"comparison.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))


if __name__ == "__main__":
    main()
