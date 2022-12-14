from numpy.lib import utils
from scipy.sparse import data
from torch_geometric.nn import GCNConv, TopKPooling
from torch_geometric.nn import global_mean_pool as gap, global_max_pool as gmp
from typing import Tuple, Dict, List, Union
from sklearn.base import BaseEstimator
from tqdm import tqdm
import torch
from omegaconf import DictConfig
from utils.training import configure_optimizers_alon
import numpy as np
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.data import DataLoader
from sklearn.model_selection import StratifiedKFold
from typing import Tuple, Dict, List, Union
from omegaconf import DictConfig
from utils.training import configure_optimizers_alon
from torch.optim import Adam, Optimizer, SGD, Adamax, RMSprop
from utils.training import cut_gadgets_encoded_contexts
import torch.nn as nn
import numpy
import torch.nn.functional as F
from utils.training import cut_sys_encoded_contexts
from utils.matrics import Statistic
import pprint as pp
from pytorch_lightning.core.lightning import LightningModule

class SYS_BGRU(LightningModule):
    _negative_value = -numpy.inf
    _activations = {
        "relu": nn.ReLU(),
        "sigmoid": nn.Sigmoid(),
        "tanh": nn.Tanh(),
        "lkrelu": nn.LeakyReLU(0.3)
    }
    _optimizers = {
        "RMSprop": RMSprop,
        "Adam": Adam,
        "SGD": SGD,
        "Adamax": Adamax
    }

    def __init__(
        self,
        config: DictConfig,
    ):
        super().__init__()
        self._config = config
        self.save_hyperparameters()
        self.init_layers()

    def _get_activation(self, activation_name: str) -> torch.nn.Module:
        if activation_name in self._activations:
            return self._activations[activation_name]
        raise KeyError(f"Activation {activation_name} is not supported")

    def _get_optimizer(self, optimizer_name: str) -> torch.nn.Module:
        if optimizer_name in self._optimizers:
            return self._optimizers[optimizer_name]
        raise KeyError(f"Optimizer {optimizer_name} is not supported")

    def init_layers(self):
        self.dropout_rnn = nn.Dropout(self._config.encoder.rnn_dropout)
        # BLSTM layer
        self.blstm_layer = nn.LSTM(
            input_size=self._config.encoder.embedding_size,
            hidden_size=self._config.encoder.rnn_size,
            num_layers=self._config.encoder.rnn_num_layers,
            bidirectional=self._config.encoder.use_bi_rnn,
            dropout=self._config.encoder.rnn_dropout
            if self._config.encoder.rnn_num_layers > 1 else 0,
            batch_first=True)
        # BGUR layer
        self.bgru_layer = nn.GRU(
            input_size=self._config.encoder.embedding_size,
            hidden_size=self._config.encoder.rnn_size,
            num_layers=self._config.encoder.rnn_num_layers,
            bidirectional=self._config.encoder.use_bi_rnn,
            dropout=self._config.encoder.rnn_dropout
            if self._config.encoder.rnn_num_layers > 1 else 0,
            batch_first=True)
        # layer for attention
        # self.att_layer = LuongAttention(self.hidden_size)
        # self.att_layer = LocalAttention(self._config.encoder.hidden_size)

        # MLP
        layers = [
            nn.Linear(self._config.encoder.rnn_size,
                      self._config.classifier.hidden_size),
            self._get_activation(self._config.classifier.activation),
            nn.Dropout(0.5)
        ]
        if self._config.classifier.n_hidden_layers < 1:
            raise ValueError(
                f"Invalid layers number ({self._config.classifier.n_hidden_layers})"
            )
        for _ in range(self._config.classifier.n_hidden_layers - 1):
            layers += [
                nn.Linear(self._config.classifier.hidden_size,
                          self._config.classifier.hidden_size),
                self._get_activation(self._config.classifier.activation),
                nn.Dropout(0.5)
            ]
        self.hidden_layers = nn.Sequential(*layers)

        self.out_layer = nn.Linear(self._config.classifier.hidden_size, 2)

    def forward(self, batch) -> torch.Tensor:
        """
        :param gadgets: (total word length, input size)
        :param words_per_label: word length for each label
        :return: (batch size, output size)
        """
        gadgets = batch.gadgets
        words_per_label = batch.tokens_per_label
        batch_size = len(words_per_label)
        # x: (batch size, seq len, input size), masks: (batch size, sen_len)
        x, masks = cut_sys_encoded_contexts(
            gadgets, words_per_label, self._config.hyper_parameters.seq_len,
            self._negative_value)

        lengths_per_label = [
            min(self._config.hyper_parameters.seq_len, word_per_label.item())
            for word_per_label in words_per_label
        ]
        # accelerating packing
        with torch.no_grad():
            first_pad_pos = torch.from_numpy(numpy.array(lengths_per_label))
            sorted_path_lengths, sort_indices = torch.sort(first_pad_pos,
                                                           descending=True)
            _, reverse_sort_indices = torch.sort(sort_indices)
            sorted_path_lengths = sorted_path_lengths.to(torch.device("cpu"))
        x = x[sort_indices]
        x = nn.utils.rnn.pack_padded_sequence(x,
                                              sorted_path_lengths,
                                              batch_first=True)

        # bgru_out: (batch size, seq len, 2 * hidden size), h_n: (num layers * 2, batch size, hidden size)
        self.bgru_layer.flatten_parameters()
        bgru_out, h_n = self.bgru_layer(x)
        # (batch size, num layers * 2, hidden size)
        h_n = h_n.permute(1, 0, 2)

        # atten_out = self.att_layer(blstm_out, h_n, masks) # (batch size, hidden size)
        # atten_out = self.att_layer(blstm_out,
        #                            masks)  # (batch size, hidden size)
        atten_out = torch.sum(h_n, dim=1)  # (batch size, hidden size)
        atten_out = self.dropout_rnn(atten_out)[reverse_sort_indices]
        out = self.out_layer(
            self.hidden_layers(atten_out))  # (batch size, output size)
        # out_prob = F.softmax(out.view(batch_size, -1)) # (batch size, output size)
        out_prob = torch.log_softmax(out.view(batch_size, -1),
                                     dim=1)  # (batch size, output size)

        return out_prob
        
class VDP_BLSTM(nn.Module):
    _negative_value = -numpy.inf
    _activations = {
        "relu": nn.ReLU(),
        "sigmoid": nn.Sigmoid(),
        "tanh": nn.Tanh(),
        "lkrelu": nn.LeakyReLU(0.3)
    }
    _optimizers = {
        "RMSprop": RMSprop,
        "Adam": Adam,
        "SGD": SGD,
        "Adamax": Adamax
    }

    def __init__(
        self,
        config: DictConfig,
        
    ):
        super().__init__()
        self._config = config
        self.init_layers()

    def _get_activation(self, activation_name: str) -> torch.nn.Module:
        if activation_name in self._activations:
            return self._activations[activation_name]
        raise KeyError(f"Activation {activation_name} is not supported")

    def _get_optimizer(self, optimizer_name: str) -> torch.nn.Module:
        if optimizer_name in self._optimizers:
            return self._optimizers[optimizer_name]
        raise KeyError(f"Optimizer {optimizer_name} is not supported")



    def init_layers(self):
        self.dropout_rnn = nn.Dropout(self._config.encoder.rnn_dropout)
        # BLSTM layer
        self.blstm_layer = nn.LSTM(
            input_size=self._config.encoder.embedding_size,
            hidden_size=self._config.encoder.rnn_size,
            num_layers=self._config.encoder.rnn_num_layers,
            bidirectional=self._config.encoder.use_bi_rnn,
            dropout=self._config.encoder.rnn_dropout
            if self._config.encoder.rnn_num_layers > 1 else 0,
            batch_first=True)
        # layer for attention
        # self.att_layer = LuongAttention(self.hidden_size)
        # self.att_layer = LocalAttention(self._config.encoder.hidden_size)

        # MLP
        layers = [
            nn.Linear(self._config.encoder.rnn_size,
                      self._config.classifier.hidden_size),
            self._get_activation(self._config.classifier.activation),
            nn.Dropout(0.5)
        ]
        if self._config.classifier.n_hidden_layers < 1:
            raise ValueError(
                f"Invalid layers number ({self._config.classifier.n_hidden_layers})"
            )
        for _ in range(self._config.classifier.n_hidden_layers - 1):
            layers += [
                nn.Linear(self._config.classifier.hidden_size,
                          self._config.classifier.hidden_size),
                self._get_activation(self._config.classifier.activation),
                nn.Dropout(0.5)
            ]
        self.hidden_layers = nn.Sequential(*layers)

        self.out_layer = nn.Linear(self._config.classifier.hidden_size, 2)

    def forward(self, batch) -> torch.Tensor:
        """
        :param gadgets: (total word length, input size)
        :param is_back:
        :param words_per_label: word length for each label
        :return: (batch size, output size)
        """
        gadgets = batch.gadgets
        is_back = batch.is_back 
        words_per_label = batch.tokens_per_label
        batch_size = len(words_per_label)  # batch size: int
        # x: (batch size, sen_len; input size), masks: (batch size; sen_len)
        x, masks = cut_gadgets_encoded_contexts(
            gadgets, is_back, words_per_label,
            self._config.hyper_parameters.seq_len, self._negative_value)

        lengths_per_label = [
            min(self._config.hyper_parameters.seq_len, word_per_label.item())
            for word_per_label in words_per_label
        ]
        # accelerating packing
        with torch.no_grad():
            first_pad_pos = torch.from_numpy(numpy.array(lengths_per_label))
            sorted_path_lengths, sort_indices = torch.sort(first_pad_pos,
                                                           descending=True)
            _, reverse_sort_indices = torch.sort(sort_indices)
            sorted_path_lengths = sorted_path_lengths.to(torch.device("cpu"))
        x = x[sort_indices]
        x = nn.utils.rnn.pack_padded_sequence(x,
                                              sorted_path_lengths,
                                              batch_first=True)

        # blstm_out: (batch size, sen len, 2 * hidden size), h_n: (num layers * 2, batch size, hidden size)
        blstm_out, (h_n, c_n) = self.blstm_layer(x)
        h_n = h_n.permute(1, 0, 2)  # (batch size, num layers * 2, hidden size)

        # atten_out = self.att_layer(blstm_out, h_n, masks) # (batch size, hidden size)
        # atten_out = self.att_layer(blstm_out,
        #                            masks)  # (batch size, hidden size)
        atten_out = torch.sum(h_n, dim=1)  # (batch size, hidden size)
        atten_out = self.dropout_rnn(atten_out)[reverse_sort_indices]
        out = self.out_layer(
            self.hidden_layers(atten_out))  # (batch size, output size)
        # out_prob = F.softmax(out.view(batch_size, -1)) # (batch size, output size)
        out_prob = torch.log_softmax(out.view(batch_size, -1),
                                     dim=1)  # (batch size, output size)

        return out_prob
        
class GCNPoolBlockLayer(nn.Module):
    """graph conv-pool block

    graph convolutional + graph pooling + graph readout

    :attr GCL: graph conv layer
    :attr GPL: graph pooling layer
    """
    def __init__(self, config: DictConfig):
        super(GCNPoolBlockLayer, self).__init__()
        self._config = config
        input_size = self._config.hyper_parameters.vector_length
        self.layer_num = self._config.gnn.layer_num
        self.input_GCL = GCNConv(input_size, config.gnn.hidden_size)

        self.input_GPL = TopKPooling(config.gnn.hidden_size,
                                     ratio=config.gnn.pooling_ratio)

        for i in range(self.layer_num - 1):
            setattr(self, f"hidden_GCL{i}",
                    GCNConv(config.gnn.hidden_size, config.gnn.hidden_size))
            setattr(
                self, f"hidden_GPL{i}",
                TopKPooling(config.gnn.hidden_size,
                            ratio=config.gnn.pooling_ratio))

    def forward(self, data):
        x, edge_index, batch = data.x, data.edge_index, data.batch
        x = F.relu(self.input_GCL(x, edge_index))
        x, edge_index, _, batch, _, _ = self.input_GPL(x, edge_index, None,
                                                       batch)
        # (batch size, hidden)
        out = torch.cat([gmp(x, batch), gap(x, batch)], dim=1)
        for i in range(self.layer_num - 1):
            x = F.relu(getattr(self, f"hidden_GCL{i}")(x, edge_index))
            x, edge_index, _, batch, _, _ = getattr(self, f"hidden_GPL{i}")(
                x, edge_index, None, batch)
            out += torch.cat([gmp(x, batch), gap(x, batch)], dim=1)

        return out


class VGD_GNN(nn.Module):
    _activations = {
        "relu": nn.ReLU(),
        "sigmoid": nn.Sigmoid(),
        "tanh": nn.Tanh(),
        "lkrelu": nn.LeakyReLU(0.3)
    }

    def __init__(
        self,
        config: DictConfig,
    ):
        super().__init__()
        self._config = config
        self.init_layers()

    def init_layers(self):
        self.gnn_layer = GCNPoolBlockLayer(self._config)
        self.lin1 = nn.Linear(self._config.gnn.hidden_size * 2,
                              self._config.gnn.hidden_size)
        self.dropout1 = nn.Dropout(self._config.classifier.drop_out)
        self.lin2 = nn.Linear(self._config.gnn.hidden_size,
                              self._config.gnn.hidden_size // 2)
        self.dropout2 = nn.Dropout(self._config.classifier.drop_out)
        self.lin3 = nn.Linear(self._config.gnn.hidden_size // 2, 2)

    def _get_activation(self, activation_name: str) -> torch.nn.Module:
        if activation_name in self._activations:
            return self._activations[activation_name]
        raise KeyError(f"Activation {activation_name} is not supported")

    def forward(self, batch):
        # (batch size, hidden)
        x = self.gnn_layer(batch)
        act = self._get_activation(self._config.classifier.activation)
        x = self.dropout1(act(self.lin1(x)))
        x = self.dropout2(act(self.lin2(x)))
        # (batch size, output size)
        # x = F.log_softmax(self.lin3(x), dim=-1)
        x = self.lin3(x)
        out_prob = F.log_softmax(x, dim=-1)
        return out_prob
            
class My_Stacking(torch.nn.Module):
    def __init__(
        self,
        models:List,
        configs:List,
        config: DictConfig
    ):
        super().__init__()
        self._config = config
        self.models = models
        self.configs = configs
        self._GPU = self._config.gpu
        # self.liner1 = nn.Linear(len(models) * 2, 16)
        # self.liner2 = nn.Linear(16, 32)
        # self.liner3 = nn.Linear(32, 128)
        # self.liner4 = nn.Linear(128, 32)
        # self.liner5 = nn.Linear(32, 16)
        # self.liner6 = nn.Linear(16, 2)
        # self.act = nn.ReLU()
        self.linear = nn.Sequential(
            nn.Linear(6, 32),
            nn.ReLU(),
            nn.Linear(32, 64),
            nn.ReLU(),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 2)
        )
        
        self.loss = F.nll_loss
        self.result = dict()
        
    def forward(self, batch):
        # (batch size, hidden)    
        x = self.linear(batch)
        logits = torch.log_softmax(x, dim=-1)
        return logits
    
    def get_dataloader(self, dataset, batch_size, idx, shuffle_data=False):
        
        sub_dataset = dataset[idx.tolist()]
        loader = DataLoader(
            sub_dataset,
            batch_size = batch_size,
            shuffle = shuffle_data,
            num_workers = self._config.num_workers,
            pin_memory = True,
        )
        return loader
    
    def k_fold_train(self, dataset, cv_n_folds=5):
        # k???????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????
        # ????????????????????????????????????????????????stacking???????????????3??????????????????????????????3???????????????????????????????????????????????????????????????
        # ????????????????????????????????????????????????
        # ????????????Staking????????????????????????????????????????????????????????????staking????????????CL????????????
        X, s, xfg_id = [i.x for i in dataset], [i.y for i in dataset], [i.xfg_id.item() for i in dataset]
        
        K = len(np.unique(s))
        s = np.asarray(s)
        
        kf = StratifiedKFold(n_splits=cv_n_folds, shuffle=True, random_state=self._config.seed)
        
        # Intialize psx array
        
        # Split X and s into "cv_n_folds" stratified folds.
        liner_inputs = []
        for model, config in zip(self.models,self.configs):
            if torch.cuda.is_available():
                model.cuda(self._GPU)
            psx = np.zeros((len(s), K))
            
            optimizers, schedulers = configure_optimizers_alon(config.hyper_parameters,
                                         model.parameters())
            optimizer, scheduler = optimizers[0], schedulers[0]
            
            for k, (cv_train_idx, cv_holdout_idx) in enumerate(kf.split(X, s)):
                train_dataloader = self.get_dataloader(dataset, config.hyper_parameters.batch_size, cv_train_idx, True)
                test_dataloader = self.get_dataloader(dataset, config.hyper_parameters.test_batch_size, cv_holdout_idx, False)
                #????????????
                model.train()
                for epoch in tqdm(range(config.hyper_parameters.n_epochs)):
                    for batch in train_dataloader:
                        device = torch.device("cuda:{}".format(self._GPU) if torch.cuda.is_available() else "cpu")
                        batch.to(device)
                        optimizer.zero_grad()
                        output = model(batch)
                        loss = F.nll_loss(output, batch.y, weight=None)
                        loss.backward()
                        optimizer.step()
                    scheduler.step() 
                #????????????
                model.eval()
                outputs = []
                outs = []
                for batch in test_dataloader:
                    device = torch.device("cuda:{}".format(self._GPU) if torch.cuda.is_available() else "cpu")
                    batch.to(device)
                    output = model(batch)
                    loss = F.nll_loss(output, batch.y)
                    with torch.no_grad():
                        _, preds = output.max(dim=1)
                        # with open('srad_simple_analysis/train_false_xfg_ids.txt', 'a+') as f:
                        #     for xfg_id in batch.xfg_id[batch.y != preds]:
                        #         f.write(str(xfg_id.tolist()) + ',')
                        #     f.close()
                        statistic = Statistic().calculate_statistic(
                            batch.y,
                            preds,
                            2,
                        )
                    outs.append({"loss": loss, "statistic": statistic})
                    outputs.append(output)
                with torch.no_grad():
                    mean_loss = torch.stack([out["loss"]
                                     for out in outs]).mean().item()
                    logs = {"test/loss": mean_loss}
                    logs.update(
                        Statistic.union_statistics([
                        out["statistic"] for out in outs
                    ]).calculate_metrics("test"))
                    pp.pprint(logs)
                # Outputs are log_softmax (log probabilities)
                outputs = torch.cat(outputs, dim=0)
                psx[cv_holdout_idx] = outputs.cpu().detach().numpy() 
            liner_inputs.append(torch.tensor(psx, dtype=torch.float))
        liner_inputs = torch.cat(liner_inputs, dim = 1)
        liner_inputs = torch.exp(liner_inputs)
        liner_input_train = liner_inputs.numpy().tolist()
        self.result['train'] = dict()
        self.result['train']['liner_input_train'] = liner_inputs.numpy().tolist()
        self.result['train']['s'] = s.tolist()
        self.result['train']['xfg_id'] = xfg_id
        
        # from utils.json_ops import read_json
        # result = read_json('liner_input.json')
        # liner_inputs = result['train']["liner_input_train"]
        # liner_inputs = numpy.array(liner_inputs)
        # liner_inputs = torch.Tensor(liner_inputs)

        #?????????????????????
        if torch.cuda.is_available():
            self.cuda(self._GPU)
        optimizers, schedulers = configure_optimizers_alon(self._config.hyper_parameters,
                                         self.parameters())
        self.optimizer, self.scheduler = optimizers[0], schedulers[0]
        self.train()
        
        for epoch in tqdm(range(self._config.hyper_parameters.n_epochs)):
            device = torch.device("cuda:{}".format(self._GPU) if torch.cuda.is_available() else "cpu")
            liner_inputs = liner_inputs.to(device)
            self.optimizer.zero_grad()
            logits = self(liner_inputs)
            loss = self.loss(logits, torch.tensor(s, dtype=torch.long).to(device))
            loss.backward()
            self.optimizer.step()
            self.scheduler.step()
        
    def predict_proba(self, batch):
        self.result['test'] = dict()
        liner_inputs = []
        self.result['test']['s'] = batch.y.tolist()
        self.result['test']['xfg_id'] = batch.xfg_id.tolist()
        for model in self.models:
            model.eval()
            device = torch.device("cuda:{}".format(self._GPU) if torch.cuda.is_available() else "cpu")
            batch.to(device)
            model.to(device)
            liner_inputs.append(model(batch))
        liner_inputs = torch.cat(liner_inputs, dim = 1)
        liner_inputs = torch.exp(liner_inputs)
        device = torch.device("cuda:{}".format(self._GPU) if torch.cuda.is_available() else "cpu")
        
        self.result['test']['liner_input_test'] = liner_inputs.cpu().detach().numpy().tolist()
        
        liner_inputs = liner_inputs.to(device)
        self.eval()
        return self(liner_inputs)
    
    
    def _general_epoch_end(self, outputs: List[Dict], group: str) -> Dict:
        with torch.no_grad():
            mean_loss = torch.stack([out["loss"]
                                     for out in outputs]).mean().item()
            logs = {f"{group}/loss": mean_loss}
            logs.update(
                Statistic.union_statistics([
                    out["statistic"] for out in outputs
                ]).calculate_metrics(group))
            pp.pprint(logs)
            
            
    def test(self, test_dataset):
        
        loader = DataLoader(
            test_dataset,
            batch_size = len(test_dataset),
            shuffle = False,
            num_workers = 1,
            pin_memory = True,
        )
       
        outputs = []
        self.eval()
        for batch in tqdm(loader):
            logits = self.predict_proba(batch)
            loss = self.loss(logits, batch.y)
            with torch.no_grad():
                _, preds = logits.max(dim=1)
                # with open('srad_simple_analysis/train_false_xfg_ids.txt', 'a+') as f:
                #     for xfg_id in batch.xfg_id[batch.y != preds]:
                #         f.write(str(xfg_id.tolist()) + ',')
                #     f.close()
                statistic = Statistic().calculate_statistic(
                    batch.y,
                    preds,
                    2,
                )
                outputs.append({"loss": loss, "statistic": statistic})
        self._general_epoch_end(outputs, "test")
        
        # from utils.json_ops import write_json
        # pp.pprint(self.result)
        # write_json(self.result, 'liner_input.json')
                
       
        
        
class MY_CL_Stacking(BaseEstimator):  # Inherits sklearn classifier
    """Wraps a PyTorch CNN for the MNIST dataset within an sklearn template

    Defines ``.fit()``, ``.predict()``, and ``.predict_proba()`` functions. This
    template enables the PyTorch CNN to flexibly be used within the sklearn
    architecture -- meaning it can be passed into functions like
    cross_val_predict as if it were an sklearn model. The cleanlab library
    requires that all models adhere to this basic sklearn template and thus,
    this class allows a PyTorch CNN to be used in for learning with noisy
    labels among other things.

    Parameters
    ----------
    batch_size: int
    epochs: int
    log_interval: int
    lr: float
    momentum: float
    no_cuda: bool
    seed: int
    test_batch_size: int, default=None
    dataset: {'mnist', 'sklearn-digits'}
    loader: {'train', 'test'}
      Set to 'test' to force fit() and predict_proba() on test_set

    Note
    ----
    Be careful setting the ``loader`` param, it will override every other loader
    If you set this to 'test', but call .predict(loader = 'train')
    then .predict() will still predict on test!

    Attributes
    ----------
    batch_size: int
    epochs: int
    log_interval: int
    lr: float
    momentum: float
    no_cuda: bool
    seed: int
    test_batch_size: int, default=None
    dataset: {'mnist', 'sklearn-digits'}
    loader: {'train', 'test'}
      Set to 'test' to force fit() and predict_proba() on test_set

    Methods
    -------
    fit
      fits the model to data.
    predict
      get the fitted model's prediction on test data
    predict_proba
      get the fitted model's probability distribution over clases for test data
    """
    def __init__(
            self,
            models,
            configs,
            dataset,
            config: DictConfig,
            no_cuda,
            loader = None
            
    ):
        self.config = config
        self.dataset = dataset
        self.batch_size = config.cl.batch_size
        self.epochs = config.cl.n_epochs
        self.lr = config.hyper_parameters.learning_rate
        self.no_cuda = no_cuda
        self.seed = config.seed
        self._GPU = config.gpu
        self.cuda = not self.no_cuda and torch.cuda.is_available()
        self.log_interval = config.hyper_parameters.log_interval
        torch.manual_seed(self.seed)
        if self.cuda:  # pragma: no cover
            torch.cuda.manual_seed(self.seed)

        # Instantiate PyTorch model
        self.model = My_Stacking(models=models, configs=configs, config=config)
        #??????GPU??????
        if self.cuda:  # pragma: no cover
            self.model.cuda(self._GPU)

        self.loader_kwargs = {'num_workers': self.config.num_workers,
                              'pin_memory': True} if self.cuda else {}
        self.loader = loader
        
        self.cnt_dict = dict()
        self.test_batch_size = config.hyper_parameters.test_batch_size

    def get_dataloader(self, idx, shuffle_data=False):
    
        
        sub_dataset = self.dataset[idx.tolist()]
        loader = DataLoader(
            sub_dataset,
            batch_size = self.batch_size,
            shuffle = shuffle_data,
            num_workers = self.config.num_workers,
            pin_memory = True,
        )
        return loader
    
    def get_sub_dataset(self, idx):
        return self.dataset[idx.tolist()]

    def fit(self, train_idx, train_labels=None, sample_weight=None,
            loader='train'):
        """This function adheres to sklearn's "fit(X, y)" format for
        compatibility with scikit-learn. ** All inputs should be numpy
        arrays, not pyTorch Tensors train_idx is not X, but instead a list of
        indices for X (and y if train_labels is None). This function is a
        member of the cnn class which will handle creation of X, y from the
        train_idx via the train_loader. """
        if self.loader is not None:
            loader = self.loader
        if train_labels is not None and len(train_idx) != len(train_labels):
            raise ValueError(
                "Check that train_idx and train_labels are the same length.")

        if sample_weight is not None:  # pragma: no cover
            if len(sample_weight) != len(train_labels):
                raise ValueError("Check that train_labels and sample_weight "
                                 "are the same length.")
            class_weight = sample_weight[
                np.unique(train_labels, return_index=True)[1]]
            class_weight = torch.from_numpy(class_weight).float()
            if self.cuda:
                class_weight = class_weight.cuda(self._GPU)
        else:
            class_weight = None

        
        train_dataset = self.get_sub_dataset(train_idx)
        self.model.k_fold_train(train_dataset, cv_n_folds=5)
        
        
    def predict(self, idx=None, loader=None):
        """Get predicted labels from trained model."""
        # get the index of the max probability
        probs = self.predict_proba(idx)
        return probs.argmax(axis=1)

    
    def predict_proba(self, idx=None, loader=None):
        if self.loader is not None:
            loader = self.loader
        # if loader is None:
        #     is_test_idx = idx is not None and len(
        #         idx) == self.test_size and np.all(
        #         np.array(idx) == np.arange(self.test_size))
        #     loader = 'test' if is_test_idx else 'train'
        test_loader = self.get_dataloader(idx)

        # sets model.train(False) inactivating dropout and batch-norm layers

        # Run forward pass on model to compute outputs
        outputs = []
        for batch in tqdm(test_loader):
            device = torch.device("cuda:{}".format(self._GPU) if torch.cuda.is_available() else "cpu")
            batch.to(device)
            output = self.model.predict_proba(batch)
            outputs.append(output)

        # Outputs are log_softmax (log probabilities)
        outputs = torch.cat(outputs, dim=0)
        # Convert to probabilities and return the numpy array of shape N x K
        out = outputs.cpu().detach().numpy() if self.cuda else outputs.detach().numpy()
        pred = np.exp(out)
        return pred