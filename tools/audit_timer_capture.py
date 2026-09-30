"""Check whether captured timer state can be read without guessing from UI text."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from luck_agent.evaluation.live_timer_state import parse_timer

TIMED_SYMBOLS = frozenset({'snail','turtle','sloth','magpie','robin_hood','owl','gambler','thief'})


def audit(paths):
    counts = Counter()
    missing = Counter()
    instances = set()
    values = {}
    parse_rejections = Counter()
    for path in paths:
        for line in Path(path).read_text(encoding='utf-8').splitlines():
            try:
                record = json.loads(line)
                symbols = record['state']['symbols']
                if not isinstance(symbols, list): raise ValueError('symbols must be a list')
            except (ValueError, TypeError, KeyError):
                counts['malformed_records'] += 1
                continue
            counts['records'] += 1
            for symbol in symbols:
                if not isinstance(symbol, dict) or not isinstance(symbol.get('type'), str) or symbol['type'] not in TIMED_SYMBOLS:
                    continue
                counts['timed_symbol_observations'] += 1
                key = (record.get('session_id'), symbol.get('instance_id'))
                instances.add(key)
                required = ('times_displayed','values','modded','inherit_effects')
                absent = [field for field in required if field not in symbol]
                missing.update(absent)
                if absent:
                    counts['missing_timer_state'] += 1
                    continue
                if (type(symbol['times_displayed']) is not int or symbol['times_displayed'] < 0
                        or not isinstance(symbol['values'], list)
                        or any(type(v) not in (int,float) for v in symbol['values'])
                        or type(symbol['modded']) is not bool
                        or type(symbol['inherit_effects']) is not bool):
                    counts['invalid_timer_state'] += 1
                    continue
                counts['readable_timer_state'] += 1
                values.setdefault(key, set()).add(symbol['times_displayed'])
                try:
                    parse_timer(symbol)
                except ValueError as error:
                    parse_rejections[str(error)] += 1
                else:
                    counts['verified_format_timer_state'] += 1
    return {'scope':'Field availability only; changes do not prove correct timer transitions or symbol support',
            'counts':dict(counts), 'missing_fields':dict(missing), 'unique_instances':len(instances),
            'format_rejections':dict(parse_rejections),
            'instances_with_multiple_timer_values':sum(len(v)>1 for v in values.values())}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('logs', nargs='+', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = json.dumps(audit(args.logs),indent=2)+'\n'
    if args.output: args.output.write_text(result,encoding='utf-8')
    print(result)


if __name__ == '__main__': main()
