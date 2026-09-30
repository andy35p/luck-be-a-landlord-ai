"""Small candidate scorer with ordered last-board context, not a trained policy."""
import torch
from torch import nn
from luck_agent.evaluation.spatial_batching import SpatialCandidateEncoder
from luck_agent.evaluation.spatial_preprocessing import validate_spatial_scaler


def spatial_tensors(batch, *, expected_version=SpatialCandidateEncoder.version):
    if batch.get('encoder_version')!=expected_version:
        raise ValueError('Spatial batch version mismatch')
    keys=('scalars','deck','items','candidates','board','deck_mask','items_mask','candidates_mask','board_mask','board_observed')
    tensors={k:torch.tensor(batch[k],dtype=torch.bool if k.endswith('_mask') else torch.float32) for k in keys}
    n=len(batch['scalars'])
    for k,width in [('deck',4),('candidates',4),('board',5)]:
        tensors[k]=tensors[k].reshape(n,-1,width)
    if tensors['board'].shape[1]!=20:raise ValueError('Expected 20 board cells')
    return tensors


class SpatialCandidateModel(nn.Module):
    version='spatial-mlp-v1'
    encoder_class=SpatialCandidateEncoder

    def __init__(self,width=16):
        super().__init__();self.width=width;enc=self.encoder_class()
        self.symbol=nn.Embedding(len(enc.symbols)+1,width,padding_idx=0)
        self.item=nn.Embedding(len(enc.items)+1,width,padding_idx=0)
        self.action=nn.Embedding(11,width,padding_idx=0)
        self.instance=nn.Linear(width+3,width)
        self.board_cell=nn.Sequential(nn.Linear(2*width+3,width),nn.ReLU())
        self.head=nn.Sequential(nn.Linear(26*width+10,64),nn.ReLU(),nn.Linear(64,1))

    @staticmethod
    def pool(values,mask):
        return (values*mask.unsqueeze(-1)).sum(1)/mask.sum(1,keepdim=True).clamp_min(1)

    def forward(self,b):
        deck=b['deck'];cand=b['candidates'].long();board=b['board']
        instances=self.instance(torch.cat((self.symbol(deck[...,0].long()),deck[...,1:]),-1))
        instances=instances*b['deck_mask'].unsqueeze(-1)
        padded=torch.cat((instances.new_zeros(instances.shape[0],1,self.width),instances),1)
        def pointed(indices):return padded.gather(1,indices.long().unsqueeze(-1).expand(-1,-1,self.width))
        cells=self.board_cell(torch.cat((self.symbol(board[...,0].long()),board[...,1:4],pointed(board[...,4])),-1))
        cells=cells*b['board_mask'].unsqueeze(-1)
        context=torch.cat((b['scalars'],self.pool(instances,b['deck_mask']),
                           self.pool(self.item(b['items'].long()),b['items_mask']),cells.flatten(1),
                           b['deck_mask'].sum(1,keepdim=True).float()/20,
                           b['board_observed'].reshape(-1,1)),1)
        x=torch.cat((context.unsqueeze(1).expand(-1,cand.shape[1],-1),self.action(cand[...,0]),
                     self.symbol(cand[...,1]),self.item(cand[...,2]),pointed(cand[...,3])),-1)
        return self.head(x).squeeze(-1).masked_fill(~b['candidates_mask'],float('-inf'))


class SpatialTorchScorer:
    def __init__(self,model):self.model=model.eval()
    def __call__(self,features):
        batch={k:[features[k]] for k in ('scalars','deck','items','candidates','board','board_mask','board_observed')}
        batch.update(encoder_version=SpatialCandidateEncoder.version,deck_mask=[[True]*len(features['deck'])],
                     items_mask=[[True]*len(features['items'])],candidates_mask=[features['candidate_mask']])
        with torch.no_grad():return self.model(spatial_tensors(batch))[0].tolist()


def save_spatial_checkpoint(path,model,scaler,*,directory,policies,training_updates=0):
    validate_spatial_scaler(scaler,directory,policies);enc=SpatialCandidateEncoder()
    payload={'model_version':model.version,'encoder_version':enc.version,'width':model.width,
             'symbols':enc.symbols,'items':enc.items,'scaler':scaler,'training_updates':training_updates,
             'state_dict':model.state_dict()}
    with open(path,'xb') as stream:torch.save(payload,stream)


def load_spatial_checkpoint(path,*,directory,policies):
    payload=torch.load(path,map_location='cpu',weights_only=True);enc=SpatialCandidateEncoder()
    if (payload.get('model_version')!=SpatialCandidateModel.version or payload.get('encoder_version')!=enc.version
            or payload.get('symbols')!=enc.symbols or payload.get('items')!=enc.items):
        raise ValueError('Checkpoint model/encoder/vocabulary mismatch')
    validate_spatial_scaler(payload['scaler'],directory,policies)
    model=SpatialCandidateModel(payload['width']);model.load_state_dict(payload['state_dict'],strict=True)
    return model.eval(),payload['scaler']
