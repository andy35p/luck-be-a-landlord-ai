import importlib.util
import unittest


@unittest.skipUnless(importlib.util.find_spec("torch"), "Optional model environment")
class CoverageTests(unittest.TestCase):
    def test_threshold_bins_and_direction(self):
        from audit_threshold_coverage import tally
        data={}
        tally(data,19,0,1);tally(data,20,1,0);tally(data,19,0,0)
        self.assertEqual(data["19"]["total"],2)
        self.assertEqual(data["19"]["model_skip_teacher_pick"],1)
        self.assertEqual(data["20"]["model_pick_teacher_skip"],1)
        self.assertEqual(data["19"]["teacher_pick"],2)
