from builtins import slice
from os.path import exists, join
import shutil
from typing import List, Optional, Tuple
import random
import numpy as np
from numpy.lib.function_base import flip
from sklearn import preprocessing
from utils.json_ops import read_json
import torch
from omegaconf import DictConfig
from pytorch_lightning import LightningDataModule
import sys
sys.path.append('..')
from models.deepwukong.dataset_build import PGDataset
from math import ceil
from torch_geometric.data import DataLoader
from utils.json_ops import write_json, read_json
from torch.utils.data import Subset
from torch_geometric.data import  DataLoader, Batch
import os
from models.reveal.reveal_dataset_build import RevealDataset
import json
class RevealDataModule(LightningDataModule):
    def __init__(self, config: DictConfig, noise_rate, rm_xfg_list, rm_count):
        super().__init__()
        self._config = config
        self._dataset_dir = os.path.join(self._config.data_folder, 
                                         self._config.name,
                                         self._config.dataset.name
                                         )
        self.data_path = os.path.join(self._dataset_dir, f'{self._config.dataset.name}.json')  
        self.data_json = read_json(self.data_path) 
        # self.test_data_path = join(self._config.data_folder, self._config.name, self._config.dataset.name, 'true_test.json')
        # self.test_data = read_json(self.test_data_path)
        self._geo_dir = join(self._config.geo_folder, self._config.name, self._config.dataset.name, 'geo')
        self.rm_xfg_list = rm_xfg_list
        self.rm_count = rm_count
        self.noise_set = config.noise_set
        if self.noise_set not in ['training', 'all']:
            raise RuntimeError("False noise set !!")
        if self.noise_set == 'all':
            self.noise_info_path = join(config.data_folder, config.name, config.dataset.name, 'noise_info.json')
        elif self.noise_set == 'training':
            self.noise_info_path = join(config.data_folder, config.name, config.dataset.name, 'training_noise_info.json')
        self.noisy_rate = noise_rate
        #????????????
        self.processing_data()
        
    def get_data_class_rate(self):
        
        negative_cpgs = 0
        positive_cpgs = 0
        for cpg in self.train_xfgs:
            if(cpg['target'] == 1):
                positive_cpgs += 1
            else:
                negative_cpgs += 1
        
        return negative_cpgs / positive_cpgs, len(self.test_xfgs)
    
    def flip_data(self, np_train_data, noise_xfg_ids):  
        flip_count = 0  
        for xfg in np_train_data:
            xfg_id = xfg['xfg_id']
            
            if xfg_id in noise_xfg_ids:
                # print('before flip : {} {}'.format(xfg_id, xfg['target']) )
                xfg['target'] = xfg['target'] ^ 1
                xfg['flip'] = True
                flip_count+=1
        print(flip_count)
        return np_train_data
                # print('after flip : {} {}'.format(xfg_id, xfg['target']) )
        # print('flip_count: ', flip_count)
    def remove_data(self, np_train_data, rm_xfg_list):
        true_count = 0
        rm_count = 0
        re_list = []
        # print('before rm : {}'.format(len(np_data)))
        for xfg in np_train_data:
            xfg_id = xfg['xfg_id']
            if xfg_id in rm_xfg_list:
                continue
            re_list.append(xfg)
        # print('true_count: ', true_count)
        # print('rm_count', rm_count)
        # print('after rm : {}'.format(len(re_list)))
        # result = np.array(re_list)
        return re_list 
     
    def processing_data(self):
        noise_info = read_json(self.noise_info_path)
        noise_key = '{}_percent'.format(int(self.noisy_rate * 100))
        noise_xfg_ids = noise_info[noise_key]['noise_xfg_ids']
        size = len(self.data_json)
        #??????????????????
        if noise_xfg_ids != []:
            self.data_json = self.flip_data(self.data_json, noise_xfg_ids)
        #???????????????????????????
        print('origin', len(self.data_json))

        if self.rm_xfg_list != None:
            self.data_json = self.remove_data(self.data_json, self.rm_xfg_list)   
            
        print('after remove', len(self.data_json))
        
        train_slice = slice(size // 5, len(self.data_json))
        val_slice = slice(0, size // 5)
        test_slice = slice(size // 10, size // 5)

        self.train_xfgs = self.data_json[train_slice]
        
        if self.rm_count > 0:
            print(f'before remove {self.rm_count} from train data :', len(self.train_xfgs))
            self.train_xfgs = np.random.choice(self.train_xfgs, len(self.train_xfgs) - self.rm_count, replace=False)
            print(f'after remove {self.rm_count} from train data :', len(self.train_xfgs))
        self.val_xfgs = self.data_json[val_slice]
        self.test_xfgs = self.data_json[test_slice]
        # self.test_xfgs = self.test_data
        self.data_class_rate, self.test_n_samples = self.get_data_class_rate()  
        
    def prepare_data(self):
        
        print('prepare_data')
        
        # sz = len(self.data_json)
        # sz_list = list(range(sz))
        # self.train_slice = sz_list[slice(sz // 5, sz)]  # 20% - 100%???????????????
        # self.val_slice = sz_list[slice(0, sz // 10)]  # 0 - 10%???????????????
        # self.test_slice = sz_list[slice(sz // 10, sz // 5)]  # 10% - 20%???????????????
        
    

        
        
        # TODO: download data from s3 if not exists

    def setup(self, stage: Optional[str] = None):
        # TODO: collect or convert vocabulary if needed
        if stage == 'fit':
            self.train_dataset = RevealDataset(self._config, self._geo_dir, self.train_xfgs)
            self.val_dataset = RevealDataset(self._config, self._geo_dir, self.val_xfgs)
            # self.test_dataset = RevealDataset(self._config, self._geo_dir, self.test_xfgs)

        else:
            self.test_dataset = RevealDataset(self._config, self._geo_dir, self.test_xfgs)

    def create_dataloader(
        self,
        dataset: RevealDataset,
        shuffle: bool,
        batch_size: int,
        n_workers: int,
    ) -> Tuple[DataLoader, int]:
        
        dataloader = DataLoader(
            dataset,
            batch_size=batch_size,
            shuffle=shuffle,
            num_workers=n_workers,
            pin_memory=True,
        )
        return dataloader, len(dataset)

    def train_dataloader(self, *args, **kwargs) -> DataLoader:
        train_dataset = self.train_dataset
        train_dataloader, _ = self.create_dataloader(train_dataset,
                                      self._config.hyper_parameters.shuffle_data, 
                                      self._config.hyper_parameters.batch_size,
                                      self._config.num_workers)
        return train_dataloader

    def val_dataloader(self, *args, **kwargs) -> DataLoader:
        # val_dataset = Subset(self.dataset, self.val_slice)
        val_dataset = self.val_dataset
        val_dataloader, _ = self.create_dataloader(val_dataset,
                                      self._config.hyper_parameters.shuffle_data, 
                                      self._config.hyper_parameters.test_batch_size,
                                      self._config.num_workers)
        return val_dataloader

    def test_dataloader(self, *args, **kwargs) -> DataLoader:
        # test_dataset = Subset(self.dataset, self.test_slice)
        test_dataset = self.test_dataset
        test_dataloader, _ = self.create_dataloader(test_dataset,
                                      self._config.hyper_parameters.shuffle_data, 
                                      self._config.hyper_parameters.test_batch_size,
                                      self._config.num_workers)
        return test_dataloader

    def transfer_batch_to_device(self, batch, device: torch.device):
        batch.to(device)
        return batch


# ????????????train, test, val????????????positive???negative sample????????????
def shuffle_datas_indices(positive_cpgs: list, negative_cpgs: list):
    positive_cpg_indices = list(range(len(positive_cpgs)))
    negative_cpg_indices = list(range(len(negative_cpgs)))
    random.shuffle(positive_cpg_indices)
    random.shuffle(negative_cpg_indices)

    sz = len(positive_cpg_indices)
    positive_train_dataset_slice = slice(sz // 5, sz)  # 20% - 100%???????????????
    positive_val_dataset_slice = slice(0, sz // 10)  # 0 - 10%???????????????
    positive_test_dataset_slice = slice(sz // 10, sz // 5)  # 10% - 20%???????????????

    train_positive_cpgs_indices = positive_cpg_indices[positive_train_dataset_slice]
    val_positive_cpgs_indices = positive_cpg_indices[positive_val_dataset_slice]
    test_positive_cpgs_indices = positive_cpg_indices[positive_test_dataset_slice]

    sz = len(negative_cpg_indices)
    negative_train_dataset_slice = slice(sz // 5, sz)  # 20% - 100%???????????????
    negative_val_dataset_slice = slice(0, sz // 10)  # 0 - 10%???????????????
    negative_test_dataset_slice = slice(sz // 10, sz // 5)  # 10% - 20%???????????????

    train_negative_cpgs_indices = negative_cpg_indices[negative_train_dataset_slice]
    val_negative_cpgs_indices = negative_cpg_indices[negative_val_dataset_slice]
    test_negative_cpgs_indices = negative_cpg_indices[negative_test_dataset_slice]

    return len(positive_cpgs), len(negative_cpgs),train_positive_cpgs_indices, val_positive_cpgs_indices, test_positive_cpgs_indices, \
           train_negative_cpgs_indices, val_negative_cpgs_indices, test_negative_cpgs_indices


# Triple Loss????????????
def generate_idx(idx = -1, length = 0):
    num = random.randint(0, length - 1)
    if idx != -1:
        while num == idx:
            num = random.randint(0, length - 1)
    return num


def generate_batch(datasets: list, batch_size: int):
    num_batch = len(datasets) // batch_size
    if len(datasets) % batch_size != 0:
        num_batch += 1

    for i in range(num_batch):
        start_idx = i * batch_size
        end_idx = min((i + 1) * batch_size, len(datasets))

        a_data = [data[0] for data in datasets[start_idx: end_idx]]
        p_data = [data[1] for data in datasets[start_idx: end_idx]]
        n_data = [data[2] for data in datasets[start_idx: end_idx]]

        yield Batch.from_data_list(a_data), Batch.from_data_list(p_data), Batch.from_data_list(n_data)

# Triple Loss
def get_dataloader_triple_loss(config, dataset, dataset_dir):
    
    positive_cpgs = [cpg for cpg in json.load(open(f'{dataset_dir}/positive.json', 'r', encoding='utf-8'))
                         if len(cpg['node-line-content']) > 3]
    negative_cpgs = [cpg for cpg in json.load(open(f'{dataset_dir}/negative.json', 'r', encoding='utf-8'))
                         if len(cpg['node-line-content']) > 3 and 'bad' not in cpg['functionName']]
    
    len_positive, len_negative, train_positive_cpgs_indices, val_positive_cpgs_indices, test_positive_cpgs_indices, \
    train_negative_cpgs_indices, val_negative_cpgs_indices, test_negative_cpgs_indices = shuffle_datas_indices(
        positive_cpgs, negative_cpgs)

    val_slice = val_positive_cpgs_indices + [indice + len_positive for indice in val_negative_cpgs_indices]
    test_slice = test_positive_cpgs_indices + [indice + len_positive for indice in test_negative_cpgs_indices]
    valset = Subset(dataset, val_slice)
    testset = Subset(dataset, test_slice)

    dataloader = dict()
    dataloader['eval'] = DataLoader(valset, batch_size=config.hyper_parameters.test_batch_size, shuffle=config.hyper_parameters.shuffle_data)
    dataloader['test'] = DataLoader(testset, batch_size=config.hyper_parameters.test_batch_size, shuffle=False)

    # ?????????????????????
    train_datas = []
    for i, cpg_idx in enumerate(train_positive_cpgs_indices):
        anchor_data = dataset[cpg_idx]

        p_idx = generate_idx(i, len(train_positive_cpgs_indices))
        n_idx = generate_idx(-1, len(train_negative_cpgs_indices))
        p_data = dataset[train_positive_cpgs_indices[p_idx]]
        n_data = dataset[len_positive + train_negative_cpgs_indices[n_idx]]

        train_datas.append((anchor_data, p_data, n_data))

    for i, cpg_idx in enumerate(train_negative_cpgs_indices):
        anchor_data = dataset[cpg_idx]

        p_idx = generate_idx(i, len(train_negative_cpgs_indices))
        n_idx = generate_idx(-1, len(train_positive_cpgs_indices))
        p_data = dataset[len_positive + train_negative_cpgs_indices[p_idx]]
        n_data = dataset[train_positive_cpgs_indices[n_idx]]

        train_datas.append((anchor_data, p_data, n_data))

    train_loader = generate_batch(train_datas, batch_size=config.hyper_parameters.batch_size)

    dataloader['train'] = train_loader
 
    
    return dataloader





# ???????????????
def get_dataloader(config, dataset, dataset_dir):
    
    positive_cpgs = [cpg for cpg in json.load(open(f'{dataset_dir}/positive.json', 'r', encoding='utf-8'))
                         if len(cpg['node-line-content']) > 3]
    negative_cpgs = [cpg for cpg in json.load(open(f'{dataset_dir}/negative.json', 'r', encoding='utf-8'))
                         if len(cpg['node-line-content']) > 3 and 'bad' not in cpg['functionName']]
    
    len_positive, len_negative, train_positive_cpgs_indices, val_positive_cpgs_indices, test_positive_cpgs_indices, \
    train_negative_cpgs_indices, val_negative_cpgs_indices, test_negative_cpgs_indices = shuffle_datas_indices(positive_cpgs, negative_cpgs)

    train_slice = train_positive_cpgs_indices + [indice + len_positive for indice in train_negative_cpgs_indices]
    val_slice = val_positive_cpgs_indices + [indice + len_positive for indice in val_negative_cpgs_indices]
    test_slice = test_positive_cpgs_indices + [indice + len_positive for indice in test_negative_cpgs_indices]

    trainset = Subset(dataset, train_slice)
    valset = Subset(dataset, val_slice)
    testset = Subset(dataset, test_slice)


    dataloader = dict()
    dataloader['train'] = DataLoader(trainset, batch_size=config.hyper_parameters.batch_size, shuffle=config.hyper_parameters.shuffle_data)
    dataloader['eval'] = DataLoader(valset, batch_size=config.hyper_parameters.test_batch_size, shuffle=config.hyper_parameters.shuffle_data)
    dataloader['test'] = DataLoader(testset, batch_size=config.hyper_parameters.test_batch_size, shuffle=False)

    return dataloader

if __name__ == '__main__':
    dataset = RevealDataset()
    positive_cpgs = [cpg for cpg in json.load(open(f'{data_args.dataset_dir}/positive.json', 'r', encoding='utf-8')) if len(cpg['node-line-content']) > 3]
    negative_cpgs = [cpg for cpg in json.load(open(f'{data_args.dataset_dir}/negative.json', 'r', encoding='utf-8')) if len(cpg['node-line-content']) > 3
                     and 'bad' not in cpg['functionName']]
    dataloader = get_dataloader_triple_loss(dataset, positive_cpgs, negative_cpgs)

    train_loader = dataloader['train']

    for datas in train_loader:
        print('===================')
        print(datas[0])
        print(datas[1])
        print(datas[2])