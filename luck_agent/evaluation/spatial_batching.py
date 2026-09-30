"""Versioned goldfish observations; last board is a pre-resolution snapshot."""
from luck_agent.env.instance_goldfish_engine import goldfish_catalog
from luck_agent.env.rule_engine import load_catalog
from luck_agent.evaluation.batching import CandidateEncoder, collate
from luck_agent.evaluation.dataset import read_episodes, split_for_seed


class SpatialCandidateEncoder(CandidateEncoder):
    version = 'goldfish-spatial-candidates-v1'

    def __init__(self):
        catalog=goldfish_catalog(load_catalog())
        self.symbols={s:i+1 for i,s in enumerate(sorted(catalog['symbol_pool']))}
        self.items={s:i+1 for i,s in enumerate(sorted(catalog['item_pool']))}

    def encode_observation(self,state,actions):
        sample=super().encode_observation(state,actions)
        if len({(a['action_type'],a['target_id'],a['secondary_target_id']) for a in actions})!=len(actions):
            raise ValueError('Duplicate action candidates')
        cells=state['visible_board_cells']
        snapshots=state['visible_board_instances']
        by_id={s['instance_id']:s for s in snapshots}
        occupied=[uid for uid in cells if uid is not None]
        if (len(cells) not in (0,20) or len(by_id)!=len(snapshots)
                or len(set(occupied))!=len(occupied) or set(occupied)!=set(by_id)):
            raise ValueError('Inconsistent board snapshot identities')
        ids={s['instance_id']:i+1 for i,s in enumerate(state['symbols'])}
        board=[]
        for uid in cells or [None]*20:
            if uid is None:
                board.append([0,0,0,0,0]);continue
            s=by_id[uid]
            board.append([self.symbols[s['symbol_id']],s['permanent_bonus'],
                          s['remaining_appearances'] or 0,int(s['remaining_appearances'] is not None),
                          ids.get(uid,0)])
        sample.update(encoder_version=self.version,board=board,
                      board_mask=[row[0]!=0 for row in board],board_observed=bool(cells))
        return sample

    @staticmethod
    def features(sample):
        if sample.get('encoder_version')!=SpatialCandidateEncoder.version:
            raise ValueError('Spatial encoder version mismatch')
        return {**{k:sample[k] for k in ('scalars','deck','items','candidates','board','board_mask','board_observed')},
                'candidate_mask':[True]*len(sample['candidates'])}


def collate_spatial(samples):
    if not samples or any(s.get('encoder_version')!=SpatialCandidateEncoder.version for s in samples):
        raise ValueError('Expected a homogeneous spatial batch')
    batch=collate(samples)
    batch['encoder_version']=SpatialCandidateEncoder.version
    for key in ('board','board_mask','board_observed'):
        batch[key]=[s[key] for s in samples]
    return batch


def iter_spatial_samples(path, *, split):
    if split not in {'train','validation','test'}:
        raise ValueError('Explicit seed-group split required')
    encoder=SpatialCandidateEncoder()
    for header,episode in read_episodes(path):
        if header['config'].get('rule_version')!='instance-goldfish-v1':
            raise ValueError('Spatial dataset requires instance-goldfish-v1')
        if split_for_seed(episode[0]['episode_seed'])!=split:continue
        for record in episode:
            sample=encoder.encode(record,header['agent'])
            sample['metadata']['policy_config']=dict(header.get('policy_config',{}))
            yield sample
