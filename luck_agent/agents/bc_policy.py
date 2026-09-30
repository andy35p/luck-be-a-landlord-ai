"""Thin deterministic evaluation adapter for the data-bound V130 policy."""
import hashlib
import math
from pathlib import Path
from time import perf_counter

import torch

from luck_agent.agents.magpie_corpus_agent import MagpieCorpusAgent
from luck_agent.agents.magpie_model import MagpieCandidateModel
from luck_agent.evaluation.magpie_batching import MagpieCandidateEncoder


class BCPolicyAdapter:
    def __init__(self, checkpoint, *, expected_sha256, dataset_dir, rule_version):
        checkpoint = Path(checkpoint)
        if len(expected_sha256) != 64 or any(c not in "0123456789abcdef" for c in expected_sha256.lower()):
            raise ValueError("A valid expected checkpoint SHA-256 is required")
        actual = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        if actual != expected_sha256.lower():
            raise ValueError("Checkpoint SHA-256 mismatch")
        torch.set_num_threads(1)
        torch.use_deterministic_algorithms(True)
        self.agent = MagpieCorpusAgent(checkpoint, directory=dataset_dir, rule_version=rule_version)
        self.checkpoint = str(checkpoint)
        self.checkpoint_sha256 = actual
        self.model_version = MagpieCandidateModel.version
        self.encoder_version = MagpieCandidateEncoder.version
        self.training_updates = self.agent.updates

    def choose(self, state, actions):
        return self.choose_with_diagnostics(state, actions)[0]

    def choose_with_diagnostics(self, state, actions):
        started = perf_counter()
        scores = self.agent.score_actions(state, actions)
        selected = max(range(len(scores)), key=scores.__getitem__)
        if len(scores) == 1:
            confidence, margin = 1.0, None
        else:
            maximum = max(scores)
            weights = [math.exp(score - maximum) for score in scores]
            total = sum(weights)
            probabilities = [weight / total for weight in weights]
            ordered = sorted(scores, reverse=True)
            confidence = probabilities[selected]
            margin = ordered[0] - ordered[1]
        return actions[selected], {
            "scores": scores,
            "top1_confidence": confidence,
            "score_margin": margin,
            "latency_seconds": perf_counter() - started,
        }
