"""Offline support coverage, deduplicated by decision; never publishes advice."""
import argparse
from collections import Counter
import json
from pathlib import Path

from luck_agent.agents.live_advisor import LiveAdvisor
from luck_agent.evaluation.live_observation import observe_symbol_choice


def audit(paths):
    counts = Counter()
    blockers, symbols, items, candidates = (Counter() for _ in range(4))
    seen = set()
    for path in paths:
        with Path(path).open(encoding='utf-8-sig') as stream:
            for line in stream:
                try:
                    record = json.loads(line)
                    if not isinstance(record, dict): raise ValueError('Record must be an object')
                    counts['records'] += 1
                    if 'test_fixture' in record:
                        counts['controlled_excluded'] += 1
                        continue
                    observed = observe_symbol_choice(record)
                    if not observed['readiness_hint']:
                        counts['not_settled_symbol_choice'] += 1
                        continue
                    state = record['state']
                    # Heartbeats and reopened menus do not create extra decisions.
                    key = json.dumps([record['session_id'], state['progress']['spins'],
                        state['progress']['times_rent_paid'], observed['candidates'],
                        sorted(s['instance_id'] for s in observed['nonempty_symbols'])], sort_keys=True)
                    if key in seen:
                        counts['duplicate_decision_records'] += 1
                        continue
                    result = LiveAdvisor().update(record, fresh=True)
                    # Offline policy-unit evaluation only; never claim record freshness.
                    seen.add(key)
                    counts['unique_symbol_decisions'] += 1
                    counts['policy_ready' if result['status']=='ready' else 'policy_rejected'] += 1
                    blockers.update(result['reasons'])
                    symbols.update(sorted({s['type'] for s in observed['nonempty_symbols'] if s['type'] not in LiveAdvisor.supported}))
                    items.update(sorted({i['type'] for i in state.get('items', [])}))
                    candidates.update(sorted({c for c in observed['candidates'] if c not in LiveAdvisor.supported}))
                except (ValueError, TypeError, KeyError, AttributeError):
                    counts['malformed'] += 1
    return {'scope':'Offline observed-decision coverage; not win rate, independent games, or live freshness',
            'counts':dict(counts), 'blockers':dict(blockers.most_common()),
            'unsupported_inventory_symbols':dict(symbols.most_common()),
            'owned_items':dict(items.most_common()),
            'unsupported_candidates':dict(candidates.most_common())}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('logs',nargs='+',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    result=audit(args.logs)
    text=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    if args.output: args.output.write_text(text,encoding='utf-8')
    print(text)


if __name__=='__main__': main()
