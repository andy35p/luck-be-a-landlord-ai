"""Collect paired development traces without changing either baseline policy."""
import argparse
import csv
import hashlib
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from datetime import datetime, timezone
from luck_agent.env.game_env import EnvConfig
from luck_agent.evaluation.evaluator import evaluate
from luck_agent.evaluation.trajectory import TrajectoryWriter, replay


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", type=int, default=100)
    parser.add_argument("--seed-start", type=int, default=0)
    parser.add_argument("--output", default="logs/coal_diagnosis")
    parser.add_argument("--include-validated", action="store_true",
                        help="Also collect the frozen coal-score candidate (-1.2)")
    args = parser.parse_args()
    config = EnvConfig(floor=1, rule_version="instance-coal-v1")
    output = Path(args.output) / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output.mkdir(parents=True)
    summary = {}
    policies = {"random": {}, "heuristic": {"coal_score_adjustment": 0.0}}
    if args.include_validated:
        policies["heuristic_coal_v029"] = {"coal_score_adjustment": -1.2}
    for label, policy in policies.items():
        mode = "random" if label == "random" else "heuristic"
        counts = {}
        action_counts, picks, reward_signs = Counter(), Counter(), Counter()
        with TrajectoryWriter(output / f"{label}.jsonl.gz", config, label, policy_config=policy) as writer:
            def sink(seed, step, state, actions, action, reward, next_state, terminated, truncated, info):
                writer(seed, step, state, actions, action, reward, next_state, terminated, truncated, info)
                action_counts[action.action_type.name] += 1
                reward_signs["positive" if reward > 0 else "negative" if reward < 0 else "zero"] += 1
                if int(action.action_type) == 0:
                    picks[action.target_id] += 1
                row = counts.setdefault(seed, {"coal_offers": 0, "coal_picks": 0,
                    "early_coal_picks": 0, "coal_removed": 0, "coal_matured": 0})
                row["coal_offers"] += state.decision_type in {"symbol", "forced_symbol"} and "coal" in state.candidates
                if int(action.action_type) == 0 and action.target_id == "coal":
                    row["coal_picks"] += 1
                    row["early_coal_picks"] += state.rent_stage < 2
                if int(action.action_type) == 4:
                    row["coal_removed"] += any(s.instance_id == action.target_id and s.symbol_id == "coal" for s in state.symbols)
                row["coal_matured"] += sum(e.get("reason") == "coal_matured" for e in info["instance_events"])
            rows, _ = evaluate(args.games, mode, args.seed_start, config, transition_sink=sink, **policy)
        for row in rows: row.update(counts[row["seed"]])
        with (output / f"{label}.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
        summary[label] = {"replay": replay(output / f"{label}.jsonl.gz"),
            "policy_config": policy, "action_counts": dict(action_counts),
            "symbol_picks": dict(picks), "transition_reward_signs": dict(reward_signs),
            "mean_episode_reward": sum(r["reward"] for r in rows)/len(rows),
            "wins": sum(r["won"] for r in rows), "truncations": sum(r["truncated"] for r in rows),
            "average_stage": sum(r["stage"] for r in rows)/len(rows),
            "totals": {key: sum(r[key] for r in rows) for key in counts[rows[0]["seed"]]},
            "early_pick_groups": {str(picked): {"games": len(group),
                "failed_before_rent_3": sum(r["stage"] < 3 for r in group)}
                for picked in (False, True)
                for group in [[r for r in rows if bool(r["early_coal_picks"]) == picked]]}}
    manifest = {"config": asdict(config), "seed_start": args.seed_start, "games": args.games,
        "policies": policies, "dataset_role": "development_behavior_data_not_holdout",
        "files": {p.name: {"bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                  for p in sorted(output.iterdir())},
        "purpose": "Development diagnosis, observational association only; no policy changes or training",
        "sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in sorted(Path("luck_agent").rglob("*.py")) + [Path(__file__), Path("luck_agent/legacy/catalog.json")]}}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), **summary}, indent=2))


if __name__ == "__main__":
    main()
