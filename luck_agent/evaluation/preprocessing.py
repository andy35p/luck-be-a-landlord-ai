"""Training-only scalar statistics and bounded reproducible shuffling."""
import hashlib
import math
from pathlib import Path
from random import Random


def shuffled(samples, seed, epoch=0, buffer_size=1024):
    if any(type(x) is not int for x in (seed, epoch, buffer_size)) or epoch < 0 or buffer_size < 2:
        raise ValueError("Integer seed, nonnegative epoch and buffer >= 2 required")
    rng = Random(f"behavior-shuffle-v1:{seed}:{epoch}")
    buffer = []
    for sample in samples:
        if len(buffer) < buffer_size:
            buffer.append(sample)
        else:
            i = rng.randrange(len(buffer))
            yield buffer[i]
            buffer[i] = sample
    rng.shuffle(buffer)
    yield from buffer


def fit_scaler(index_path, policies):
    from luck_agent.evaluation.batching import CandidateEncoder, iter_samples
    fields = list(CandidateEncoder.scalar_fields)
    n, means, m2 = 0, [0.0]*len(fields), [0.0]*len(fields)
    for sample in iter_samples(index_path, split="train", policies=policies):
        n += 1
        for i, x in enumerate(sample["scalars"]):
            if not math.isfinite(x): raise ValueError("Nonfinite scalar")
            delta = x-means[i]; means[i] += delta/n; m2[i] += delta*(x-means[i])
    if not n: raise ValueError("No training samples")
    return {"version": "train-zscore-v1", "encoder": CandidateEncoder.version,
            "index_sha256": hashlib.sha256(Path(index_path).read_bytes()).hexdigest(),
            "fit_split": "train", "policies": sorted(set(policies)), "samples": n,
            "fields": fields, "mean": means,
            "scale": [math.sqrt(max(0, v/n)) if v/n > 1e-12 else 1.0 for v in m2]}


def validate_scaler(scaler, index_path, policies):
    from luck_agent.evaluation.batching import CandidateEncoder
    if (scaler.get("version") != "train-zscore-v1" or scaler.get("fit_split") != "train"
            or scaler.get("encoder") != CandidateEncoder.version
            or scaler.get("fields") != list(CandidateEncoder.scalar_fields)
            or scaler.get("policies") != sorted(set(policies))
            or scaler.get("index_sha256") != hashlib.sha256(Path(index_path).read_bytes()).hexdigest()):
        raise ValueError("Scaler provenance mismatch")
    width = len(CandidateEncoder.scalar_fields)
    if (len(scaler["mean"]) != width or len(scaler["scale"]) != width
            or not all(math.isfinite(x) for x in scaler["mean"])
            or not all(math.isfinite(x) and x > 0 for x in scaler["scale"])):
        raise ValueError("Invalid scaler statistics")


def scale_sample(sample, scaler):
    # Do not transform categorical tokens, pointers, masks, reward or metadata.
    result = dict(sample)
    result["scalars"] = [(x-m)/s for x, m, s in zip(sample["scalars"], scaler["mean"], scaler["scale"])]
    if not all(math.isfinite(x) for x in result["scalars"]): raise ValueError("Nonfinite scaled input")
    return result
