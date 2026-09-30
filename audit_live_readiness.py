"""Audit source-informed readiness without guessing absent input context."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from luck_agent.evaluation.live_observation import observe_symbol_choice


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    counts, blockers = Counter(), Counter()
    files = []
    for path in sorted(Path(args.directory).glob('*.jsonl')):
        raw = path.read_bytes()
        files.append({'name': path.name, 'sha256': hashlib.sha256(raw).hexdigest()})
        for line in raw.splitlines():
            if not line.strip(): continue
            record = json.loads(line)
            if record.get('kind') != 'observation' or record.get('state', {}).get('prompt', {}).get('type') != 'add_tile':
                continue
            result = observe_symbol_choice(record)
            counts['ordinary_choice_observations'] += 1
            blockers.update(result['blockers'])
            if result['readiness_hint']: counts['ready_hints'] += 1
            if result['blockers'] and all(b.startswith('input_context_') for b in result['blockers']):
                counts['blocked_only_by_input_context'] += 1
    report = {'counts': dict(counts), 'blocker_counts': dict(blockers), 'files': files,
              'recommendations_generated': 0, 'game_actions_submitted': 0,
              'limits': 'Historical observations only; no missing context inferred; not live validation.'}
    with Path(args.output).open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
    print(json.dumps({'counts': report['counts'], 'blockers': report['blocker_counts']}))


if __name__ == '__main__': main()
