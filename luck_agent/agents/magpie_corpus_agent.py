"""Data-bound multi-episode research model adapter."""
from luck_agent.agents.magpie_agent import MagpieModelAgent
from luck_agent.agents.magpie_corpus_checkpoint import load_corpus_checkpoint
from luck_agent.evaluation.magpie_corpus_preprocessing import scale_corpus_sample


class MagpieCorpusAgent(MagpieModelAgent):
    checkpoint_loader=staticmethod(load_corpus_checkpoint)
    scale=staticmethod(scale_corpus_sample)
