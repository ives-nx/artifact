from typing import Tuple, Dict, List, Union

import torch
from pytorch_lightning.core.lightning import LightningModule
from torch.optim import Optimizer
from torch.optim.lr_scheduler import _LRScheduler

from omegaconf import DictConfig
from models.vuldeepecker.data_classes import VDPBatch
from utils.training import configure_optimizers_alon
from torch.optim import Adam, Optimizer, SGD, Adamax, RMSprop

import torch.nn as nn
import numpy
import torch.nn.functional as F
from utils.training import cut_gadgets_encoded_contexts
from utils.matrics import Statistic


class VDP_BLSTM(LightningModule):
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
        self._GPU = config.gpu
        self.init_layers()
        optimizers, schedulers = configure_optimizers_alon(self._config.hyper_parameters,
                                         self.parameters())
        self.optimizer = optimizers[0]
        self.scheduler = schedulers[0]
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

    def forward(self, gadgets: torch.Tensor, is_back: List[bool],
                words_per_label: List[int]) -> torch.Tensor:
        """
        :param gadgets: (total word length, input size)
        :param is_back:
        :param words_per_label: word length for each label
        :return: (batch size, output size)
        """

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



    def my_train(self, data_module, ds_idx):
        data_module.prepare_data()
        data_loader, n_samples = data_module.train_dataloader()
        loss_dict = dict()
        
        # Train for self.epochs epochs
        if torch.cuda.is_available():
            self.cuda(self._GPU)
        self.train()
        for epoch in range(self._config.dt.n_epochs):

            for batch_idx,data in enumerate(data_loader) :
                data.move_to_device("cuda:{}".format(self._GPU) if torch.cuda.is_available() else "cpu")
                self.optimizer.zero_grad()
                logits = self(data.gadgets, data.is_back, data.tokens_per_label)
                loss = F.nll_loss(logits, data.labels, weight=None)
   
                if epoch >= 0:
                    
                    with torch.no_grad():
                        for logit_t, y_t, xfg_id_t in zip(logits, data.labels, data.idxs):
                            logit = logit_t.tolist()

                            y = y_t.tolist()
                            xfg_id = xfg_id_t.tolist()
                            loss_v = F.nll_loss(logit_t.reshape(1,2), y_t.reshape(1)).item()
                            if xfg_id in ds_idx:
                                if str(xfg_id) not in loss_dict.keys():
                                    loss_dict[str(xfg_id)] = list()
                                loss_dict[str(xfg_id)].append(loss_v)    


                loss.backward()
                self.optimizer.step()
                if self._config.hyper_parameters.log_interval is not None and \
                            batch_idx % self._config.hyper_parameters.log_interval == 0:
                    print(
                            'TrainEpoch: {} [{}/{} ({:.0f}%)]\tLoss: {:.6f}'.format(
                                epoch, batch_idx * self._config.hyper_parameters.batch_size, n_samples,
                                100. * batch_idx / len(data_loader),
                                loss.item()),end='\r'
                    )
            self.scheduler.step()
        return loss_dict

    def training_step(self, batch: VDPBatch, batch_idx: int) -> Dict:
        # (batch size, output size)
        logits = self(batch.gadgets, batch.is_back, batch.tokens_per_label)
        # loss = F.cross_entropy(logits, batch.labels)
        loss = F.nll_loss(logits, batch.labels)

        for logit_t, y_t, id_t in zip(logits, batch.labels, batch.idxs):
            logit = logit_t.tolist()

            y = y_t.tolist()
            idx = id_t.tolist()
            if y == 0:
                loss_v = pow(logit[y]-y,2)
            else:
                loss_v = pow(logit[y]-(y-1),2)
            
            if idx in self.ds_idx:
                if str(idx) not in self.loss_dict.keys():
                    self.loss_dict[str(idx)] = list()
                self.loss_dict[str(idx)].append(loss_v)

        log: Dict[str, Union[float, torch.Tensor]] = {"train/loss": loss}
        with torch.no_grad():
            _, preds = logits.max(dim=1)
            statistic = Statistic().calculate_statistic(
                batch.labels,
                preds,
                2,
            )
            batch_matric = statistic.calculate_metrics(group="train")
            log.update(batch_matric)
            self.log_dict(log)
            self.log("f1",
                     batch_matric["train/f1"],
                     prog_bar=True,
                     logger=False)

        return {"loss": loss, "statistic": statistic}

    def validation_step(self, batch: VDPBatch, batch_idx: int) -> Dict:
        # (batch size, output size)
        logits = self(batch.gadgets, batch.is_back, batch.tokens_per_label)

        # loss = F.cross_entropy(logits, batch.labels)
        loss = F.nll_loss(logits, batch.labels)
        with torch.no_grad():
            _, preds = logits.max(dim=1)
            statistic = Statistic().calculate_statistic(
                batch.labels,
                preds,
                2,
            )

        return {"loss": loss, "statistic": statistic}

    def test_step(self, batch: VDPBatch, batch_idx: int) -> Dict:
        return self.validation_step(batch, batch_idx)

    def _general_epoch_end(self, outputs: List[Dict], group: str) -> Dict:
        with torch.no_grad():
            mean_loss = torch.stack([out["loss"]
                                     for out in outputs]).mean().item()
            logs = {f"{group}/loss": mean_loss}
            logs.update(
                Statistic.union_statistics([
                    out["statistic"] for out in outputs
                ]).calculate_metrics(group))
            self.log_dict(logs)
            self.log(f"{group}_loss", mean_loss)

    # ===== OPTIMIZERS =====

    def configure_optimizers(
            self) -> Tuple[List[Optimizer], List[_LRScheduler]]:
        return self._get_optimizer(self._config.hyper_parameters.optimizer)(
            self.parameters(), self._config.hyper_parameters.learning_rate)

    # ===== ON EPOCH END =====

    def training_epoch_end(self, outputs: List[Dict]) -> Dict:
        return self._general_epoch_end(outputs, "train")

    def validation_epoch_end(self, outputs: List[Dict]) -> Dict:
        return self._general_epoch_end(outputs, "val")

    def test_epoch_end(self, outputs: List[Dict]) -> Dict:
        return self._general_epoch_end(outputs, "test")
