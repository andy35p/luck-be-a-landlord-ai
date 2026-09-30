"""Online spatial scorer adapter; model sees public numerical features only."""
from math import isfinite
from luck_agent.evaluation.spatial_batching import SpatialCandidateEncoder
from luck_agent.evaluation.spatial_preprocessing import validate_spatial_scaler,scale_spatial_sample
from luck_agent.evaluation.trajectory import normalized
from luck_agent.evaluation.batching import masked_argmax


class SpatialCandidateAgent:
    def __init__(self,scorer,*,rule_version,scaler,directory,policies):
        if rule_version!='instance-goldfish-v1':raise ValueError('Spatial agent requires goldfish rules')
        validate_spatial_scaler(scaler,directory,policies)
        self.encoder=SpatialCandidateEncoder();self.scorer=scorer;self.scaler=scaler

    def choose(self,state,actions):
        if state.is_terminal or state.is_truncated or not actions:raise ValueError('No active decision')
        if len(set(actions))!=len(actions):raise ValueError('Duplicate candidates')
        sample=self.encoder.encode_observation(normalized(state),normalized(actions))
        if len(actions)==1:return actions[0]
        features=self.encoder.features(scale_spatial_sample(sample,self.scaler))
        scores=list(self.scorer(features))
        if len(scores)!=len(actions) or not all(isfinite(x) for x in scores):
            raise ValueError('Expected one finite score per legal action')
        return actions[masked_argmax(scores,features['candidate_mask'])]
