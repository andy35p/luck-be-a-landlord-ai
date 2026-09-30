import copy
import unittest
from luck_agent.evaluation.live_board import displayed_ids


def snapshot():
    return {'displayed_board':{'width':5,'height':4,'rows':[[str(y*5+x) for x in range(5)] for y in range(4)]},
            'symbols':[{'instance_id':str(n),'grid_position':[0,0]} for n in range(25)]}


class LiveBoardTests(unittest.TestCase):
    def test_explicit_membership_keeps_offboard_inventory(self):
        state=snapshot();before=copy.deepcopy(state)
        self.assertEqual(displayed_ids(state),tuple(str(n) for n in range(20)))
        self.assertEqual(state,before)
        self.assertNotIn('24',displayed_ids(state))

    def test_coordinates_do_not_replace_missing_membership(self):
        state=snapshot();del state['displayed_board']
        with self.assertRaisesRegex(ValueError,'missing_displayed_board'):displayed_ids(state)

    def test_missing_duplicate_and_unknown_identity_rejected(self):
        for value in (None,'','1','unknown'):
            state=snapshot();state['displayed_board']['rows'][0][0]=value
            with self.subTest(value=value),self.assertRaises(ValueError):displayed_ids(state)
        state=snapshot();state['symbols'].append(state['symbols'][0])
        with self.assertRaises(ValueError):displayed_ids(state)

    def test_incomplete_or_changed_board_rejected(self):
        for mutate in (lambda b:b.update(width=6),lambda b:b['rows'].pop(),lambda b:b['rows'][0].pop()):
            state=snapshot();mutate(state['displayed_board'])
            with self.assertRaises(ValueError):displayed_ids(state)
