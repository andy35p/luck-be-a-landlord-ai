import unittest
from luck_agent.env.board import InstanceBoard
from luck_agent.env.game_env import GameEnv,EnvConfig
from luck_agent.env.action import Action,ActionType as T


class BoardTests(unittest.TestCase):
    def test_edges_corners_and_no_wrap(self):
        b=InstanceBoard.from_draw([str(i) for i in range(20)])
        self.assertEqual(b.adjacent_cells(0),(1,5,6))
        self.assertEqual(b.adjacent_cells(4),(3,8,9))
        self.assertEqual(b.adjacent_cells(19),(13,14,18))
        self.assertEqual(len(b.adjacent_cells(7)),8)
        self.assertNotIn(5,b.adjacent_cells(4))
        for i in range(20):
            expected=tuple(j for j in range(20) if j!=i and max(abs(i//5-j//5),abs(i%5-j%5))<=1)
            self.assertEqual(b.adjacent_cells(i),expected)

    def test_explicit_empty_cell_does_not_compact(self):
        b=InstanceBoard(('a',None,'b')+(None,)*17)
        self.assertEqual(b.adjacent_ids('a'),())
        self.assertEqual(b.cells[2],'b')
        self.assertEqual(InstanceBoard.from_draw(['a','b']).adjacent_ids('a'),('b',))

    def test_duplicate_and_invalid_cell_rejected(self):
        with self.assertRaises(ValueError):InstanceBoard.from_draw(['a','a'])
        with self.assertRaises(ValueError):InstanceBoard.from_draw([None])
        for cell in (-1,20,True):
            with self.assertRaises(ValueError):InstanceBoard.coordinates(cell)

    def test_resolved_snapshot_keeps_destroyed_and_excludes_generated(self):
        env=GameEnv(EnvConfig(floor=1,rule_version='instance-time-v1'));e=env._engine
        self.assertEqual(env.state.visible_board_cells,())
        e.choose('bar_of_soap');uid=e.instances.snapshot()[-1].instance_id
        e.instances.tick((uid,));e.instances.tick((uid,));e._sync_deck()
        e.pending_instance_ids=(uid,);e.pending_shown=['bar_of_soap']
        state,*_=env.step(Action(T.SPIN))
        self.assertEqual(state.visible_board_cells,(uid,)+(None,)*19)
        self.assertNotIn(uid,{s.instance_id for s in state.symbols})
        bubble=next(s.instance_id for s in state.symbols if s.symbol_id=='bubble')
        self.assertNotIn(bubble,state.visible_board_cells)
        rng=e.rng.getstate();self.assertEqual(env.state.visible_board_cells,state.visible_board_cells)
        self.assertEqual(rng,e.rng.getstate())
        env.reset(0);self.assertEqual(env.state.visible_board_cells,())
