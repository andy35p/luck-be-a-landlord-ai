"""Separate vocabulary contract: never reinterpret existing BC checkpoints."""
from luck_agent.env.instance_magpie_engine import magpie_catalog
from luck_agent.env.rule_engine import load_catalog
from luck_agent.evaluation.spatial_batching import SpatialCandidateEncoder
from luck_agent.evaluation.batching import collate


class MagpieCandidateEncoder(SpatialCandidateEncoder):
    version='magpie-spatial-candidates-v1'

    def __init__(self):
        catalog=magpie_catalog(load_catalog())
        self.symbols={s:i+1 for i,s in enumerate(sorted(catalog['symbol_pool']))}
        self.items={s:i+1 for i,s in enumerate(sorted(catalog['item_pool']))}

    @staticmethod
    def features(sample):
        if sample.get('encoder_version')!=MagpieCandidateEncoder.version:
            raise ValueError('Magpie encoder version mismatch')
        return {**{k:sample[k] for k in ('scalars','deck','items','candidates','board','board_mask','board_observed')},
                'candidate_mask':[True]*len(sample['candidates'])}


def collate_magpie(samples):
    if not samples or any(s.get('encoder_version')!=MagpieCandidateEncoder.version for s in samples):
        raise ValueError('Expected homogeneous magpie batch')
    batch=collate(samples);batch['encoder_version']=MagpieCandidateEncoder.version
    for key in ('board','board_mask','board_observed'):batch[key]=[s[key] for s in samples]
    return batch
