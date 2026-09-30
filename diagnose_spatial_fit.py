"""Fixed-budget memorization diagnostic using only existing teacher/train data."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import torch
from luck_agent.evaluation.spatial_dataset import iter_corpus
from luck_agent.evaluation.spatial_batching import SpatialCandidateEncoder, collate_spatial
from luck_agent.evaluation.spatial_preprocessing import scale_spatial_sample
from luck_agent.agents.spatial_model import load_spatial_checkpoint, save_spatial_checkpoint, spatial_tensors
from luck_agent.agents.candidate_model import masked_bc_loss
from train_spatial_bc_smoke import offline


def sample_group(sample):
    """Disjoint groups; synergy takes priority over deck size, independent of errors."""
    if sample['metadata']['decision_type'] != 'symbol':
        return None
    action = sample['metadata']['actions'][sample['label']]
    enc = SpatialCandidateEncoder()
    counts = Counter(row[0] for row in sample['deck'])
    if action['action_type'] == 0:
        target = action['target_id']
        if target == 'mouse' and counts[enc.symbols['cheese']]:
            return 'mouse_with_cheese'
        if target == 'cheese' and counts[enc.symbols['mouse']]:
            return 'cheese_with_mouse'
    return 'deck_18_19' if len(sample['deck']) in (18, 19) else 'other_symbol'


def select_samples(samples, per_group=32):
    groups = {k: [] for k in ('mouse_with_cheese', 'cheese_with_mouse', 'deck_18_19', 'other_symbol')}
    seen = set()
    for sample in samples:
        key = (sample['metadata']['seed'], sample['metadata']['step'])
        if key in seen:
            raise ValueError('Duplicate sample identity')
        seen.add(key)
        group = sample_group(sample)
        if group is not None and len(sample['candidates']) > 1:
            rank = hashlib.sha256(f'v069:{key[0]}:{key[1]}'.encode()).hexdigest()
            groups[group].append((rank, key, sample))
    selected, index = [], []
    for group, rows in groups.items():
        if len(rows) < per_group:
            raise ValueError('Insufficient group coverage: ' + group)
        for _, key, sample in sorted(rows, key=lambda row: (row[0], row[1]))[:per_group]:
            selected.append(sample)
            index.append({'seed': key[0], 'step': key[1], 'group': group})
    return selected, index


def main():
    directory = 'logs/spatial-dataset-v063'
    source = Path('logs/spatial-bc-v066/final.pt')
    parent = json.loads(Path('logs/spatial-bc-v066/results.json').read_text())
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if digest != parent['final_checkpoint_sha256']:
        raise ValueError('Frozen checkpoint changed')
    out = Path('logs/spatial-fit-v069')
    out.mkdir(exist_ok=False)
    protocol = {'source_checkpoint_sha256': digest, 'dataset': directory, 'policies': ['heuristic'],
                'split': 'train', 'per_group': 32, 'updates': 400, 'batch_size': 128,
                'learning_rate': 0.001, 'gradient_clip': 1, 'seed': 69,
                'selection': 'sha256(v069:seed:step), disjoint groups, independent of model errors',
                'purpose': 'memorization only; no generalization or policy promotion claim'}
    (out/'protocol.json').write_text(json.dumps(protocol, indent=2))
    (out/'driver.py').write_bytes(Path(__file__).read_bytes())
    torch.set_num_threads(1)
    torch.manual_seed(protocol['seed'])
    model, scaler = load_spatial_checkpoint(source, directory=directory, policies=['heuristic'])
    selected, index = select_samples(iter_corpus(directory, split='train', policies=['heuristic']))
    # Freeze selection before computing any predictions or fitting.
    (out/'selection.json').write_text(json.dumps(index, indent=2))
    samples = [scale_spatial_sample(s, scaler) for s in selected]
    def metrics():
        return {'all': offline(model, samples, 128), **{
            group: offline(model, [s for s, row in zip(samples, index) if row['group'] == group], 128)
            for group in sorted({row['group'] for row in index})}}
    history = [{'updates': 0, 'metrics': metrics()}]
    batch = collate_spatial(samples)
    tensors = spatial_tensors(batch)
    labels = torch.tensor(batch['label'])
    optimizer = torch.optim.Adam(model.parameters(), lr=protocol['learning_rate'])
    for update in range(1, protocol['updates']+1):
        model.train()
        optimizer.zero_grad(set_to_none=True)
        loss = masked_bc_loss(model(tensors), labels, tensors['candidates_mask'])
        if loss is None or not torch.isfinite(loss):
            raise ValueError('Invalid loss')
        loss.backward()
        norm = torch.nn.utils.clip_grad_norm_(model.parameters(), protocol['gradient_clip'])
        if not torch.isfinite(norm):
            raise ValueError('Nonfinite gradient')
        optimizer.step()
        if update % 100 == 0:
            history.append({'updates': update, 'metrics': metrics()})
            print(json.dumps(history[-1]), flush=True)
    checkpoint = out/'diagnostic.pt'
    save_spatial_checkpoint(checkpoint, model, scaler, directory=directory, policies=['heuristic'],
                            training_updates=parent['training_updates']+protocol['updates'])
    restored, _ = load_spatial_checkpoint(checkpoint, directory=directory, policies=['heuristic'])
    model.eval()
    with torch.no_grad():
        if not torch.equal(model(tensors), restored(tensors)):
            raise ValueError('Reload mismatch')
    if hashlib.sha256(source.read_bytes()).hexdigest() != digest:
        raise ValueError('Source model mutated')
    results = {'protocol': protocol, 'history': history, 'reload_exact': True,
               'selection_sha256': hashlib.sha256((out/'selection.json').read_bytes()).hexdigest(),
               'dataset_manifest_sha256': hashlib.sha256((Path(directory)/'manifest.json').read_bytes()).hexdigest(),
               'checkpoint_sha256': hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
               'default_policy_changed': False}
    (out/'results.json').write_text(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
