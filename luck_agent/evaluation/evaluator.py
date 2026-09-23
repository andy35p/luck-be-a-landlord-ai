import argparse
import csv
import hashlib
import json
import platform
import subprocess
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from luck_agent import __version__
from luck_agent.env.game_env import GameEnv, EnvConfig
from luck_agent.env.rule_engine import DATA
from luck_agent.legacy.fast_env import DEFAULT_RENTS
from luck_agent.agents.random_agent import RandomAgent
from luck_agent.agents.heuristic_agent import HeuristicAgent
from luck_agent.agents.reroll_agent import RerollConfig, RerollHeuristicAgent
from luck_agent.env.action import ActionType
from luck_agent.evaluation.metrics import summarize


def evaluate(games: int, mode: str, seed_start: int, config: EnvConfig,
             reroll_config: RerollConfig = RerollConfig(), *, transition_sink=None,
             coal_score_adjustment: float = 0.0) -> tuple[list[dict], float]:
    if games <= 0:
        raise ValueError("games must be positive")
    if mode not in {"random", "heuristic", "heuristic_reroll"}:
        raise ValueError("Unknown agent")
    if coal_score_adjustment != 0 and mode != "heuristic":
        raise ValueError("Coal adjustment requires heuristic mode")
    env = GameEnv(config)
    heuristic = RerollHeuristicAgent(env.catalog, config=reroll_config) if mode == "heuristic_reroll" else HeuristicAgent(env.catalog, coal_score_adjustment=coal_score_adjustment)
    rows = []
    start = time.perf_counter()
    for seed in range(seed_start, seed_start + games):
        state = env.reset(seed)
        agent = RandomAgent(seed + 1000000) if mode == "random" else heuristic
        total_reward = 0.0
        decisions = 0
        rerolls_used = removals_used = 0
        while not (state.is_terminal or state.is_truncated):
            actions = env.legal_actions()
            action = agent.choose(state, actions)
            rerolls_used += action.action_type == ActionType.REROLL
            removals_used += action.action_type == ActionType.REMOVE_SYMBOL
            before = state
            state, reward, terminated, truncated, info = env.step(action)
            if transition_sink is not None:
                transition_sink(seed, decisions, before, actions, action, reward,
                                state, terminated, truncated, info)
            total_reward += reward
            decisions += 1
        rows.append({"seed": seed, "won": int(state.won), "stage": state.rent_stage,
                     "spins": state.spin_count, "coins": state.coins, "reward": total_reward,
                     "decisions": decisions, "truncated": int(state.is_truncated),
                     "rerolls_used": rerolls_used, "removals_used": removals_used})
    return rows, time.perf_counter() - start


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--agent", choices=["random", "heuristic", "heuristic_reroll"], default="random")
    p.add_argument("--games", type=int, default=100)
    p.add_argument("--seed-start", type=int, default=0)
    p.add_argument("--config", default="configs/default.json")
    p.add_argument("--output", default="logs/reused")
    p.add_argument("--policy-config", help="RerollConfig JSON; only for heuristic_reroll")
    args = p.parse_args()
    if args.policy_config and args.agent != "heuristic_reroll":
        p.error("--policy-config requires --agent heuristic_reroll")
    policy = RerollConfig(**json.loads(Path(args.policy_config).read_text(encoding="utf-8"))) if args.policy_config else RerollConfig()
    config_data = json.loads(Path(args.config).read_text(encoding="utf-8"))
    rows, elapsed = evaluate(args.games, args.agent, args.seed_start, EnvConfig(**config_data), policy)
    summary = summarize(rows, elapsed, len(DEFAULT_RENTS))
    output = Path(args.output) / (args.agent + "-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    output.mkdir(parents=True)
    def git(*command: str) -> str | None:
        result = subprocess.run(["git", *command], capture_output=True, text=True)
        return result.stdout.strip() if result.returncode == 0 else None
    sources = sorted(Path("luck_agent").rglob("*.py"))
    digest = hashlib.sha256(b"".join(str(s).encode() + s.read_bytes() for s in sources)).hexdigest()
    manifest = {"version": __version__, "agent": args.agent, "config": config_data,
                "effective_env_config": asdict(EnvConfig(**config_data)),
                "policy_config": asdict(policy) if args.agent == "heuristic_reroll" else None,
                "seed_start": args.seed_start, "games": args.games, "python": platform.python_version(),
                "git_commit": git("rev-parse", "HEAD"), "git_status": git("status", "--porcelain"),
                "source_hash": digest, "catalog_hash": hashlib.sha256((DATA/"catalog.json").read_bytes()).hexdigest(),
                "effective_catalog_hash": hashlib.sha256(json.dumps(GameEnv(EnvConfig(**config_data)).catalog, sort_keys=True).encode()).hexdigest(),
                "provenance": json.loads((DATA/"provenance.json").read_text(encoding="utf-8")),
                "training_steps": 0}
    for name, value in (("summary", summary), ("manifest", manifest)):
        (output/f"{name}.json").write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    with (output/"episodes.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"agent": args.agent, "output": str(output), **summary}, indent=2))


if __name__ == "__main__":
    main()
