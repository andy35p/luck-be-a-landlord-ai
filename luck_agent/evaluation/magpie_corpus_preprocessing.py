"""Training-only normalization for the magpie engineering corpus."""
import hashlib
import math
from pathlib import Path
from luck_agent.evaluation.magpie_batching import MagpieCandidateEncoder
from luck_agent.evaluation.magpie_corpus import load_corpus_samples
from luck_agent.evaluation.preprocessing import scale_sample


def fit_corpus_scaler(directory):
    fields=list(MagpieCandidateEncoder.scalar_fields)
    mean=[0.0]*len(fields);m2=[0.0]*len(fields);n=0
    for sample in load_corpus_samples(directory,split='train'):
        values=sample['scalars']
        if sample['metadata']['split']!='train' or len(values)!=len(fields) or not all(math.isfinite(x) for x in values):
            raise ValueError('Invalid training scalar sample')
        n+=1
        for i,x in enumerate(values):
            delta=x-mean[i];mean[i]+=delta/n;m2[i]+=delta*(x-mean[i])
    if not n:raise ValueError('Empty training data')
    return {'version':'magpie-corpus-zscore-v1','encoder':MagpieCandidateEncoder.version,
            'manifest_sha256':hashlib.sha256((Path(directory)/'manifest.json').read_bytes()).hexdigest(),
            'fit_split':'train','samples':n,'fields':fields,'mean':mean,
            'scale':[math.sqrt(v/n) if v/n>1e-12 else 1.0 for v in m2]}


def validate_corpus_scaler(scaler,directory):
    # Fixed development corpus: recompute rather than trust editable moments.
    if scaler!=fit_corpus_scaler(directory):raise ValueError('Scaler data provenance or moments mismatch')


def scale_corpus_sample(sample,scaler):
    width=len(MagpieCandidateEncoder.scalar_fields)
    if (sample.get('encoder_version')!=MagpieCandidateEncoder.version
            or scaler.get('version')!='magpie-corpus-zscore-v1'
            or scaler.get('encoder')!=MagpieCandidateEncoder.version
            or len(sample['scalars'])!=width or len(scaler['mean'])!=width or len(scaler['scale'])!=width
            or not all(math.isfinite(x) for x in scaler['mean'])
            or not all(math.isfinite(x) and x>0 for x in scaler['scale'])):
        raise ValueError('Invalid magpie normalization contract')
    return scale_sample(sample,scaler)
