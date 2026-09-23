"""Explicit supervised examples; executed transitions never become teacher transitions."""
import hashlib
import json
from pathlib import Path
from random import Random
from luck_agent.evaluation.batching import CandidateEncoder, iter_samples
from luck_agent.evaluation.dataset import read_episodes, split_for_seed


def teacher_example(record, source):
    teacher = record.get("teacher_action")
    if teacher is None or teacher not in record["legal_actions"]:
        raise ValueError("Missing or illegal teacher action")
    sample = CandidateEncoder().encode_observation(record["state"], record["legal_actions"])
    sample["label"] = record["legal_actions"].index(teacher)
    sample["metadata"].update(source=source, seed=record["episode_seed"], step=record["step"],
                              executed_action=record["action"], teacher_action=teacher)
    return sample  # Deliberately no reward, next_state, termination target.


def load_teacher_examples(directory, index_path):
    directory, index_path = Path(directory), Path(index_path)
    manifest = json.loads((directory/"manifest.json").read_text())
    digest = hashlib.sha256(index_path.read_bytes()).hexdigest()
    if digest != manifest["source_index_sha256"]:
        raise ValueError("Source index changed")
    index = json.loads(index_path.read_text())
    original_manifest = Path(index["source"])/"manifest.json"
    if hashlib.sha256(original_manifest.read_bytes()).hexdigest() != index["source_manifest_sha256"]:
        raise ValueError("Original manifest changed")
    original = json.loads(original_manifest.read_text())
    teacher = manifest["teacher"]
    if original["policies"].get(teacher) != manifest["teacher_config"]:
        raise ValueError("Teacher configuration mismatch")
    if manifest["split"] != "train" or manifest["supervision_field"] != "teacher_action" or manifest["executed_action_field"] != "action":
        raise ValueError("Wrong supervision contract")
    allowed = {r["episode_seed"] for r in index["episodes"] if r["policy"] == teacher and r["split"] == "train"}
    excluded = {r["episode_seed"] for r in index["episodes"] if r["split"] != "train"}
    if (allowed & excluded or set(manifest["seeds"]) != allowed or len(manifest["seeds"]) != len(allowed)
            or any(split_for_seed(s,index["salt"]) != "train" for s in allowed)):
        raise ValueError("Training seed provenance mismatch")
    path = directory/"learner.jsonl.gz"
    if hashlib.sha256(path.read_bytes()).hexdigest() != manifest["trajectory_sha256"]:
        raise ValueError("Annotated trajectory changed")
    examples, seen = [], set()
    for header, episode in read_episodes(path):
        if header["config"] != original["config"] or header["policy_config"].get("checkpoint_sha256") != manifest["checkpoint_sha256"] or header["policy_config"].get("teacher") != teacher:
            raise ValueError("Header provenance mismatch")
        seed = episode[0]["episode_seed"]
        if seed not in allowed or seed in seen: raise ValueError("Unexpected or duplicate episode")
        seen.add(seed)
        for r in episode: examples.append(teacher_example(r,manifest["trajectory_sha256"]))
    if seen != allowed: raise ValueError("Missing training episodes")
    return examples


def original_examples(index_path, teacher):
    result=[]
    for sample in iter_samples(index_path,split="train",policies=[teacher]):
        result.append({k:sample[k] for k in ("scalars","deck","items","candidates","label","metadata")})
    return result


def collate_supervision(samples):
    if not samples: raise ValueError("Empty supervised batch")
    batch={k:[s[k] for s in samples] for k in ("scalars","label","metadata")}
    for key,pad in (("deck",[0,0,0,0]),("items",0),("candidates",[0,0,0,0])):
        width=max(len(s[key]) for s in samples)
        batch[key]=[s[key]+[pad]*(width-len(s[key])) for s in samples]
        batch[key+"_mask"]=[[True]*len(s[key])+[False]*(width-len(s[key])) for s in samples]
    if any(not 0<=label<len(s["candidates"]) for label,s in zip(batch["label"],samples)):
        raise ValueError("Invalid teacher label")
    return batch


def mixed_decision_batches(original, annotated, *, steps=534, batch_size=64, seed=42, annotated_per_batch=32):
    if steps <= 0 or not 0 <= annotated_per_batch <= batch_size or batch_size <= 0:
        raise ValueError("Invalid sampling budget")
    pools=[[x for x in pool if len(x["candidates"])>1] for pool in (original,annotated)]
    sizes=(batch_size-annotated_per_batch,annotated_per_batch)
    if any(n and not pool for n,pool in zip(sizes,pools)): raise ValueError("Empty decision source")
    # Cycling permutations: no duplicates until each source cycle is exhausted.
    rng=Random(seed);orders=[[],[]]
    for _ in range(steps):
        batch=[]
        for i,n in enumerate(sizes):
            for _ in range(n):
                if not orders[i]:
                    orders[i]=list(range(len(pools[i])));rng.shuffle(orders[i])
                batch.append((i,pools[i][orders[i].pop()]))
        rng.shuffle(batch)
        yield batch
