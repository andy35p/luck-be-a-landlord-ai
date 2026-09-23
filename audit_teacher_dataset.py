import hashlib
import json
from pathlib import Path
from luck_agent.evaluation.teacher_dataset import load_teacher_examples, original_examples, mixed_decision_batches


def main():
    config=json.loads(Path("configs/bc_aggregation_v1.json").read_text())
    original=original_examples(config["index"],config["teacher"])
    annotated=load_teacher_examples(config["annotated"],config["index"])
    keys=[(s["metadata"]["source"],s["metadata"]["seed"],s["metadata"]["step"]) for s in annotated]
    if len(keys)!=len(set(keys)):raise ValueError("Duplicate provenance key")
    if any(any(k in s for k in ("reward","next_state","terminated","truncated")) for s in original+annotated):
        raise ValueError("Transition targets leaked into BC example")
    def audit():
        counts=[0,0];order=[]
        for batch in mixed_decision_batches(original,annotated,steps=config["steps"],batch_size=config["batch_size"],seed=config["sampler_seed"],annotated_per_batch=config["candidate_annotated_per_batch"]):
            if sum(i==1 for i,_ in batch)!=32:raise ValueError("Mixture changed")
            for i,s in batch:
                counts[i]+=1;order.append((i,s["metadata"]["seed"],s["metadata"]["step"]))
                assert 0<=s["label"]<len(s["candidates"])
        return counts,hashlib.sha256(json.dumps(order).encode()).hexdigest()
    first=audit();assert first==audit()
    report={"original_rows":len(original),"annotated_rows":len(annotated),
        "original_decisions":sum(len(s["candidates"])>1 for s in original),
        "annotated_decisions":sum(len(s["candidates"])>1 for s in annotated),
        "sampled_rows_by_source":first[0],"order_sha256":first[1],"reproducible":True,
        "no_transition_targets":True,"unique_provenance_keys":True,"training_updates":0}
    with Path("reports/v042_teacher_dataset_audit.json").open("x") as f:json.dump(report,f,indent=2)
    print(json.dumps(report,indent=2))


if __name__=="__main__":main()
