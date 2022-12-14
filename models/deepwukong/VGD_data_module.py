from builtins import slice
from os.path import exists, join
import shutil
from typing import List, Optional, Tuple
import random
import numpy as np
from numpy.lib.function_base import flip
from utils.json_ops import read_json
import torch
from omegaconf import DictConfig
from pytorch_lightning import LightningDataModule
import sys
sys.path.append('..')
from models.deepwukong.dataset_build import PGDataset
from math import ceil
from torch_geometric.data import DataLoader
from utils.json_ops import write_json

class VGDDataModule(LightningDataModule):
    def __init__(self, config: DictConfig, data_json, noisy_rate:float = 0, rm_xfg_list = None, rm_count=0, rv_xfg_list = None):
        super().__init__()
        self._config = config
        self.data_json = data_json
        self._geo_dir = join(config.data_folder, config.name, config.dataset.name, 'geo')
        self.rm_xfg_list = rm_xfg_list
        self.rm_count = rm_count
        self.rv_xfg_list = rv_xfg_list
        
        self.d2v_path = join(config.data_folder, 'CWES', config.dataset.name, 'd2v_model/{}.model'.format(config.dataset.name))
        self.noise_set = config.noise_set
        if self.noise_set not in ['training', 'all']:
            raise RuntimeError("False noise set !!")
        if self.noise_set == 'all':
            self.noise_info_path = join(config.data_folder, 'CWES', config.dataset.name, 'noise_info.json')
        elif self.noise_set == 'training':
            self.noise_info_path = join(config.data_folder, 'CWES', config.dataset.name, 'training_noise_info.json')
        self.noisy_rate = noisy_rate

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
  
    def reverse_data(self, np_train_data, rv_xfg_list):
        for xfg in np_train_data:
            xfg_id = xfg['xfg_id']
            if xfg_id in rv_xfg_list:
                xfg['target'] = xfg['target'] ^ 1
        return np_train_data  
    
    def prepare_data(self):
        
        # self.dataset = PGDataset(self.data_json, self._geo_dir)
        # sz = len(self.dataset)
        # self.train_dataset_slice = slice(sz // 5, sz)
        # self.val_dataset_slice = slice(0, sz//10)
        # self.test_dataset_slice = slice(sz // 10, sz // 5)

        #d2a specific
        
        noise_info = read_json(self.noise_info_path)
        noise_key = '{}_percent'.format(int(self.noisy_rate * 100))
        noise_xfg_ids = noise_info[noise_key]['noise_xfg_ids']
        

        # training_data = self.data_json['train']
        # np.random.shuffle(training_data)
        # sz = len(training_data)
        all_data = self.data_json
        sz = len(all_data)
        if noise_xfg_ids != []:
            all_data = self.flip_data(all_data, noise_xfg_ids)
        print(len(all_data))

        if self.rm_xfg_list != None:
            all_data = self.remove_data(all_data, self.rm_xfg_list)
        
        if self.rv_xfg_list != None:
            all_data = self.reverse_data(all_data, self.rv_xfg_list)
        
        
        print(len(all_data))
        train_slice = slice(sz // 5, len(all_data))
        val_slice = slice(0, sz // 10)
        test_slice = slice(sz // 10, sz // 5)

        train_xfgs = all_data[train_slice]
        if self.rm_count > 0:
            train_xfgs = np.random.choice(train_xfgs, len(train_xfgs) - self.rm_count, replace=False)
        val_xfgs = all_data[val_slice]
        test_xfgs = all_data[test_slice]
        
        # write_json(self.data_json, 'srad_simple_analysis/CWE119.json')
        # write_json(noise_xfg_ids, 'srad_simple_analysis/noise_xfg_ids.json')
        # write_json(self.rm_xfg_list, 'srad_simple_analysis/found_xfg_ids.json')
        if 'res_d2a_test' == self._config.res_folder:
            sz = len(all_data)
            train_slice = slice(sz // 10, sz)
            val_slice = slice(0, sz // 10)
            train_xfgs = all_data[train_slice]
            val_xfgs = all_data[val_slice]
            test_path = join(self._config.data_folder, 'CWES', self._config.dataset.name, 'true_test.json')
            test_xfgs = read_json(test_path)

            self.train_dataset = PGDataset(train_xfgs, self._geo_dir, self.d2v_path)
            self.val_dataset =  PGDataset(val_xfgs, self._geo_dir, self.d2v_path)
            self.test_dataset = PGDataset(test_xfgs, self._geo_dir, self.d2v_path)        
        else:
            self.train_dataset = PGDataset(train_xfgs, self._geo_dir, self.d2v_path)
            self.val_dataset =  PGDataset(val_xfgs, self._geo_dir, self.d2v_path)
            self.test_dataset = PGDataset(test_xfgs, self._geo_dir, self.d2v_path)

        
        
        # TODO: download data from s3 if not exists

    def setup(self, stage: Optional[str] = None):
        # TODO: collect or convert vocabulary if needed
        pass

    def create_dataloader(
        self,
        dataset: PGDataset,
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
        dataloader, n_samples = self.create_dataloader(
            self.train_dataset,
            self._config.hyper_parameters.shuffle_data,
            self._config.hyper_parameters.batch_size,
            self._config.num_workers,
        )
        print(
            f"\napproximate number of steps for train is {ceil(n_samples / self._config.hyper_parameters.batch_size)}"
        )
        return dataloader

    def val_dataloader(self, *args, **kwargs) -> DataLoader:
        dataloader, n_samples = self.create_dataloader(
            self.val_dataset,
            self._config.hyper_parameters.shuffle_data,
            self._config.hyper_parameters.test_batch_size,
            self._config.num_workers,
        )
        print(
            f"\napproximate number of steps for val is {ceil(n_samples / self._config.hyper_parameters.test_batch_size)}"
        )
        return dataloader

    def test_dataloader(self, *args, **kwargs) -> DataLoader:
        dataloader, n_samples = self.create_dataloader(
            self.test_dataset,
            self._config.hyper_parameters.shuffle_data,
            self._config.hyper_parameters.test_batch_size,
            self._config.num_workers,
        )
        print(
            f"\napproximate number of steps for test is {ceil(n_samples / self._config.hyper_parameters.test_batch_size)}"
        )
        self.test_n_samples = n_samples
        return dataloader

    def transfer_batch_to_device(self, batch, device: torch.device):
        batch.to(device)
        return batch
