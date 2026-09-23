"""Reference BC metrics, not an optimizer or neural network implementation."""
import math


def decision_mask(candidate_masks):
    return [sum(mask) > 1 for mask in candidate_masks]


def masked_bc_metrics(logits, labels, candidate_masks):
    if not (len(logits) == len(labels) == len(candidate_masks)):
        raise ValueError("Batch dimensions disagree")
    losses, correct = [], 0
    forced = 0
    for scores, label, mask in zip(logits, labels, candidate_masks):
        if len(scores) != len(mask) or not all(type(x) is bool for x in mask):
            raise ValueError("Invalid candidate mask")
        valid = [i for i, x in enumerate(mask) if x]
        if type(label) is not int or label not in valid:
            raise ValueError("Label must identify a legal candidate")
        if not all(math.isfinite(scores[i]) for i in valid):
            raise ValueError("Nonfinite legal logit")
        if len(valid) == 1:
            forced += 1
            continue
        peak = max(scores[i] for i in valid)
        # Padded entries never enter normalization, even if set to inf/nan.
        losses.append((peak-scores[label]) + math.log(sum(math.exp(scores[i]-peak) for i in valid)))
        correct += max(valid, key=lambda i: scores[i]) == label
    n = len(losses)
    return {"decision_count": n, "forced_count": forced,
            "loss_sum": sum(losses), "correct_count": correct,
            "mean_nll": sum(losses)/n if n else None,
            "decision_accuracy": correct/n if n else None}
