"""Untrained interface prototype with a distinct vocabulary/checkpoint contract."""
import torch
from luck_agent.agents.spatial_model import SpatialCandidateModel,spatial_tensors
from luck_agent.evaluation.magpie_batching import MagpieCandidateEncoder
from luck_agent.env.rule_revision import rule_identity


class MagpieCandidateModel(SpatialCandidateModel):
    version='magpie-spatial-mlp-v1'
    encoder_class=MagpieCandidateEncoder


def magpie_tensors(batch):
    return spatial_tensors(batch,expected_version=MagpieCandidateEncoder.version)


def save_magpie_prototype(path,model):
    if type(model) is not MagpieCandidateModel:raise ValueError('Expected magpie model')
    encoder=MagpieCandidateEncoder()
    payload={'model_version':model.version,'encoder_version':encoder.version,'width':model.width,
        'symbols':encoder.symbols,'items':encoder.items,'rule_identity':rule_identity('instance-magpie-v1'),
        'purpose':'untrained_interface_probe','preprocessing':'raw_scalars_probe_only',
        'state_dict':model.state_dict()}
    with open(path,'xb') as stream:torch.save(payload,stream)


def load_magpie_prototype(path):
    payload=torch.load(path,map_location='cpu',weights_only=True);encoder=MagpieCandidateEncoder()
    if (payload.get('model_version')!=MagpieCandidateModel.version
            or payload.get('encoder_version')!=encoder.version or payload.get('symbols')!=encoder.symbols
            or payload.get('items')!=encoder.items or payload.get('rule_identity')!=rule_identity('instance-magpie-v1')
            or payload.get('purpose')!='untrained_interface_probe' or payload.get('preprocessing')!='raw_scalars_probe_only'):
        raise ValueError('Incompatible magpie prototype')
    model=MagpieCandidateModel(payload['width']);model.load_state_dict(payload['state_dict'],strict=True)
    return model.eval()
