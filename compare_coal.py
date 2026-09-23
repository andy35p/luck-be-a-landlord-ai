"""Frozen single-variable coal experiment. Validation must follow development."""
import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from luck_agent.env.game_env import EnvConfig
from luck_agent.evaluation.evaluator import evaluate
from luck_agent.evaluation.compare_reroll import paired_stats
from luck_agent.evaluation.metrics import summarize


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("development", "validation"), default="development")
    parser.add_argument("--config", default="configs/v029_coal_experiment.json")
    parser.add_argument("--development-result")
    args = parser.parse_args()
    spec = json.loads(Path(args.config).read_text(encoding="utf-8"))
    if args.phase == "validation":
        if not args.development_result:
            parser.error("Validation requires --development-result")
        previous = json.loads(Path(args.development_result).read_text(encoding="utf-8"))
        if previous["spec"] != spec or previous["phase"] != "development" or not previous["paired"]["promotable_on_development"]:
            parser.error("Development result must pass the gate with this frozen spec")
    ranges = [set(range(spec[p]["seed_start"], spec[p]["seed_start"] + spec[p]["games"])) for p in ("development", "validation")]
    if ranges[0] & ranges[1]:
        parser.error("Development and validation overlap")
    files = sorted(Path("luck_agent").rglob("*.py")) + sorted(Path("luck_agent").rglob("*.json")) + [Path(__file__)]
    source_hash = hashlib.sha256(b"".join(str(p).encode() + p.read_bytes() for p in files)).hexdigest()
    if args.phase == "validation" and previous["source_hash"] != source_hash:
        parser.error("Source changed after development")
    output = Path("logs") / ("v029-coal-" + args.phase + "-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    output.mkdir(parents=True)
    rows, summaries = {}, {}
    for role in ("baseline", "candidate"):
        rows[role], seconds = evaluate(**spec[args.phase], mode="heuristic",
            config=EnvConfig(**spec["environment"]), coal_score_adjustment=spec[role+"_adjustment"])
        summaries[role] = summarize(rows[role], seconds, 13)
        with (output / (role+".csv")).open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[role][0])); writer.writeheader(); writer.writerows(rows[role])
    paired = paired_stats(rows["baseline"], rows["candidate"], spec["bootstrap_seed"], spec["bootstrap_samples"])
    report = {"phase": args.phase, "spec": spec, "source_hash": source_hash,
              "summaries": summaries, "paired": paired, "output": str(output), "training_steps": 0}
    (output / "comparison.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
