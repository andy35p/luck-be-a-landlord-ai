"""Formula equivalence only; does not claim native Godot execution."""
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from luck_agent.agents.heuristic_agent import HeuristicAgent

ROOT = Path(__file__).resolve().parents[1] / 'integrations/workshop_probe/package/scripts'


class WorkshopProbeTests(unittest.TestCase):
    def test_native_formulas_match_existing_teacher(self):
        agent = HeuristicAgent()
        for candidate, partner in [('mouse', 'cheese'), ('cheese', 'mouse')]:
            source = (ROOT / f'{candidate}.gd').read_text(encoding='utf-8')
            line = next(line for line in source.splitlines() if line.strip().startswith('value_text = '))
            expr = json.loads(line.split(' = ', 1)[1])['value']
            self.assertEqual(expr['starting_value']['symbols_in_inventory']['type'], partner)
            for count in range(41):
                deck = [partner] * count + ['coin', 'cat']
                value = count
                for operation in expr['var_math']:
                    key, operand = next(iter(operation.items()))
                    self.assertIn(key, ('*', '+'))
                    value = value * operand if key == '*' else value + operand
                view = SimpleNamespace(deck=deck, catalog=agent.catalog)
                self.assertAlmostEqual(value, agent.prior.score_symbol(view, candidate))

    def test_probe_declarations_do_not_add_gameplay_fields(self):
        allowed = {'mod_type', 'type', 'inherit_effects', 'inherit_art',
                   'inherit_groups', 'inherit_description', 'description', 'value_text'}
        for path in ROOT.glob('*.gd'):
            source = path.read_text(encoding='utf-8')
            for line in source.splitlines():
                if ' = ' in line:
                    self.assertIn(line.strip().split(' = ', 1)[0], allowed)
            self.assertEqual(source.count('('), 1)
            self.assertIn('func _init():', source)
            self.assertNotIn('rand_num', source)
