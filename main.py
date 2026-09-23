"""A complete console episode using the recovered rule engine."""
import argparse
import json
from pathlib import Path
from luck_agent.env.game_env import GameEnv, EnvConfig
from luck_agent.agents.random_agent import RandomAgent
from luck_agent.agents.heuristic_agent import HeuristicAgent


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--agent", choices=["random", "heuristic"], default="random")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--config", default="configs/default.json")
    args = p.parse_args()
    env = GameEnv(EnvConfig(**json.loads(Path(args.config).read_text(encoding="utf-8"))))
    state = env.reset(args.seed)
    agent = RandomAgent(args.seed + 1000000) if args.agent == "random" else HeuristicAgent(env.catalog)
    print("Game #1 | recovered approximate engine |", args.agent)
    while not (state.is_terminal or state.is_truncated):
        actions = env.legal_actions()
        action = agent.choose(state, actions)
        if state.candidates:
            print("Candidates:", list(state.candidates))
        print(state.decision_type, "->", action.action_type.name, action.target_id or "")
        previous_spins = state.spin_count
        state, reward, _, _, info = env.step(action)
        if state.spin_count != previous_spins:
            print(f"Spin {state.spin_count} | Income {info['spin_income']:+.2f} | Coins {state.coins:.2f}")
            print("Deck:", [s.symbol_id for s in state.symbols])
        if info["rents_paid"]:
            print(f"Rent #{state.rent_stage}: PASS")
    print("TRUNCATED" if state.is_truncated else "WIN" if state.won else "GAME OVER")
    print(f"Final Stage: {state.rent_stage}\nTotal Spins: {state.spin_count}\nFinal Coins: {state.coins:.2f}")


if __name__ == "__main__":
    main()
