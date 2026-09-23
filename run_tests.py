"""Run preserved rules and new interface tests using only the standard library."""
import sys
import unittest
from pathlib import Path

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root/"luck_agent/legacy"))
suite = unittest.TestSuite()
suite.addTests(unittest.TestLoader().discover(str(root/"luck_agent/legacy"), pattern="test_fast_env.py"))
suite.addTests(unittest.TestLoader().discover(str(root/"tests"), pattern="test_*.py"))
result = unittest.TextTestRunner(verbosity=1).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)
