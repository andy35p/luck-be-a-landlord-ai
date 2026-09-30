"""Research-only checkpoint adapter for the matching simulator domain."""
import torch
from luck_agent.agents.magpie_checkpoint import load_magpie_checkpoint
from luck_agent.agents.magpie_model import magpie_tensors
from luck_agent.evaluation.magpie_batching import MagpieCandidateEncoder
from luck_agent.evaluation.magpie_preprocessing import scale_magpie_sample
from luck_agent.evaluation.trajectory import normalized


class MagpieModelAgent:
    checkpoint_loader=staticmethod(load_magpie_checkpoint)
    scale=staticmethod(scale_magpie_sample)

    def __init__(self,checkpoint,*,directory,rule_version):
        if rule_version!='instance-magpie-v1':raise ValueError('Magpie model requires matching rules')
        self.model,self.scaler,self.updates=self.checkpoint_loader(checkpoint,directory=directory)
        self.encoder=MagpieCandidateEncoder()

    def score_actions(self,state,actions):
        if state.is_terminal or state.is_truncated or not actions or len(set(actions))!=len(actions):
            raise ValueError('Invalid active decision')
        sample=self.encoder.encode_observation(normalized(state),normalized(actions))
        if len(actions)==1:return (0.0,)
        features=self.encoder.features(self.scale(sample,self.scaler))
        batch={k:[features[k]] for k in ('scalars','deck','items','candidates','board','board_mask','board_observed')}
        batch.update(encoder_version=self.encoder.version,deck_mask=[[True]*len(features['deck'])],
                     items_mask=[[True]*len(features['items'])],candidates_mask=[[True]*len(actions)])
        with torch.no_grad():scores=self.model(magpie_tensors(batch))[0]
        if scores.numel()!=len(actions) or not torch.isfinite(scores).all():raise ValueError('Invalid candidate scores')
        return tuple(float(x) for x in scores)

    def choose(self,state,actions):
        scores=self.score_actions(state,actions)
        return actions[max(range(len(scores)),key=scores.__getitem__)]
