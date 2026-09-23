"""Freeze train-only statistics and audit deterministic candidate batches."""
import argparse
import hashlib
import json
from pathlib import Path
from luck_agent.evaluation.batching import iter_batches
from luck_agent.evaluation.preprocessing import fit_scaler


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--index", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--policy", default="heuristic_coal_v029")
    args = p.parse_args()
    output = Path(args.output)
    if output.exists(): raise ValueError("Output already exists")
    policies = [args.policy]
    scaler = fit_scaler(args.index, policies)
    index = json.loads(Path(args.index).read_text(encoding="utf-8"))
    results, orders = {}, []
    for split, epoch in (("train", 0), ("train", 0), ("train", 1), ("validation", 0), ("test", 0)):
        keys, batches = [], 0
        for batch in iter_batches(args.index, split=split, policies=policies, scaler=scaler,
                                  shuffle_seed=42 if split == "train" else None, epoch=epoch):
            batches += 1
            for i, m in enumerate(batch["metadata"]):
                keys.append((m["policy"], m["seed"], m["step"]))
                if not batch["candidates_mask"][i][batch["label"][i]]:
                    raise ValueError("Invalid label after preprocessing")
        expected = {(r["policy"], r["episode_seed"], step)
                    for r in index["episodes"] if r["split"] == split and r["policy"] in policies
                    for step in range(r["transitions"])}
        if len(keys) != len(expected) or set(keys) != expected:
            raise ValueError("Missing or duplicate sample")
        if split == "train": orders.append(keys)
        results[f"{split}/epoch{epoch}"] = {"samples": len(keys), "batches": batches,
            "order_sha256": hashlib.sha256(json.dumps(keys).encode()).hexdigest()}
    if orders[0] != orders[1] or orders[0] == orders[2]:
        raise ValueError("Shuffle reproducibility failed")
    output.mkdir(parents=True)
    (output/"scaler.json").write_text(json.dumps(scaler, indent=2), encoding="utf-8")
    report = {"results": results, "same_epoch_reproduced": True, "different_epoch_reordered": True,
              "shuffle_seed": 42, "shuffle_buffer": 1024, "batch_size": 64,
              "all_samples_exactly_once": True, "training_steps": 0}
    (output/"audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__": main()
