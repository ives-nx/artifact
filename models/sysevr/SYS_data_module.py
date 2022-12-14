from os.path import exists, join
from models.sysevr.buffered_path_context import BufferedPathContext
from typing import List, Optional, Tuple

import torch
from omegaconf import DictConfig
from pytorch_lightning import LightningDataModule
from torch.utils.data import DataLoader, Dataset
from utils.vectorize_gadget import GadgetVectorizer
from utils.json_ops import read_json
from models.sysevr.data_classes import SYSSample, SYSBatch
from models.sysevr.SYS_dataset import SYSDataset
from math import ceil
from sklearn.utils import resample

class   SYSDataModule(LightningDataModule):
    def __init__(self, config: DictConfig, data_json, noisy_rate:float=0, rm_id_list:list=None, rm_count=0):
        super().__init__()
        self._config = config
        self._dataset_dir = join(config.data_folder, config.name,
                                 config.dataset.name)
        self.noise_rate = noisy_rate
        self.config = config
        self.data_json = data_json
        self.w2v_path = join(self._dataset_dir, 'w2v.model')
        self.noise_set = config.noise_set
        if self.noise_set not in ['training', 'all']:
            raise RuntimeError("False noise set !!")
        if self.noise_set == 'all':
            self.noise_info_path = join(config.data_folder, config.name, config.dataset.name, 'noise_info.json')
        elif self.noise_set == 'training':
            self.noise_info_path = join(config.data_folder, config.name, config.dataset.name, 'training_noise_info.json')
        self.rm_id_list = rm_id_list
        self.rm_count = rm_count
        
    def flip_data(self, all_data, noise_xfg_ids):
        for data in all_data:
            xfg_id = data['xfg_id']
            if xfg_id in noise_xfg_ids:
                data['val'] = data['val'] ^ 1
                data['flip'] = not data['flip']
        return all_data

    def rm_data(self, all_data, rm_id_list):
        re_data = []
        for data in all_data:
            xfg_id = data['xfg_id']
            if xfg_id in rm_id_list:
                continue
            re_data.append(data)
        return re_data

    def prepare_data(self):
        if not exists(self._dataset_dir):
            raise ValueError(
                f"There is no file in passed path ({self._dataset_dir})")
        vectorizer = GadgetVectorizer(self.config)

        vectorizer.load_model(w2v_path=self.w2v_path)

        noise_key = '{}_percent'.format(int(self.noise_rate * 100))

        noise_info = read_json(self.noise_info_path)
        noise_xfg_ids = noise_info[noise_key]['noise_xfg_ids']
        all_data = self.data_json
        if noise_xfg_ids != []:
            all_data = self.flip_data(all_data, noise_xfg_ids=noise_xfg_ids)
        
        print('src data count :', len(all_data))
        if self.rm_id_list is not None:
            
            all_data = self.rm_data(all_data, self.rm_id_list)
        print('after rm data count :', len(all_data))

        X = []
        labels = []
        count = 0
        for gadget in all_data:
            count += 1
            print("Processing gadgets...", count, end="\r")
            vector, backwards_slice = vectorizer.vectorize2(
                gadget["gadget"])  # [word len, embedding size]
            # vectors.append(vector)
            X.append((vector, gadget['xfg_id'], gadget['flip']))

            labels.append(gadget["val"])


        sz = len(all_data)
        print(sz)
        train_slice = slice(sz // 5, sz)
        val_slice = slice(0, sz // 10)
        test_slice = slice(sz // 10, sz // 5)

        X_train, Y_train = X[train_slice], labels[train_slice]
        if self.rm_count > 0:
            X_train, Y_train = resample(X_train, Y_train, replace=False, n_samples=len(X_train) - self.rm_count, random_state=0)
        X_val, Y_val = X[val_slice], labels[val_slice]
        X_test, Y_test = X[test_slice], labels[test_slice]

        

        if self._config.res_folder == 'res_d2a_test':
            sz = len(all_data)
            train_slice = slice(sz // 10, sz)
            val_slice = slice(0, sz // 10)
            X_train, Y_train = X[train_slice], labels[train_slice]
            X_val, Y_val = X[val_slice], labels[val_slice]
            self.train_data = BufferedPathContext.create_from_lists(X_train, Y_train)
            self.val_data = BufferedPathContext.create_from_lists(X_val, Y_val)
            test_path = join(self._config.data_folder, self._config.name, self._config.dataset.name, 'true_test.json')
            X_test, Y_test = self.get_test(test_path, vectorizer)
            self.test_data = BufferedPathContext.create_from_lists(X_test, Y_test)
        else:
            self.train_data = BufferedPathContext.create_from_lists(X_train, Y_train)
            self.val_data = BufferedPathContext.create_from_lists(X_val, Y_val)
            self.test_data = BufferedPathContext.create_from_lists(X_test, Y_test)

        # TODO: download data from s3 if not exists

    def get_test(self, path, vectorizer):
        all_data = read_json(path)
        X = []
        labels = []
        count = 0
        for gadget in all_data:
            count += 1
            print("Processing gadgets...", count, end="\r")
            vector, backwards_slice = vectorizer.vectorize2(
                gadget["gadget"])  # [word len, embedding size]
            # vectors.append(vector)
            X.append((vector, gadget['xfg_id'], gadget['flip']))

            labels.append(gadget["val"])
        return X, labels


    def setup(self, stage: Optional[str] = None):
        # TODO: collect or convert vocabulary if needed
        pass

    @staticmethod
    def collate_wrapper(batch: List[SYSSample]) -> SYSBatch:
        return SYSBatch(batch)

    def create_dataloader(
        self,
        data: BufferedPathContext,
        seq_len: int,
        shuffle: bool,
        batch_size: int,
        n_workers: int,
    ) -> Tuple[DataLoader, int]:
        dataset = SYSDataset(data, seq_len, shuffle)
        dataloader = DataLoader(
            dataset,
            batch_size=batch_size,
            collate_fn=self.collate_wrapper,
            num_workers=n_workers,
            pin_memory=True,
        )
        return dataloader, dataset.get_n_samples()

    def train_dataloader(self, *args, **kwargs) -> DataLoader:
        
        
        dataloader, n_samples = self.create_dataloader(
            self.train_data,
            self._config.hyper_parameters.seq_len,
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
            self.val_data,
            self._config.hyper_parameters.seq_len,
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
            self.test_data,
            self._config.hyper_parameters.seq_len,
            self._config.hyper_parameters.shuffle_data,
            self._config.hyper_parameters.test_batch_size,
            self._config.num_workers,
        )
        print(
            f"\napproximate number of steps for test is {ceil(n_samples / self._config.hyper_parameters.test_batch_size)}"
        )
        self.test_n_samples = n_samples
        return dataloader

    def transfer_batch_to_device(self, batch: SYSBatch,
                                 device: torch.device) -> SYSBatch:
        batch.move_to_device(device)
        return batch
