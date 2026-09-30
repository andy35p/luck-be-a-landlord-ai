import itertools
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from luck_agent.agents.live_advisor import LiveAdvisor
from tests.test_live_advisor import observation


class LiveScoreReuseTests(unittest.TestCase):
    def test_candidate_scores_computed_once(self):
        advisor=LiveAdvisor()
        with patch.object(advisor.teacher.prior,'score_symbol',wraps=advisor.teacher.prior.score_symbol) as scorer:
            result=advisor.update(observation(),fresh=True)
        self.assertEqual(result['status'],'ready')
        self.assertEqual(scorer.call_count,3)

    def test_all_supported_triples_match_original_at_capacity_boundary(self):
        advisor=LiveAdvisor();sequence=0
        for size in (19,20):
            for candidates in itertools.combinations_with_replacement(sorted(advisor.supported),3):
                sequence+=1;record=observation(sequence)
                record['state']['symbols']=[dict(record['state']['symbols'][0],instance_id=str(i)) for i in range(size)]
                record['state']['cards']=[{'active':True,'data':{'type':s}} for s in candidates]
                result=advisor.update(record,fresh=True)
                if len(set(candidates))<3:
                    # The live observation gate may reject duplicate offers.
                    if result['status']!='ready':continue
                self.assertEqual(result['status'],'ready')
                view=SimpleNamespace(catalog=advisor.teacher.catalog,deck=['cheese']*size,force_add_next_choice=False)
                expected=advisor.teacher.prior.choose_symbol(view,candidates)
                self.assertEqual(result['action']['target_id'],None if expected=='skip' else expected)
