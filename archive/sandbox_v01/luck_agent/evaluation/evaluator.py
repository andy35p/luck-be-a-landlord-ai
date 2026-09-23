"""python -m luck_agent.evaluation.evaluator --config experiments/configs/v01.json"""
import argparse
import csv
import hashlib
import json
import math
import platform
import statistics
import subprocess
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from luck_agent import __version__
from luck_agent.agents.baselines import Agent
from luck_agent.env.game_env import Config, GameEnv
from luck_agent.env.state_encoder import encode


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def episode(config: Config, variant: dict, seed: int) -> tuple[dict, list[dict]]:
    env = GameEnv(config)
    state = env.reset(seed)
    agent = Agent(variant["mode"], seed + 100000, variant["synergy_weight"])
    trajectory, entropies = [], []
    total_income = 0
    # Finite spins, finite resources, and one draft per spin imply a finite episode.
    limit = len(config.rents) * config.spins_per_rent * 4 + 20
    while not state.terminated:
        if len(trajectory) >= limit:
            raise RuntimeError("Episode exceeded structural action bound")
        actions = env.legal_actions()
        probabilities = agent.distribution(state, actions)
        entropy = -sum(p * math.log(p) for p in probabilities if p)
        action, probability, score = agent.choose(state, actions)
        observation = encode(state)
        state, reward, terminated, truncated, info = env.step(action)
        trajectory.append({"state": observation, "available_actions": [asdict(a) for a in actions],
                           "chosen_action": asdict(action), "action_probability": probability,
                           "estimated_value": None, "heuristic_score": score, "reward": reward, "info": info,
                           "terminated": terminated, "truncated": truncated})
        entropies.append(entropy)
        total_income += info["income"]
    actual_return = 0.0
    for row in reversed(trajectory):
        actual_return = row["reward"] + config.gamma * actual_return
        row["actual_return"] = actual_return
    return {"agent": variant["name"], "seed": seed, "reward": sum(r["reward"] for r in trajectory),
            "won": int(state.won), "rent_stage": state.stage, "final_coins": state.coins,
            "gross_income": total_income, "survival_spins": state.spins,
            "decision_entropy": statistics.mean(entropies), "rerolls_used": 2 - state.rerolls,
            "removals_used": 2 - state.removals, "deck_size": len(state.deck)}, trajectory


def summarize(rows: list[dict], stages: int = 4) -> dict:
    n = len(rows)
    wins = sum(r["won"] for r in rows)
    p = wins / n
    z = 1.96
    center = (p + z*z/(2*n))/(1+z*z/n)
    radius = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))/(1+z*z/n)
    return {"games_played": n, "win_rate": p, "win_rate_wilson_95": [max(0.0, center-radius), min(1.0, center+radius)],
            "mean_reward": statistics.mean(r["reward"] for r in rows),
            "median_reward": statistics.median(r["reward"] for r in rows),
            "mean_coin": statistics.mean(r["final_coins"] for r in rows),
            "survival_length": statistics.mean(r["survival_spins"] for r in rows),
            "survival_std": statistics.stdev(r["survival_spins"] for r in rows) if n > 1 else 0,
            "decision_entropy": statistics.mean(r["decision_entropy"] for r in rows),
            "rent_stage_distribution": dict(Counter(r["rent_stage"] for r in rows)),
            "rent_pass_rates": {str(i): sum(r["rent_stage"] >= i for r in rows)/n for i in range(1, stages + 1)},
            "reroll_efficiency": None, "remove_efficiency": None,
            "efficiency_note": "Resource use counts are in CSV; causal efficiency requires counterfactual evaluation."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="experiments/configs/v01.json")
    parser.add_argument("--split", choices=["development", "test"], default="development")
    parser.add_argument("--output", default="logs")
    args = parser.parse_args()
    spec = json.loads(Path(args.config).read_text(encoding="utf-8"))
    if set(spec["development_seeds"]) & set(spec["test_seeds"]):
        raise ValueError("Seed splits overlap")
    config = Config(**{**spec["environment"], "rents": tuple(spec["environment"]["rents"])})
    seeds = spec[f"{args.split}_seeds"]
    if not seeds or len(seeds) != len(set(seeds)):
        raise ValueError("Seeds must be nonempty and unique")
    output = Path(args.output) / (spec["experiment_id"] + "-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    output.mkdir(parents=True)
    def git(*command: str) -> str | None:
        result = subprocess.run(["git", *command], capture_output=True, text=True)
        return result.stdout.strip() if result.returncode == 0 else None
    sources = sorted(Path("luck_agent").rglob("*.py")) + sorted(Path("luck_agent/data").glob("*.json"))
    source_hash = hashlib.sha256(b"".join(str(p).encode() + p.read_bytes() for p in sources)).hexdigest()
    write_json(output / "manifest.json", {"experiment_id": spec["experiment_id"], "model_version": __version__,
        "environment_version": "sandbox-0.1", "database_hash": GameEnv(config).db.digest,
        "git_commit": git("rev-parse", "HEAD"), "git_status": git("status", "--porcelain"),
        "source_hash": source_hash, "python": platform.python_version(), "config": spec,
        "split": args.split, "seeds": seeds, "training_steps": 0, "games_played": len(seeds)*len(spec["variants"])})
    all_rows, summaries, failures = [], {}, []
    with (output / "trajectories.jsonl").open("w", encoding="utf-8") as stream:
        for variant in spec["variants"]:
            rows = []
            for seed in seeds:
                row, trajectory = episode(config, variant, seed)
                rows.append(row)
                for index, decision in enumerate(trajectory):
                    stream.write(json.dumps({"agent": variant["name"], "seed": seed, "decision": index, **decision}, ensure_ascii=False) + "\n")
                if not row["won"]:
                    failures.append({"category": "rent_failure", "agent": variant["name"], "seed": seed,
                                     "rent_stage": row["rent_stage"], "last_decisions": trajectory[-5:]})
            summaries[variant["name"]] = summarize(rows, len(config.rents))
            all_rows.extend(rows)
    with (output / "episodes.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(all_rows[0]))
        writer.writeheader()
        writer.writerows(all_rows)
    write_json(output / "summary.json", summaries)
    write_json(output / "failures.json", failures)
    # Paired descriptive differences; no claim of significance from a small sample.
    by_agent = {name: {r["seed"]: r for r in all_rows if r["agent"] == name} for name in summaries}
    comparisons = {}
    for other in by_agent:
        if other != "heuristic" and "heuristic" in by_agent:
            differences = [by_agent["heuristic"][s]["won"] - by_agent[other][s]["won"] for s in seeds]
            comparisons[other] = {"paired_win_delta": statistics.mean(differences), "per_seed_win_delta": differences,
                "paired_final_coin_delta": statistics.mean(by_agent["heuristic"][s]["final_coins"] - by_agent[other][s]["final_coins"] for s in seeds)}
    write_json(output / "comparisons.json", comparisons)
    report = ["# Failure report", "", "All results concern sandbox-0.1 only.",
              f"Failed episodes: {len(failures)}. Last 5 decisions per failure: failures.json.",
              "", "## Prioritized hypotheses", "",
              "1. Game Knowledge / Environment: incomplete rules dominate transfer uncertainty; validate one original mechanic at a time before any original-game claim.",
              "2. State / Model: static synergy ranks ignore layout probability; compare synergy weight 1 versus 0 using paired seeds.",
              "3. Exploration: conservative baselines never reroll or remove; next compare one resource decision rule at a time.",
              "", "No action is labeled a mistake without an oracle or counterfactual. No automatic parameter promotion from these development results."]
    (output / "failure_report.md").write_text("\n".join(report), encoding="utf-8")
    print(json.dumps({"output": str(output), "summary": summaries, "comparisons": comparisons}, indent=2))


if __name__ == "__main__":
    main()
