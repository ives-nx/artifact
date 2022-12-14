from argparse import ArgumentParser
import os
from os.path import join
from typing import Tuple
import json
import torch
import jsonlines
from omegaconf import DictConfig
from pytorch_lightning import seed_everything, Trainer, LightningModule, LightningDataModule
from pytorch_lightning.callbacks import ModelCheckpoint, EarlyStopping, LearningRateMonitor
from pytorch_lightning.loggers import WandbLogger, TensorBoardLogger
from models.sysevr.SYS_bgru import SYS_BGRU
from models.sysevr.SYS_data_module import SYSDataModule
import numpy as np
from utils.callback import UploadCheckpointCallback, PrintEpochResultCallback, CollectResCallback
from utils.common import print_config, filter_warnings, get_config_dwk
from utils.plot_result import plot_approach_f1, plot_cwe_f1
from statistic import get_dt_found_noise_ids




def train(config: DictConfig, json_data, method:str = None, noisy_rate:float = None, resume_from_checkpoint: str = None , rm_id_list: list = None, rm_count=0):
    """
    @description  : sysevr train 
    ---------
    @param  : 
                method: reduce noisy sample method : df or cl
                noisy_rate: 0.1, 0.2, 0.3
    -------
    @Returns  :
    -------
    """
    
    filter_warnings()
    print_config(config)
    # seed_everything(config.seed)
    model = SYS_BGRU(config)
    # if method == 'dt':
    #     data_module = SYSDataModule(config, json_data, 0)
    # else:
    data_module = SYSDataModule(config, json_data, noisy_rate=noisy_rate, rm_id_list = rm_id_list, rm_count=rm_count)
    
    # define logger
    # wandb logger
    # wandb_logger = WandbLogger(project=f"{config.name}-{config.dataset.name}",
    #                            log_model=True,
    #                            offline=config.log_offline)
    # wandb_logger.watch(model)
    # checkpoint_callback = ModelCheckpoint(
    #     dirpath=wandb_logger.experiment.dir,
    #     filename="{epoch:02d}-{val_loss:.4f}",
    #     period=config.save_every_epoch,
    #     save_top_k=-1,
    # )
    # upload_checkpoint_callback = UploadCheckpointCallback(
    #     wandb_logger.experiment.dir)

    # tensorboard logger
    tensorlogger = TensorBoardLogger(join("ts_logger", config.name),
                                     config.dataset.name)
    # define model checkpoint callback
    checkpoint_callback = ModelCheckpoint(
        dirpath=join(tensorlogger.log_dir, "checkpoints"),
        monitor="val_loss",
        filename="{epoch:02d}-{val_loss:.4f}",
        period=config.save_every_epoch,
        save_top_k=3,
    )
    upload_checkpoint_callback = UploadCheckpointCallback(
        join(tensorlogger.log_dir, "checkpoints"))

    # define early stopping callback
    early_stopping_callback = EarlyStopping(
        patience=config.hyper_parameters.patience,
        monitor="val_loss",
        verbose=True,
        mode="min")
    # define callback for printing intermediate result
    print_epoch_result_callback = PrintEpochResultCallback("train", "val")
    collect_test_res_callback = CollectResCallback(config, data_module , method, noisy_rate)
    # use gpu if it exists
    gpu = [0] if torch.cuda.is_available() else None
    print(gpu)
    # define learning rate logger
    lr_logger = LearningRateMonitor("step")
    trainer = Trainer(
        max_epochs=config.hyper_parameters.n_epochs,
        gradient_clip_val=config.hyper_parameters.clip_norm,
        deterministic=True,
        check_val_every_n_epoch=config.val_every_epoch,
        log_every_n_steps=config.log_every_epoch,
        logger=[tensorlogger],
        reload_dataloaders_every_epoch=config.hyper_parameters.
        reload_dataloader,
        gpus=gpu,
        progress_bar_refresh_rate=config.progress_bar_refresh_rate,
        callbacks=[
            lr_logger, early_stopping_callback, checkpoint_callback,
            print_epoch_result_callback, upload_checkpoint_callback,
            collect_test_res_callback
        ],
        resume_from_checkpoint=resume_from_checkpoint,
    )
    print(get_parameter_number(net=model))
    trainer.fit(model=model, datamodule=data_module)
    trainer.test()
    # trainer.test()

def get_parameter_number(net):
    total_num = sum(p.numel() for p in net.parameters())
    trainable_num = sum(p.numel() for p in net.parameters() if p.requires_grad)
    return {'Total': total_num, 'Trainable': trainable_num}

def read_json(path):
    json_dict = []
    with open(path, 'r', encoding='utf8') as f:
        
        json_dict = json.load(f)
        f.close()
    return json_dict


def statistic_cl_result(cl_result):
    idxs = cl_result['idx']
    flip = cl_result['flips']
    error_label = cl_result['error_label']
    r_count = 0
    fliped_count = 0
    all = len(error_label)
    rm_id_list = []
    for idx in error_label:
        if flip[idx]:
            r_count += 1
        rm_id_list.append(idxs[idx])
    for id, f in zip(idxs, flip):
        if f:
            fliped_count += 1
    print(' r_count: {} r_rate: {} all {} flipped {}'.format(r_count, r_count/all, all, fliped_count) )
    return rm_id_list

def sysevr_train(_config, noisy_rate:float=0):
    """
    @description  : train sysevr with noise or without
    ---------
    @param  : if noisy_rate is None , it will train sysevr without noise.
    -------
    @Returns  :
    -------
    """
    
    
    print_config(_config)
    data_path = os.path.join(_config.data_folder, 'sysevr', _config.dataset.name, '{}.json'.format(_config.dataset.name))
    data_json = read_json(data_path)
    train(_config, data_json, noisy_rate=noisy_rate)

def sysevr_dt_train(_config, noisy_rate):
    """
    @description  : train deepwukong after removing noisy samples found by df
    ---------
    @param  :
    -------
    @Returns  :
    -------
    """
    
    
    print_config(_config)
    data_path = os.path.join(_config.data_folder, 'sysevr', _config.dataset.name, '{}.json'.format(_config.dataset.name))
    data_json = read_json(data_path)
    rm_xfg_list = get_dt_found_noise_ids(_config, noisy_rate)
    print(len(rm_xfg_list))
    rm_xfg_list.sort()
    train(_config, data_json, 'dt', noisy_rate, rm_id_list=rm_xfg_list)

def sysevr_cl_train(_config, noisy_rate):
    """
    @description  : train sysevr after removing noisy samples found by cl 
    ---------
    @param  :
    -------
    @Returns  :
    -------
    """
    
    
    print_config(_config)
    data_path = os.path.join(_config.data_folder, 'sysevr', _config.dataset.name, '{}.json'.format(_config.dataset.name))
    data_json = read_json(data_path)
    # ws_fliped_path = '/home/niexu/project/python/deepwukong/data/diff_train/CWE119/flipped/bigjson_flip.json'
    cl_result_path = join(_config.res_folder, _config.name ,'cl_result', _config.dataset.name, str(int(noisy_rate * 100)) + '_percent_res.json')
    result = read_json(cl_result_path)
    
    idxs = np.array(result['idx'])

    error_labels = result['error_label']
    rm_id_list = idxs[error_labels].tolist()
    rm_id_list.sort()
    train(_config, data_json, 'cl', noisy_rate, rm_id_list=rm_id_list)



def sysevr_ds_train(_config, noisy_rate):
    """
    @description  : keep sample count in training set same as training set after removing cl result
    ---------
    @param  :
    -------
    @Returns  :
    -------
    """
    
    
    print_config(_config)
    data_path = os.path.join(_config.data_folder, 'sysevr', _config.dataset.name, '{}.json'.format(_config.dataset.name))
    data_json = read_json(data_path)
    # ws_fliped_path = '/home/niexu/project/python/deepwukong/data/diff_train/CWE119/flipped/bigjson_flip.json'
    cl_result_path = join(_config.res_folder, _config.name ,'cl_result', _config.dataset.name, str(int(noisy_rate * 100)) + '_percent_res.json')
    result = read_json(cl_result_path)
    
    idxs = np.array(result['idx'])

    error_labels = result['error_label']
    rm_id_list = idxs[error_labels].tolist()
    rm_id_list.sort()
    train(_config, data_json, 'ds', noisy_rate, rm_count=len(rm_id_list))


if __name__ == "__main__":
   
    arg_parser = ArgumentParser()
    # arg_parser.add_argument("model", type=str)
    # arg_parser.add_argument("--dataset", type=str, default=None)
    arg_parser.add_argument("--offline", action="store_true")
    arg_parser.add_argument("--resume", type=str, default=None)
    args = arg_parser.parse_args()
    # cwe_ids = ['CWE119', 'CWE020', 'CWE125', 'CWE190', 'CWE400', 'CWE787']
    # for cwe_id in cwe_ids:
        
    #     _config = get_config_dwk(cwe_id,'sysevr' ,log_offline=args.offline)
    #     _config.res_folder = 'res'
    #     _config.noise_set = 'all'
        # sysevr_train(_config)
        # sysevr_train(_config,0.1)
        # sysevr_train(_config,0.2)
        # sysevr_train(_config,0.3)
        # sysevr_cl_train(_config, noisy_rate=0.1)
        # sysevr_ds_train(_config, noisy_rate=0.1)
        # sysevr_cl_train(_config, noisy_rate=0.2)
        # sysevr_ds_train(_config, noisy_rate=0.2)
        # sysevr_cl_train(_config, noisy_rate=0.3)
        # sysevr_ds_train(_config, noisy_rate=0.3)
    #     sysevr_dt_train(_config,0.1)
    #     sysevr_dt_train(_config,0.2)
    #     sysevr_dt_train(_config,0.3)
    # print('end')
    _config = get_config_dwk('INTEGER_OVERFLOW','sysevr' ,log_offline=args.offline)
    _config.res_folder = 'res_d2a2'
    _config.noise_set = 'all'
    sysevr_train(_config,0)
    # _config = get_config_dwk('INTEGER_OVERFLOW','sysevr' ,log_offline=args.offline)
    # sysevr_cl_train(_config, 0)



 
   