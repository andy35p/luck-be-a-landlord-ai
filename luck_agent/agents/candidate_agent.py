"""Live candidate scoring adapter. Scorers receive numerical features only."""
from math import isfinite
from luck_agent.evaluation.batching import CandidateEncoder, masked_argmax
from luck_agent.evaluation.preprocessing import scale_sample, validate_scaler
from luck_agent.evaluation.trajectory import normalized


class CandidateAgent:
    def __init__(self, scorer, *, rule_version, scaler=None, index_path=None, policies=None):
        if rule_version != "instance-coal-v1":
            raise ValueError("Only instance-coal-v1 is encoded")
        if scaler is not None:
            if index_path is None or not policies:
                raise ValueError("Scaler requires provenance")
            validate_scaler(scaler, index_path, policies)
        self.encoder, self.scorer, self.scaler = CandidateEncoder(), scorer, scaler

    def choose(self, state, actions):
        if state.is_terminal or state.is_truncated or not actions:
            raise ValueError("No active decision")
        if len(set(actions)) != len(actions):
            raise ValueError("Duplicate candidates")
        sample = self.encoder.encode_observation(normalized(state), normalized(actions))
        if len(actions) == 1:
            return actions[0]
        if self.scaler is not None: sample = scale_sample(sample, self.scaler)
        # Never pass labels, reward, episode identity or raw metadata to a scorer.
        features = {k: sample[k] for k in ("scalars", "deck", "items", "candidates")}
        features["candidate_mask"] = [True]*len(actions)
        scores = list(self.scorer(features))
        if len(scores) != len(actions) or not all(isfinite(x) for x in scores):
            raise ValueError("Scorer must return one finite score per candidate")
        selected = masked_argmax(scores, [True]*len(actions))
        return actions[selected]


def first_candidate_scores(features):
    """Deliberately weak deterministic smoke-test policy, not a trained agent."""
    return [-float(i) for i in range(len(features["candidates"]))]
