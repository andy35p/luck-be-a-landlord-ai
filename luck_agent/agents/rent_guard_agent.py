"""Experimental coal scoring gate for the bounded goldfish backend only."""
from luck_agent.agents.heuristic_agent import HeuristicAgent


class RentGuardAgent(HeuristicAgent):
    persistent = frozenset({'coin','pearl','cherry','flower','cat','mouse','goldfish','diamond'})

    def __init__(self, catalog):
        if catalog.get('catalog_source') != 'recovered_catalog:instance-goldfish-v1-subset':
            raise ValueError('Rent guard is scoped to instance-goldfish-v1')
        super().__init__(catalog)
        self.no_coal_bonus = HeuristicAgent(catalog,coal_score_adjustment=-1.2)

    def projected_cash(self, state):
        """Lower bound after adding coal, conditional on no further deck edits.

        Ignore transient payouts and all synergy. Count every potential soap
        child immediately as zero to allow for future board dilution.
        This is a scoring estimate, not a survival guarantee for future picks.
        """
        if not state.supports_stable_instances:
            raise ValueError('Stable instances required')
        horizon=state.spins_until_rent
        values=[self.catalog['symbol_values'][s.symbol_id]+(s.permanent_bonus or 0)
                if s.symbol_id in self.persistent else 0 for s in state.symbols]
        births=sum(min(horizon,s.remaining_appearances or 0) for s in state.symbols
                   if s.symbol_id=='bar_of_soap')
        values.extend([0]*(1+births))  # Candidate coal and possible new bubbles.
        per_spin=sum(sorted(values)[:20])
        return state.coins+horizon*per_spin

    def choose(self,state,actions):
        if (state.decision_type in {'symbol','forced_symbol'} and 'coal' in state.candidates
                and self.projected_cash(state)<state.current_rent):
            return self.no_coal_bonus.choose(state,actions)
        return super().choose(state,actions)
