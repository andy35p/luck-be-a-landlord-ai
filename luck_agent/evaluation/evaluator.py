import argparse
import csv
import hashlib
import json
import platform
import subprocess
import time
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from luck_agent import __version__
from luck_agent.env.game_env import GameEnv, EnvConfig
from luck_agent.env.rule_revision import rule_identity
from luck_agent.env.rule_engine import DATA
from luck_agent.legacy.fast_env import DEFAULT_RENTS
from luck_agent.agents.random_agent import RandomAgent
from luck_agent.agents.heuristic_agent import HeuristicAgent
from luck_agent.agents.magpie_cycle_agent import MagpieCycleAgent
from luck_agent.agents.forecast_agent import ForecastAgent
from luck_agent.agents.rent_forecast_agent import RentForecastAgent
from luck_agent.agents.rent_guard_agent import RentGuardAgent
from luck_agent.agents.reroll_agent import RerollConfig, RerollHeuristicAgent
from luck_agent.env.action import ActionType
from luck_agent.evaluation.metrics import summarize
from luck_agent.evaluation.decision_coverage import (finalize_diagnostics, finish_episode,
                                                     merge_diagnostics, new_diagnostics,
                                                     record_decision)


@dataclass(frozen=True)
class BCSpec:
    checkpoint: str
    checkpoint_sha256: str
    dataset_dir: str


def _make_policy(mode, env, reroll_config, coal_score_adjustment, bc_spec):
    if mode == "random":
        return None, {"agent": mode, "model_version": "none", "checkpoint": "",
                      "checkpoint_sha256": "", "encoder_version": "none", "training_steps": 0}
    if mode == "bc":
        if bc_spec is None:
            raise ValueError("BC evaluation requires checkpoint, SHA-256 and dataset directory")
        from luck_agent.agents.bc_policy import BCPolicyAdapter
        policy = BCPolicyAdapter(bc_spec.checkpoint, expected_sha256=bc_spec.checkpoint_sha256,
                                 dataset_dir=bc_spec.dataset_dir,
                                 rule_version=env.config.rule_version)
        return policy, {"agent": mode, "model_version": policy.model_version,
                        "checkpoint": policy.checkpoint,
                        "checkpoint_sha256": policy.checkpoint_sha256,
                        "encoder_version": policy.encoder_version,
                        "training_steps": policy.training_updates}
    policy = RerollHeuristicAgent(env.catalog, config=reroll_config) if mode == "heuristic_reroll" else HeuristicAgent(env.catalog, coal_score_adjustment=coal_score_adjustment)
    if mode == "heuristic_rent_guard":
        policy = RentGuardAgent(env.catalog)
    if mode == "heuristic_magpie_cycle":
        policy = MagpieCycleAgent(env.catalog)
    if mode == "forecast":
        policy = ForecastAgent(env.catalog)
    if mode == "forecast_rents":
        policy = RentForecastAgent(env.catalog)
    if mode == "forecast_rents_v143":
        from luck_agent.agents.rent_reroll_agent import RentRerollAgent
        policy = RentRerollAgent(env.catalog)
    return policy, {"agent": mode, "model_version": "rule-policy", "checkpoint": "",
                    "checkpoint_sha256": "", "encoder_version": "none", "training_steps": 0}


def _evaluate(games: int, mode: str, seed_start: int, config: EnvConfig,
              reroll_config: RerollConfig = RerollConfig(), *, transition_sink=None,
              coal_score_adjustment: float = 0.0, bc_spec: BCSpec | None = None,
              diagnostics: bool = False):
    if games <= 0:
        raise ValueError("games must be positive")
    if mode not in {"random", "heuristic", "heuristic_reroll", "heuristic_rent_guard",
                    "heuristic_magpie_cycle", "forecast", "forecast_rents", "forecast_rents_v143", "bc"}:
        raise ValueError("Unknown agent")
    if coal_score_adjustment != 0 and mode != "heuristic":
        raise ValueError("Coal adjustment requires heuristic mode")
    env = GameEnv(config)
    policy, metadata = _make_policy(mode, env, reroll_config, coal_score_adjustment, bc_spec)
    diagnostic = new_diagnostics(metadata) if diagnostics else None
    teacher = RentForecastAgent(env.catalog) if diagnostics and mode == "bc" else None
    rows = []
    start = time.perf_counter()
    for seed in range(seed_start, seed_start + games):
        state = env.reset(seed)
        agent = RandomAgent(seed + 1000000) if mode == "random" else policy
        total_reward = 0.0
        decisions = 0
        rerolls_used = removals_used = 0
        error_start = len(diagnostic["high_confidence_errors"]) if diagnostic else 0
        while not (state.is_terminal or state.is_truncated):
            actions = env.legal_actions()
            if mode == "bc":
                action, policy_diagnostic = agent.choose_with_diagnostics(state, actions)
                teacher_action = (teacher.choose(state, actions) if teacher is not None and len(actions) > 1
                                  else actions[0] if teacher is not None else None)
            else:
                action, policy_diagnostic, teacher_action = agent.choose(state, actions), None, None
            if diagnostic and not record_decision(diagnostic, seed=seed, step=decisions, state=state,
                                                  actions=actions, chosen=action,
                                                  policy=policy_diagnostic, teacher=teacher_action):
                raise ValueError("Policy selected an illegal action")
            if action not in actions:
                raise ValueError("Policy selected an illegal action")
            rerolls_used += action.action_type == ActionType.REROLL
            removals_used += action.action_type == ActionType.REMOVE_SYMBOL
            before = state
            state, reward, terminated, truncated, info = env.step(action)
            if transition_sink is not None:
                transition_sink(seed, decisions, before, actions, action, reward,
                                state, terminated, truncated, info)
            total_reward += reward
            decisions += 1
        if diagnostic:
            finish_episode(diagnostic, error_start, reward=total_reward,
                           stage=state.rent_stage, won=state.won)
        rows.append({"agent": mode, "model_version": metadata["model_version"],
                     "checkpoint": metadata["checkpoint"],
                     "checkpoint_sha256": metadata["checkpoint_sha256"],
                     "encoder_version": metadata["encoder_version"],
                     "seed": seed, "episode_id": seed, "won": int(state.won),
                     "stage": state.rent_stage, "final_stage": state.rent_stage,
                     "spins": state.spin_count, "coins": state.coins,
                     "final_coins": state.coins, "reward": total_reward,
                     "final_reward": total_reward, "decisions": decisions,
                     "truncated": int(state.is_truncated), "invalid_actions": 0,
                     "rerolls_used": rerolls_used, "removals_used": removals_used})
    return rows, time.perf_counter() - start, diagnostic


def evaluate(games: int, mode: str, seed_start: int, config: EnvConfig,
             reroll_config: RerollConfig = RerollConfig(), *, transition_sink=None,
             coal_score_adjustment: float = 0.0,
             bc_spec: BCSpec | None = None) -> tuple[list[dict], float]:
    rows, elapsed, _ = _evaluate(games, mode, seed_start, config, reroll_config,
                                 transition_sink=transition_sink,
                                 coal_score_adjustment=coal_score_adjustment,
                                 bc_spec=bc_spec)
    return rows, elapsed


def _parallel(games, mode, seed_start, config, reroll_config, workers, bc_spec, diagnostics):
    """Independent seed ranges, returned in seed order. No shared environment."""
    if type(workers) is not int or workers < 1:
        raise ValueError("workers must be a positive integer")
    if type(games) is not int or games < 1:
        raise ValueError("games must be a positive integer")
    if workers == 1:
        return _evaluate(games, mode, seed_start, config, reroll_config,
                         bc_spec=bc_spec, diagnostics=diagnostics)
    count = min(workers, games)
    size, remainder = divmod(games, count)
    start = time.perf_counter()
    rows = []
    parts = []
    # Spawn explicitly on every platform: no inherited RNG or mutable engine.
    with ProcessPoolExecutor(max_workers=count, mp_context=multiprocessing.get_context("spawn")) as pool:
        jobs = []
        offset = seed_start
        for i in range(count):
            n = size + (i < remainder)
            jobs.append(pool.submit(_evaluate, n, mode, offset, config, reroll_config,
                                    bc_spec=bc_spec, diagnostics=diagnostics))
            offset += n
        for job in jobs:
            batch, _, part = job.result()  # Propagate failures; never publish partial results.
            rows.extend(batch)
            if diagnostics:
                parts.append(part)
    return rows, time.perf_counter() - start, merge_diagnostics(parts) if diagnostics else None


def evaluate_parallel(games, mode, seed_start, config, reroll_config=RerollConfig(), *,
                      workers=1, bc_spec=None):
    rows, elapsed, _ = _parallel(games, mode, seed_start, config, reroll_config,
                                 workers, bc_spec, False)
    return rows, elapsed


def evaluate_parallel_detailed(games, mode, seed_start, config,
                               reroll_config=RerollConfig(), *, workers=1, bc_spec=None):
    rows, elapsed, diagnostic = _parallel(games, mode, seed_start, config, reroll_config,
                                          workers, bc_spec, True)
    return rows, elapsed, finalize_diagnostics(diagnostic)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--agent", choices=["random", "heuristic", "heuristic_reroll", "heuristic_rent_guard", "heuristic_magpie_cycle", "forecast", "forecast_rents", "forecast_rents_v143", "bc"], default="random")
    p.add_argument("--games", type=int, default=100)
    p.add_argument("--seed-start", type=int, default=0)
    p.add_argument("--workers", type=int, default=1, help="Independent evaluation processes (default: 1)")
    p.add_argument("--config", default="configs/default.json")
    p.add_argument("--output", default="logs/reused")
    p.add_argument("--policy-config", help="RerollConfig JSON; only for heuristic_reroll")
    p.add_argument("--checkpoint", help="BC checkpoint; required for --agent bc")
    p.add_argument("--checkpoint-sha256", help="Expected BC checkpoint SHA-256")
    p.add_argument("--dataset-dir", help="Bound BC corpus directory")
    args = p.parse_args()
    if args.policy_config and args.agent != "heuristic_reroll":
        p.error("--policy-config requires --agent heuristic_reroll")
    if args.agent == "bc" and not all((args.checkpoint, args.checkpoint_sha256, args.dataset_dir)):
        p.error("--agent bc requires --checkpoint, --checkpoint-sha256 and --dataset-dir")
    if args.agent != "bc" and any((args.checkpoint, args.checkpoint_sha256, args.dataset_dir)):
        p.error("BC checkpoint options require --agent bc")
    policy = RerollConfig(**json.loads(Path(args.policy_config).read_text(encoding="utf-8"))) if args.policy_config else RerollConfig()
    config_data = json.loads(Path(args.config).read_text(encoding="utf-8"))
    bc_spec = BCSpec(args.checkpoint, args.checkpoint_sha256, args.dataset_dir) if args.agent == "bc" else None
    rows, elapsed, diagnostic = evaluate_parallel_detailed(
        args.games, args.agent, args.seed_start, EnvConfig(**config_data), policy,
        workers=args.workers, bc_spec=bc_spec)
    summary = summarize(rows, elapsed, len(DEFAULT_RENTS))
    summary["invalid_actions"] = sum(row["invalid_actions"] for row in rows)
    output = Path(args.output) / (args.agent + "-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    output.mkdir(parents=True)
    def git(*command: str) -> str | None:
        result = subprocess.run(["git", *command], capture_output=True, text=True)
        return result.stdout.strip() if result.returncode == 0 else None
    sources = sorted(Path("luck_agent").rglob("*.py"))
    digest = hashlib.sha256(b"".join(str(s).encode() + s.read_bytes() for s in sources)).hexdigest()
    manifest = {"version": __version__, "agent": args.agent, "config": config_data,
                "workers_requested": args.workers, "workers_effective": min(args.workers,args.games),
                "timing_scope": "episode_loop" if args.workers == 1 else "pool_startup_evaluation_shutdown",
                "rule_identity": rule_identity(EnvConfig(**config_data).rule_version),
                "effective_env_config": asdict(EnvConfig(**config_data)),
                "policy_config": asdict(policy) if args.agent == "heuristic_reroll" else None,
                "seed_start": args.seed_start, "games": args.games, "python": platform.python_version(),
                "git_commit": git("rev-parse", "HEAD"), "git_status": git("status", "--porcelain"),
                "source_hash": digest, "catalog_hash": hashlib.sha256((DATA/"catalog.json").read_bytes()).hexdigest(),
                "effective_catalog_hash": hashlib.sha256(json.dumps(GameEnv(EnvConfig(**config_data)).catalog, sort_keys=True).encode()).hexdigest(),
                "provenance": json.loads((DATA/"provenance.json").read_text(encoding="utf-8")),
                "forecast_policy": {"trials": 8, "seed": 20270927, "objective": "mean_income_until_rent", "future_choices": "excluded"} if args.agent == "forecast" else None,
                "rent_forecast_policy": {"trials":8,"seed":20270927,"horizon":30,"ranking":["first_rent_paid","rents_paid","cash"],"future_choices":"excluded"} if args.agent in ("forecast_rents","forecast_rents_v143") else None,
                "training_steps": diagnostic["agent_metadata"]["training_steps"],
                "model": diagnostic["agent_metadata"]}
    if args.agent == "forecast_rents_v143":
        from luck_agent.agents.rent_reroll_agent import RentRerollConfig
        manifest["teacher_version"]="forecast_rents_v143"
        manifest["teacher_reroll_config"]=asdict(RentRerollConfig())
    for name, value in (("summary", summary), ("manifest", manifest)):
        (output/f"{name}.json").write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    with (output/"episodes.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (output/"decision_coverage.json").write_text(
        json.dumps({"coverage": diagnostic["coverage"]}, ensure_ascii=False, indent=2), encoding="utf-8")
    (output/"failure_summary.json").write_text(json.dumps({
        "bc_by_decision_type": diagnostic["bc_by_decision_type"],
        "high_confidence_errors": diagnostic["high_confidence_errors"],
        "inference": diagnostic["inference"],
        "teacher": "forecast_rents on the same BC states" if args.agent == "bc" else None,
        "high_confidence_definition": "teacher disagreement and softmax(top candidate logits) >= 0.8",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"agent": args.agent, "output": str(output), **summary}, indent=2))


if __name__ == "__main__":
    main()
