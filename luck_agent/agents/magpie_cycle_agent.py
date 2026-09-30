"""Experimental rent-horizon magpie preference; no live or training default."""
from luck_agent.agents.heuristic_agent import HeuristicAgent
from luck_agent.legacy.fast_env import HeuristicAgent as PriorHeuristic


def fresh_magpie_score(spins, deck_size):
    """Expected income per appearance before rent under fixed independent draws.

    Existing inventory size is before adding the candidate. This approximation
    excludes deck changes, other choices, rent survival and capacity opportunity
    costs. It is a preference comparable with base-value teacher scores, not Q.
    """
    if type(spins) is not int or not 0 <= spins <= 10000:
        raise ValueError('Invalid spin horizon')
    if type(deck_size) is not int or deck_size < 0:
        raise ValueError('Invalid inventory size')
    if spins == 0: return -1.0
    probability=min(1.0,20/(deck_size+1))
    phase=[1.0,0.0,0.0,0.0]
    income=0.0
    for _ in range(spins):
        income += -probability+9*phase[3]*probability
        phase=[phase[i]*(1-probability)+phase[(i-1)%4]*probability for i in range(4)]
    return income/(spins*probability)


class CyclePrior(PriorHeuristic):
    magpie_score=-2.0

    def score_symbol(self, env, candidate):
        return self.magpie_score if candidate=='magpie' else super().score_symbol(env,candidate)


class MagpieCycleAgent(HeuristicAgent):
    def __init__(self,catalog):
        if catalog.get('catalog_source') != 'recovered_catalog:instance-magpie-v1-subset':
            raise ValueError('Cycle experiment requires instance-magpie-v1')
        super().__init__(catalog)
        self.prior=CyclePrior()

    def choose(self,state,actions):
        self.prior.magpie_score=fresh_magpie_score(state.spins_until_rent,len(state.symbols))
        return super().choose(state,actions)
