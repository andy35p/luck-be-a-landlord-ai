"""Data-bound research checkpoints; incompatible with raw interface probes."""
import torch
from luck_agent.agents.magpie_model import MagpieCandidateModel
from luck_agent.evaluation.magpie_batching import MagpieCandidateEncoder
from luck_agent.evaluation.magpie_dataset import POLICY
from luck_agent.evaluation.magpie_preprocessing import validate_magpie_scaler
from luck_agent.env.rule_revision import rule_identity


def contract():
    encoder=MagpieCandidateEncoder()
    return {'checkpoint_version':'magpie-research-checkpoint-v1','model_version':MagpieCandidateModel.version,
        'encoder_version':encoder.version,'symbols':encoder.symbols,'items':encoder.items,
        'rule_identity':rule_identity('instance-magpie-v1'),'teacher':'forecast_rents','teacher_config':POLICY,
        'purpose':'engineering_smoke_not_validated_policy'}


def validate_payload(payload,directory):
    if any(payload.get(k)!=v for k,v in contract().items()):raise ValueError('Checkpoint contract mismatch')
    if type(payload.get('width')) is not int or not 1<=payload['width']<=256:raise ValueError('Invalid model width')
    if type(payload.get('training_updates')) is not int or payload['training_updates']<0:raise ValueError('Invalid update count')
    validate_magpie_scaler(payload['scaler'],directory)
    if not payload['state_dict'] or any(not torch.is_tensor(t) or not torch.isfinite(t).all() for t in payload['state_dict'].values()):
        raise ValueError('Invalid model weights')


def save_magpie_checkpoint(path,model,scaler,*,directory,training_updates):
    if type(model) is not MagpieCandidateModel:raise ValueError('Wrong model type')
    payload={**contract(),'width':model.width,'training_updates':training_updates,'scaler':scaler,'state_dict':model.state_dict()}
    validate_payload(payload,directory)
    with open(path,'xb') as stream:torch.save(payload,stream)


def load_magpie_checkpoint(path,*,directory):
    payload=torch.load(path,map_location='cpu',weights_only=True)
    validate_payload(payload,directory)
    model=MagpieCandidateModel(payload['width']);model.load_state_dict(payload['state_dict'],strict=True)
    return model.eval(),payload['scaler'],payload['training_updates']
