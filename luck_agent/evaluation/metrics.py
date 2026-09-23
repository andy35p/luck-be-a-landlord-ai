import statistics


def summarize(rows: list[dict], seconds: float, stages: int) -> dict:
    n = len(rows)
    if n == 0:
        raise ValueError("At least one episode required")
    return {"games": n, "win_rate": sum(r["won"] for r in rows)/n,
            "average_stage": statistics.mean(r["stage"] for r in rows),
            "average_spins": statistics.mean(r["spins"] for r in rows),
            "average_coins": statistics.mean(r["coins"] for r in rows),
            "mean_reward": statistics.mean(r["reward"] for r in rows),
            "median_reward": statistics.median(r["reward"] for r in rows),
            "rent_survival": {str(i): sum(r["stage"] >= i for r in rows)/n for i in range(1, stages+1)},
            "truncated_games": sum(r["truncated"] for r in rows),
            "seconds": seconds, "episodes_per_second": n/seconds,
            "decisions_per_second": sum(r["decisions"] for r in rows)/seconds,
            "warning": "Recovered approximate environment only; not original-game win rate."}
