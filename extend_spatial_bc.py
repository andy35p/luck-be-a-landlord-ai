"""Prespecified full-training-set extension of V066; never trains on V069 weights."""
from collections import Counter
import hashlib
import json
from pathlib import Path
from random import Random
import torch
from diagnose_spatial_fit import sample_group
from train_spatial_bc_smoke import offline, online
from luck_agent.agents.spatial_model import load_spatial_checkpoint, save_spatial_checkpoint, spatial_tensors
from luck_agent.agents.candidate_model import masked_bc_loss
from luck_agent.evaluation.spatial_dataset import iter_corpus
from luck_agent.evaluation.spatial_batching import collate_spatial
from luck_agent.evaluation.spatial_preprocessing import scale_spatial_sample


def grouped_metrics(model, samples, batch_size=64):
    """Exact labels plus directional skip errors; groups overlap only in deck diagnostic."""
    groups = {'all': samples}
    for sample in samples:
        group = sample_group(sample)
        if group is not None:
            groups.setdefault(group, []).append(sample)
        if sample['metadata']['decision_type'] == 'symbol' and len(sample['deck']) in (18, 19):
            groups.setdefault('all_symbol_deck_18_19', []).append(sample)
    result = {}
    model.eval()
    for group, rows in groups.items():
        metrics = offline(model, rows, batch_size)
        counts = Counter()
        with torch.no_grad():
            for start in range(0, len(rows), batch_size):
                part = rows[start:start+batch_size]
                logits = model(spatial_tensors(collate_spatial(part)))
                for sample, prediction in zip(part, logits.argmax(1).tolist()):
                    actions = sample['metadata']['actions']
                    expected, chosen = actions[sample['label']], actions[prediction]
                    if sample['metadata']['decision_type'] != 'symbol':
                        continue
                    counts['symbol_decisions'] += 1
                    if expected['action_type'] == 0:
                        counts['teacher_picks'] += 1
                        if chosen['action_type'] == 1:
                            counts['model_skips_teacher_pick'] += 1
                    elif expected['action_type'] == 1:
                        counts['teacher_skips'] += 1
                        if chosen['action_type'] == 0:
                            counts['model_picks_teacher_skip'] += 1
        result[group] = {**metrics, **dict(counts)}
    return result


def main():
    spec_path = Path('configs/v070_spatial_extension.json')
    spec = json.loads(spec_path.read_text())
    source = Path(spec['source_checkpoint'])
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if digest != spec['source_checkpoint_sha256']:
        raise ValueError('Source checkpoint changed')
    parent = json.loads(Path('logs/spatial-bc-v066/results.json').read_text())
    if digest != parent['final_checkpoint_sha256']:
        raise ValueError('Parent run mismatch')
    out = Path('logs/spatial-extension-v070')
    out.mkdir(exist_ok=False)
    (out/'protocol.json').write_bytes(spec_path.read_bytes())
    (out/'driver.py').write_bytes(Path(__file__).read_bytes())
    torch.set_num_threads(1)
    torch.manual_seed(spec['shuffle_seed'])
    model, scaler = load_spatial_checkpoint(source, directory=spec['dataset'], policies=spec['policies'])
    partitions = {split: [scale_spatial_sample(s, scaler)
        for s in iter_corpus(spec['dataset'], split=split, policies=spec['policies'])
        if len(s['candidates']) > 1] for split in ('train', 'validation')}
    train = partitions['train']
    if not train:
        raise ValueError('Empty training set')
    def metrics():
        return {split: grouped_metrics(model, samples, spec['batch_size'])
                for split, samples in partitions.items()}
    history = [{'additional_epochs': 0, 'additional_updates': 0, 'metrics': metrics()}]
    optimizer = torch.optim.Adam(model.parameters(), lr=spec['learning_rate'])
    updates = 0
    for epoch in range(spec['additional_epochs']):
        order = list(range(len(train)))
        Random(spec['shuffle_seed']+epoch).shuffle(order)
        model.train()
        for start in range(0, len(order), spec['batch_size']):
            batch = collate_spatial([train[i] for i in order[start:start+spec['batch_size']]])
            tensors = spatial_tensors(batch)
            optimizer.zero_grad(set_to_none=True)
            loss = masked_bc_loss(model(tensors), torch.tensor(batch['label']), tensors['candidates_mask'])
            if loss is None or not torch.isfinite(loss):
                raise ValueError('Invalid loss')
            loss.backward()
            norm = torch.nn.utils.clip_grad_norm_(model.parameters(), spec['gradient_clip'])
            if not torch.isfinite(norm):
                raise ValueError('Nonfinite gradient')
            optimizer.step()
            updates += 1
        entry = {'additional_epochs': epoch+1, 'additional_updates': updates, 'metrics': metrics()}
        history.append(entry)
        print(json.dumps({'epoch': epoch+1, 'updates': updates,
            'train': entry['metrics']['train']['all'], 'validation': entry['metrics']['validation']['all']}), flush=True)
    checkpoint = out/'final.pt'
    save_spatial_checkpoint(checkpoint, model, scaler, directory=spec['dataset'], policies=spec['policies'],
                            training_updates=parent['training_updates']+updates)
    restored, _ = load_spatial_checkpoint(checkpoint, directory=spec['dataset'], policies=spec['policies'])
    probe = spatial_tensors(collate_spatial(partitions['validation'][:64]))
    model.eval()
    with torch.no_grad():
        if not torch.equal(model(probe), restored(probe)):
            raise ValueError('Reload mismatch')
    baseline, _ = load_spatial_checkpoint(source, directory=spec['dataset'], policies=spec['policies'])
    baseline_rows = online(baseline, scaler, spec)
    if baseline_rows != parent['online_rows']['trained']:
        raise ValueError('Original online baseline did not reproduce')
    rows = online(restored, scaler, spec)
    if any(row['truncated'] for row in rows):
        raise ValueError('Incomplete online episodes')
    if hashlib.sha256(source.read_bytes()).hexdigest() != digest:
        raise ValueError('Original model mutated')
    result = {'protocol': spec, 'history': history, 'additional_updates': updates,
              'cumulative_updates': parent['training_updates']+updates,
              'reload_exact': True, 'baseline_online_exact': True,
              'online_rows': {'baseline': baseline_rows, 'extended': rows},
              'online_summary': {name: {'mean_stage': sum(r['stage'] for r in run)/len(run),
                  'wins': sum(r['won'] for r in run), 'truncated': sum(r['truncated'] for r in run)}
                  for name, run in [('baseline', baseline_rows), ('extended', rows)]},
              'checkpoint_sha256': hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
              'dataset_manifest_sha256': hashlib.sha256((Path(spec['dataset'])/'manifest.json').read_bytes()).hexdigest(),
              'default_policy_changed': False}
    (out/'results.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result['online_summary']), flush=True)


if __name__ == '__main__':
    main()
