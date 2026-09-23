"""Count real decision rows and audit reference masked loss on stored batches."""
import argparse
import json
import hashlib
from pathlib import Path
from luck_agent.evaluation.batching import iter_batches
from luck_agent.evaluation.bc_contract import masked_bc_metrics


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--index", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    contract = json.loads(Path("configs/bc_contract_v1.json").read_text())
    results = {}
    for split in ("train", "validation", "test"):
        phases = {}; total = {"decision_count": 0, "forced_count": 0, "loss_sum": 0.0, "correct_count": 0}
        for batch in iter_batches(args.index, split=split, policies=[contract["teacher"]]):
            scores = [[0.0 if valid else 1e9 for valid in mask] for mask in batch["candidates_mask"]]
            measured = masked_bc_metrics(scores, batch["label"], batch["candidates_mask"])
            for key in total: total[key] += measured[key]
            for row, label, mask, metadata in zip(scores, batch["label"], batch["candidates_mask"], batch["metadata"]):
                phase = phases.setdefault(metadata["decision_type"], {"rows": 0, "decisions": 0, "first_candidate_correct": 0, "uniform_expected_correct": 0.0})
                phase["rows"] += 1
                if sum(mask) > 1:
                    phase["decisions"] += 1
                    phase["first_candidate_correct"] += label == 0
                    phase["uniform_expected_correct"] += 1/sum(mask)
        n = total["decision_count"]
        results[split] = {**total, "uniform_logits_mean_nll": total["loss_sum"]/n,
            "first_candidate_decision_accuracy": total["correct_count"]/n,
            "uniform_random_expected_decision_accuracy": sum(x["uniform_expected_correct"] for x in phases.values())/n,
            "phases": phases}
    report = {"contract": contract, "index_sha256": hashlib.sha256(Path(args.index).read_bytes()).hexdigest(),
              "results": results, "note": "Uniform logits and first-candidate tie breaking only; no fitted model."}
    with Path(args.output).open("x", encoding="utf-8") as stream: json.dump(report, stream, indent=2)
    print(json.dumps(results, indent=2))


if __name__ == "__main__": main()
