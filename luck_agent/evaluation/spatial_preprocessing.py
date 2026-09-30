"""Frozen training-only scalar normalization for the spatial encoder."""
import hashlib
import math
from pathlib import Path
from luck_agent.evaluation.spatial_batching import SpatialCandidateEncoder,collate_spatial
from luck_agent.evaluation.spatial_dataset import iter_corpus
from luck_agent.evaluation.preprocessing import scale_sample,shuffled


def manifest_hash(directory):
    return hashlib.sha256((Path(directory)/'manifest.json').read_bytes()).hexdigest()


def fit_spatial_scaler(directory, *, policies):
    fields=list(SpatialCandidateEncoder.scalar_fields)
    n=0;mean=[0.0]*len(fields);m2=[0.0]*len(fields)
    for sample in iter_corpus(directory,split='train',policies=policies):
        values=sample['scalars']
        if len(values)!=len(fields) or not all(math.isfinite(x) for x in values):
            raise ValueError('Invalid scalar input')
        n+=1
        for i,x in enumerate(values):
            delta=x-mean[i];mean[i]+=delta/n;m2[i]+=delta*(x-mean[i])
    if not n:raise ValueError('No training samples')
    return {'version':'spatial-train-zscore-v1','encoder':SpatialCandidateEncoder.version,
            'manifest_sha256':manifest_hash(directory),'fit_split':'train',
            'policies':sorted(policies),'samples':n,'fields':fields,'mean':mean,
            'scale':[math.sqrt(v/n) if v/n>1e-12 else 1.0 for v in m2]}


def validate_spatial_scaler(scaler,directory,policies):
    fields=list(SpatialCandidateEncoder.scalar_fields)
    if (scaler.get('version')!='spatial-train-zscore-v1' or scaler.get('encoder')!=SpatialCandidateEncoder.version
            or scaler.get('fit_split')!='train' or scaler.get('fields')!=fields
            or scaler.get('policies')!=sorted(policies) or not policies or len(set(policies))!=len(policies)
            or scaler.get('manifest_sha256')!=manifest_hash(directory)
            or type(scaler.get('samples')) is not int or scaler['samples']<=0):
        raise ValueError('Spatial scaler provenance mismatch')
    if (len(scaler['mean'])!=len(fields) or len(scaler['scale'])!=len(fields)
            or not all(math.isfinite(x) for x in scaler['mean'])
            or not all(math.isfinite(x) and x>0 for x in scaler['scale'])):
        raise ValueError('Invalid spatial scaler statistics')


def scale_spatial_sample(sample,scaler):
    if (sample.get('encoder_version')!=SpatialCandidateEncoder.version
            or scaler.get('encoder')!=SpatialCandidateEncoder.version
            or len(sample['scalars'])!=len(SpatialCandidateEncoder.scalar_fields)
            or len(scaler['mean'])!=len(sample['scalars']) or len(scaler['scale'])!=len(sample['scalars'])):
        raise ValueError('Spatial scalar shape/version mismatch')
    return scale_sample(sample,scaler)


def iter_spatial_batches(directory, *, split, policies, scaler, batch_size=64, shuffle_seed=None,epoch=0):
    if type(batch_size) is not int or batch_size<=0:raise ValueError('Positive batch size required')
    validate_spatial_scaler(scaler,directory,policies)
    samples=iter_corpus(directory,split=split,policies=policies)
    if shuffle_seed is not None:
        if split!='train':raise ValueError('Only training may be shuffled')
        samples=shuffled(samples,shuffle_seed,epoch)
    pending=[]
    for sample in samples:
        pending.append(scale_spatial_sample(sample,scaler))
        if len(pending)==batch_size:
            yield collate_spatial(pending);pending=[]
    if pending:yield collate_spatial(pending)
