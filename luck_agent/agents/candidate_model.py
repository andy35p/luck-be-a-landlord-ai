"""Small shared candidate scorer; no fixed global action output layer."""
import torch
from torch import nn
from torch.nn import functional as F
from luck_agent.evaluation.batching import CandidateEncoder


def tensor_batch(batch):
    return {key: torch.tensor(batch[key], dtype=torch.bool if key.endswith("_mask") else torch.float32)
            for key in ("scalars", "deck", "items", "candidates", "deck_mask", "items_mask", "candidates_mask")}


class CandidateModel(nn.Module):
    def __init__(self, width=16, *, deck_count=False):
        super().__init__()
        encoder = CandidateEncoder()
        self.symbol = nn.Embedding(len(encoder.symbols)+1, width, padding_idx=0)
        self.item = nn.Embedding(len(encoder.items)+1, width, padding_idx=0)
        self.action = nn.Embedding(11, width, padding_idx=0)
        self.instance = nn.Linear(width+3, width)
        self.head = nn.Sequential(nn.Linear(8+6*width, 64), nn.ReLU(), nn.Linear(64, 1))
        self.deck_count = deck_count
        if deck_count:
            old = self.head[0]
            extended = nn.Linear(old.in_features+1, old.out_features)
            with torch.no_grad():
                extended.weight[:, :-1].copy_(old.weight)
                extended.weight[:, -1].zero_()
                extended.bias.copy_(old.bias)
            self.head[0] = extended

    @staticmethod
    def count_feature(batch):
        return batch["deck_mask"].sum(1, keepdim=True).float()/20.0

    def forward(self, batch):
        deck, candidates = batch["deck"], batch["candidates"].long()
        instances = self.instance(torch.cat((self.symbol(deck[..., 0].long()), deck[..., 1:]), dim=-1))
        def pool(values, mask):
            return (values*mask.unsqueeze(-1)).sum(1)/mask.sum(1, keepdim=True).clamp_min(1)
        context = torch.cat((batch["scalars"], pool(instances, batch["deck_mask"]),
                             pool(self.item(batch["items"].long()), batch["items_mask"])), dim=-1)
        # Pointer 0 means no instance target; actual pointers address deck rows.
        padded = torch.cat((instances.new_zeros(instances.shape[0], 1, instances.shape[2]), instances), dim=1)
        target = padded.gather(1, candidates[..., 3].unsqueeze(-1).expand(-1, -1, instances.shape[2]))
        features = torch.cat((context.unsqueeze(1).expand(-1, candidates.shape[1], -1),
                              self.action(candidates[..., 0]), self.symbol(candidates[..., 1]),
                              self.item(candidates[..., 2]), target), dim=-1)
        if self.deck_count:
            features = torch.cat((features, self.count_feature(batch).unsqueeze(1).expand(-1, candidates.shape[1], -1)), dim=-1)
        logits = self.head(features).squeeze(-1)
        return logits.masked_fill(~batch["candidates_mask"], float("-inf"))


def masked_bc_loss(logits, labels, mask):
    labels = labels.long()
    if logits.ndim != 2 or logits.shape != mask.shape or labels.shape != (logits.shape[0],):
        raise ValueError("Invalid batch shapes")
    if not torch.all((labels >= 0) & (labels < logits.shape[1])):
        raise ValueError("Label out of bounds")
    if not torch.all(mask.gather(1, labels[:, None])) or not torch.isfinite(logits[mask]).all():
        raise ValueError("Illegal label or nonfinite legal logits")
    decisions = mask.sum(1) > 1
    if not decisions.any(): return None
    return F.cross_entropy(logits[decisions].masked_fill(~mask[decisions], float("-inf")), labels[decisions])


class TorchScorer:
    def __init__(self, model):
        self.model = model.eval()

    def __call__(self, features):
        batch = {key: [features[key]] for key in ("scalars", "deck", "items", "candidates")}
        batch.update(deck_mask=[[True]*len(features["deck"])], items_mask=[[True]*len(features["items"])],
                     candidates_mask=[features["candidate_mask"]])
        with torch.no_grad():
            return self.model(tensor_batch(batch))[0].tolist()
