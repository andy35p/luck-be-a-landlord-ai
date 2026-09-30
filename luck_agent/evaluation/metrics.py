import statistics
from math import sqrt


Z_95 = statistics.NormalDist().inv_cdf(0.975)


def _mean_stats(values):
    values = list(values)
    mean = statistics.mean(values)
    std = statistics.stdev(values) if len(values) > 1 else 0.0
    margin = Z_95 * std / sqrt(len(values))
    return mean, std, [mean - margin, mean + margin]


def _wilson_interval(successes, total):
    proportion = successes / total
    denominator = 1 + Z_95**2 / total
    centre = (proportion + Z_95**2 / (2 * total)) / denominator
    margin = Z_95 * sqrt((proportion * (1 - proportion) + Z_95**2 / (4 * total)) / total) / denominator
    return [max(0.0, centre - margin), min(1.0, centre + margin)]


def summarize(rows: list[dict], seconds: float, stages: int) -> dict:
    n = len(rows)
    if n == 0:
        raise ValueError("At least one episode required")
    fields = {name: _mean_stats(r[key] for r in rows) for name, key in
              (("stage", "stage"), ("spins", "spins"), ("coins", "coins"), ("reward", "reward"))}
    wins = sum(r["won"] for r in rows)
    survival_counts = {str(i): sum(r["stage"] >= i for r in rows) for i in range(1, stages+1)}
    return {"games": n, "win_rate": wins/n,
            "win_rate_95_ci": _wilson_interval(wins, n),
            "average_stage": fields["stage"][0],
            "average_spins": fields["spins"][0],
            "average_coins": fields["coins"][0],
            "mean_reward": fields["reward"][0],
            "median_reward": statistics.median(r["reward"] for r in rows),
            "std": {name: result[1] for name, result in fields.items()},
            "mean_95_ci": {name: result[2] for name, result in fields.items()},
            "rent_survival": {stage: count/n for stage, count in survival_counts.items()},
            "rent_survival_95_ci": {stage: _wilson_interval(count, n)
                                     for stage, count in survival_counts.items()},
            "truncated_games": sum(r["truncated"] for r in rows),
            "seconds": seconds, "episodes_per_second": n/seconds,
            "decisions_per_second": sum(r["decisions"] for r in rows)/seconds,
            "warning": "Recovered approximate environment only; not original-game win rate."}
