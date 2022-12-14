from argparse import ArgumentParser
import os
from os.path import join
import json
# from vuldeepecker.VDP_data_module import VDPDataModule
import torch
import jsonlines
from omegaconf import DictConfig
from pytorch_lightning import seed_everything, Trainer, LightningModule, LightningDataModule
from models.dt.pytorchtools import EarlyStopping as es
from pytorch_lightning.callbacks import ModelCheckpoint, EarlyStopping, LearningRateMonitor
from pytorch_lightning.loggers import WandbLogger, TensorBoardLogger
from utils.callback import UploadCheckpointCallback, PrintEpochResultCallback, CollectResCallback
from models.dt.VGD_gnn import VGD_GNN
from models.dt.VGD_data_module import VGDDataModule
from models.dt.xfg_flip import dwk_downsample
from models.dt.SYS_bgru_dt import SYS_BGRU
from models.dt.SYS_data_module_dt import SYSDataModule
from models.dt.VDP_data_module_dt import VDPDataModule
from models.dt.VDP_blstm_dt import VDP_BLSTM
from utils.common import print_config, filter_warnings, get_config_dwk
from models.dt.outlier import get_train_data,vote
from models.sysevr.buffered_path_context import BufferedPathContext as BPC_sys
from models.vuldeepecker.buffered_path_context import BufferedPathContext as BPC_vdp
from confident_learning import flip_data, get_data_json, write_json
from models.cl.dataset_build import PGDataset
from models.cl.my_cl_model import MY_VGD_GNN , MY_SYS_BGRU, MY_VDP_BLSTM
from utils.vectorize_gadget import GadgetVectorizer
import numpy as np
import random
from models.dt.fold_cv import my_cv

def read_json(path):
    json_dict = []
    with open(path, 'r', encoding='utf8') as f:
        
        json_dict = json.load(f)
        f.close()
    return json_dict

def flip_noisy_xfg(outlier_list, ws, dropout):
    """
    @description  : remove the noisy samples found by last iteration 
    ---------
    @param  :
    -------
    @Returns  :
    -------
    """
    
    
    outlier_xfg_id = []
    for outlier in outlier_list:
        
        xfg_id = int(outlier[0])
        outlier_xfg_id.append(xfg_id)

    flip_xfg_id = []
    for xfg in ws:
        xfg_id = xfg['xfg_id']
        random_t = random.uniform(0,1)
        if xfg_id in outlier_xfg_id and  random_t >= dropout:
            flip_xfg_id.append(xfg_id)
            if 'target' in xfg.keys():
                key = 'target'
            else:
                key = 'val'
            xfg[key] = xfg[key] ^ 1
            xfg['flip'] = not xfg['flip']  

    flip_outlier_list = []
    for outlier in outlier_list:
        
        xfg_id = int(outlier[0])
        if xfg_id in flip_xfg_id:
            flip_outlier_list.append(outlier)

    
    return flip_outlier_list, ws

def remove_noisy_xfg(outlier_list, ws):
    """
    @description  : remove the noisy samples found by last iteration 
    ---------
    @param  :
    -------
    @Returns  :
    -------
    """
    
    
    outlier_xfg_id = []
    for outlier in outlier_list:
        
        xfg_id = int(outlier[0])
        outlier_xfg_id.append(xfg_id)

    re_list = []
    for xfg in ws:
        xfg_id = xfg['xfg_id']
        if xfg_id in outlier_xfg_id:
            continue
        re_list.append(xfg)    
    
    return outlier_xfg_id, re_list

def get_parameter_number(net):
    total_num = sum(p.numel() for p in net.parameters())
    trainable_num = sum(p.numel() for p in net.parameters() if p.requires_grad)
    return {'Total': total_num, 'Trainable': trainable_num}





def dwk_train(config: DictConfig, json_data, ds_idx, noisy_rate:float = None, type:str = None, resume_from_checkpoint: str = None ):
    filter_warnings()
    # seed_everything(config.seed)
    model = VGD_GNN(config)
    data_module = VGDDataModule(config, json_data, noisy_rate, type)
    
    loss_dict = model.my_train(data_module=data_module, ds_idx=ds_idx)
    # define learning rate logger
    
    
    return loss_dict

def dwk_dt_one(_config, ws, contamination,noisy_rate = None):
    """
    @description  : train once dt
    ---------
    @param  :
    -------
    @Returns  :
    -------
    """
    
    
    # dds_loss = []
    # wds_loss = []
    ds, ds_idx = dwk_downsample(ws, _config.dt.ds_count, noisy_rate)
    
    

    dds_loss = dwk_train(_config, ds, ds_idx, noisy_rate, 'ds')
    wds_loss = dwk_train(_config, ws, ds_idx, noisy_rate, 'ws')
    
    write_json(dds_loss, 'dds_loss.json')
    write_json(wds_loss, 'wds_loss.json')



    vote_rate =  _config.dt.vote_rate
    X_train, Y_train, flipped, xfg_ids = get_train_data(ws, wds_loss, dds_loss)
    outlier_list = vote(X_train, Y_train, flipped, vote_rate, xfg_ids, contamination)
    
    
    



    return outlier_list


def dwk_dt(_config, noisy_rate = 0):
    """
    @description  :differential training with different noisy dataset 
    ---------
    @param  :
    -------
    @Returns  :
    -------
    """
    
    
    print_config(_config)
  
    noise_key = '{}_percent'.format(int(noisy_rate * 100))
    noise_info_path = os.path.join(_config.data_folder, 'CWES', _config.dataset.name, 'noise_info.json')
    noise_info = read_json(noise_info_path)
    noise_xfg_ids = noise_info[noise_key]['noise_xfg_ids']
    data_path = os.path.join(_config.data_folder, 'CWES', _config.dataset.name, '{}.json'.format(_config.dataset.name))
    data_json = read_json(data_path)

    flip_data(_config.name, data_json, noise_xfg_ids)
    outlier_result_path = join(_config.res_folder,_config.dt.model_name,'dt_result', _config.dataset.name, str(int(noisy_rate * 100)) + '_percent_res.jsonl')
    
    out_ws_path = join(_config.res_folder,_config.dt.model_name,'dt_result', _config.dataset.name, str(int(noisy_rate * 100)) + '_percent_ws.json')
    
    
    ws = data_json
    
    if not os.path.exists(os.path.dirname(outlier_result_path)):
        os.makedirs(os.path.dirname(outlier_result_path))
   

    early_stopping = es(patience=3, verbose=True, delta=_config.dt.delta)
    drop_out = _config.dt.drop_out
    iter = 0
    iter_count = 20
    while True:
        accuracy = cv_dwk(_config, ws, noisy_rate)
        print(1- accuracy)
        early_stopping(1 - accuracy)
        if  early_stopping.early_stop:
            print("Differential training early stopping")
		    # ??????????????????
            break 
        contamination = (1 - accuracy) * 0.7
        outlier_list = dwk_dt_one(_config, ws, contamination, noisy_rate)
        log_dict = dict()
        outlier_list, ws = flip_noisy_xfg(outlier_list, ws, drop_out)
        log_dict['iter'] = iter
        log_dict['outlier_list'] = outlier_list
        found_rate = len(outlier_list) / _config.dt.ds_count
        log_dict['noisy_rate'] = found_rate
        log_dict['noise_count'] = len(outlier_list)
        f=jsonlines.open(outlier_result_path,"a")
        jsonlines.Writer.write(f,log_dict)
        f.close()
        # break
        iter += 1
        
        # ????????? early stopping ??????
        write_json(ws, output=out_ws_path)
        
         

def sys_dt(_config, noisy_rate = 0):
    """
    @description  : differential training for sysevr
    ---------
    @param  :
    -------
    @Returns  :
    -------
    """
    print_config(_config)

    noise_key = '{}_percent'.format(int(noisy_rate * 100))
    noise_info_path = os.path.join(_config.data_folder, _config.name, _config.dataset.name, 'noise_info.json')
    noise_info = read_json(noise_info_path)
    noise_xfg_ids = noise_info[noise_key]['noise_xfg_ids']
    data_path = os.path.join(_config.data_folder, _config.name, _config.dataset.name, '{}.json'.format(_config.dataset.name))
    data_json = read_json(data_path)

    flip_data(_config.name, data_json, noise_xfg_ids)
    outlier_result_path = join(_config.res_folder,_config.dt.model_name,'dt_result', _config.dataset.name, str(int(noisy_rate * 100)) + '_percent_res.jsonl')
    
    out_ws_path = join(_config.res_folder,_config.dt.model_name,'dt_result', _config.dataset.name, str(int(noisy_rate * 100)) + '_percent_ws.json')
    print(data_path)
    ws = data_json
    if not os.path.exists(os.path.dirname(outlier_result_path)):
        os.makedirs(os.path.dirname(outlier_result_path))

    early_stopping = es(patience=3, verbose=True, delta=_config.dt.delta)
    drop_out = _config.dt.drop_out
    iter = 0
  

    #?????? res.jsonl??????????????????????????????
    if os.path.exists(outlier_result_path):
        ws = read_json(out_ws_path)
        f = open(outlier_result_path, 'r')
        iter = len(f.readlines())
        f.close()
    while True:
        accuracy = cv_sysevr(_config, ws, noisy_rate)
        print(1- accuracy)
        early_stopping(1 - accuracy)
        if  early_stopping.early_stop:
            print("Differential training early stopping")
		    # ??????????????????
            break 
        contamination = (1 - accuracy) * 0.7
        outlier_list = sys_dt_one(_config, ws, contamination, noisy_rate)
        log_dict = dict()
        outlier_list, ws = flip_noisy_xfg(outlier_list, ws, drop_out)
        log_dict['iter'] = iter
        log_dict['outlier_list'] = outlier_list
        found_rate = len(outlier_list) / _config.dt.ds_count
        log_dict['noisy_rate'] = found_rate
        log_dict['noise_count'] = len(outlier_list)
        f=jsonlines.open(outlier_result_path,"a")
        # grid_dict = dict()
        # t_c = 0
        # for outlier in outlier_list:
        #     if outlier[2] == True:
        #         t_c += 1
            
        # grid_dict['n_epoch'] = _config.dt.n_epochs
        # grid_dict['vote_rate'] = _config.dt.vote_rate
        # grid_dict['ds_count'] = _config.dt.ds_count
        # grid_dict['tp'] = t_c
        # grid_dict['fp'] = len(outlier_list) - t_c
        # grid_dict['all'] = len(outlier_list)
        # grid_dict['tpr'] = t_c / len(outlier_list)
        # grid_dict['fpr'] = (len(outlier_list) - t_c) / len(outlier_list) 
        jsonlines.Writer.write(f,log_dict)
        f.close()
        # break
        iter += 1
        
        # ????????? early stopping ??????
        write_json(ws, output=out_ws_path)

def sys_dt_one(_config, ws, contamination, noisy_rate):
    """
    @description  : train once dt for sysevr
    ---------
    @param  :
    -------
    @Returns  :
    -------
    """
    ds, ds_idx = dwk_downsample(ws, _config.dt.ds_count, noisy_rate)
    # log_dict_list = list()
    # flip_ids = []
    # for xfg in ws:
    #     xfg_id = xfg['xfg_id']
    #     if xfg['flip']:
    #         flip_ids.append(xfg_id)
    
    dds_loss = sys_train(_config, ds, ds_idx, noisy_rate, 'ds')
    wds_loss = sys_train(_config, ws, ds_idx, noisy_rate, 'ws')
    
    # for loss_id in wds_loss:
    #     log_dict = dict()
    #     log_dict['xfg_id'] = int(loss_id)
    #     log_dict['ws_loss'] = wds_loss[loss_id]
    #     log_dict['ds_loss'] = dds_loss[loss_id]
        
    #     if int(loss_id) in flip_ids:
    #         log_dict['flip'] = True
    #     else:
    #         log_dict['flip'] = False
    #     log_dict_list.append(log_dict)
    # write_json(dds_loss, 'dds_loss.json')
    # write_json(wds_loss, 'wds_loss.json')
    # write_json(log_dict_list, 'loss_dict.json')
    
    vote_rate = _config.dt.vote_rate
    X_train, Y_train, flipped, idxs = BPC_sys.get_loss_vector(ws, wds_loss, dds_loss)
    outlier_list = vote(X_train, Y_train, flipped, vote_rate, idxs, contamination)
    
    return outlier_list
    
def sys_train(config, data_json, ds_idx, noise_rate, type):
    filter_warnings()
    # seed_everything(config.seed)
    data_module = SYSDataModule(config, data_json, noise_rate, type)
    model = SYS_BGRU(config)
    loss_dict = model.my_train(data_module=data_module, ds_idx=ds_idx)
    
    # define learning rate logger
    return loss_dict
   
def vdp_dt(_config, noisy_rate = 0):
    """
    @description  : differential training for vuldeepecker
    ---------
    @param  :
    -------
    @Returns  :
    -------
    """
    print_config(_config)

    noise_key = '{}_percent'.format(int(noisy_rate * 100))
    noise_info_path = os.path.join(_config.data_folder, _config.name, _config.dataset.name, 'noise_info.json')
    noise_info = read_json(noise_info_path)
    noise_xfg_ids = noise_info[noise_key]['noise_xfg_ids']
    data_path = os.path.join(_config.data_folder, _config.name, _config.dataset.name, '{}.json'.format(_config.dataset.name))
    data_json = read_json(data_path)


    flip_data(_config.name, data_json, noise_xfg_ids)
    outlier_result_path = join(_config.res_folder,_config.dt.model_name,'dt_result', _config.dataset.name, str(int(noisy_rate * 100)) + '_percent_res.jsonl')
 
    out_ws_path = join(_config.res_folder,_config.dt.model_name,'dt_result', _config.dataset.name, str(int(noisy_rate * 100)) + '_percent_ws.json')
    print(data_path)
    ws = data_json
    if not os.path.exists(os.path.dirname(outlier_result_path)):
        os.makedirs(os.path.dirname(outlier_result_path))

    early_stopping = es(patience=3, verbose=True, delta=_config.dt.delta)
    drop_out = _config.dt.drop_out
    iter = 0
    

    #?????? res.jsonl??????????????????????????????
    if os.path.exists(outlier_result_path):
        ws = read_json(out_ws_path)
        f = open(outlier_result_path, 'r')
        iter = len(f.readlines())
        f.close()
    while True:
        accuracy = cv_vuldeepecker(_config, ws, noisy_rate)
        print('accuracy:', 1- accuracy)
        early_stopping(1 - accuracy)
        if  early_stopping.early_stop:
            print("Differential training early stopping")
		    # ??????????????????
            break 
        contamination = (1 - accuracy) * 0.7
        outlier_list = vdp_dt_one(_config, ws, contamination, noisy_rate)
        log_dict = dict()
        outlier_list, ws = flip_noisy_xfg(outlier_list, ws, drop_out)
        log_dict['iter'] = iter
        log_dict['outlier_list'] = outlier_list
        found_rate = len(outlier_list) / _config.dt.ds_count
        log_dict['noisy_rate'] = found_rate
        log_dict['noise_count'] = len(outlier_list)
        f=jsonlines.open(outlier_result_path,"a")
        # grid_dict = dict()
        # t_c = 0
        # for outlier in outlier_list:
        #     if outlier[2] == True:
        #         t_c += 1
            
        # grid_dict['n_epoch'] = _config.dt.n_epochs
        # grid_dict['vote_rate'] = _config.dt.vote_rate
        # grid_dict['ds_count'] = _config.dt.ds_count
        # grid_dict['tp'] = t_c
        # grid_dict['fp'] = len(outlier_list) - t_c
        # grid_dict['all'] = len(outlier_list)
        # grid_dict['tpr'] = t_c / len(outlier_list)
        # grid_dict['fpr'] = (len(outlier_list) - t_c) / len(outlier_list) 
        jsonlines.Writer.write(f,log_dict)
        f.close()
        # break
        iter += 1
        
        # ????????? early stopping ??????
        write_json(ws, output=out_ws_path)

def vdp_dt_one(_config, ws, contamination, noisy_rate):
    """
    @description  : train once dt for sysevr
    ---------
    @param  :
    -------
    @Returns  :
    -------
    """
    ds, ds_idx = dwk_downsample(ws, _config.dt.ds_count, noisy_rate)
   
    dds_loss = vdp_train(_config, ds, ds_idx, noisy_rate, 'ds')
    wds_loss = vdp_train(_config, ws, ds_idx, noisy_rate, 'ws')
    
    vote_rate = _config.dt.vote_rate
    X_train, Y_train, flipped, idxs = BPC_sys.get_loss_vector(ws, wds_loss, dds_loss)
    outlier_list = vote(X_train, Y_train, flipped, vote_rate, idxs, contamination)
    
    return outlier_list    
    


def vdp_train(config, data_json, ds_idx, noise_rate, type):
    filter_warnings()
    # seed_everything(config.seed)
    data_module = VDPDataModule(config, data_json, noise_rate, type)
    model = VDP_BLSTM(config)
    loss_dict = model.my_train(data_module=data_module, ds_idx=ds_idx)
    
    return loss_dict

def cv_dwk(_config, ws, noisy_rate = 0):
    """
    @description  : confident learning with different noisy dataset
    ---------
    @param  :
    -------
    @Returns  :
    -------
    """
    
    
    print_config(_config)

    noise_key = '{}_percent'.format(int(noisy_rate * 100))

    data_geo = os.path.join(_config.data_folder, 'cl', _config.dataset.name, '{}_{}_percent'.format(_config.dataset.name, str(int(noisy_rate*100))))
    


    d2v_path = os.path.join(_config.data_folder, 'CWES', _config.dataset.name, 'd2v_model/{}.model'.format(_config.dataset.name))

   

    dataset = PGDataset(ws, data_geo, d2v_path=d2v_path)

    X, s = [data.x.tolist()[0] for data in dataset ], [data.y.tolist()[0] for data in dataset]

   
    
    
    # _config.cl.n_epochs = 50
    accuracy = my_cv(
    np.array(X), np.array(s), cv_n_folds=5, clf=MY_VGD_GNN(_config, dataset=dataset, no_cuda = False))
    return accuracy

def cv_sysevr(config, ws, noisy_rate = 0):
    """
    @description  : cross-validation
    ---------
    @param  :
    -------
    @Returns  :
    -------
    """
    
    
    print_config(config)
    dataset_dir = join(config.data_folder, config.name,
                                 config.dataset.name)
    w2v_path = os.path.join(dataset_dir, 'w2v.model')
    vectorizer = GadgetVectorizer(config)
    vectorizer.load_model(w2v_path=w2v_path)

    X = []
    labels = []
    count = 0
    for gadget in ws:
        count += 1
        # print("Processing gadgets...", count, end="\r")
        vector, backwards_slice = vectorizer.vectorize2(
            gadget["gadget"])  # [word len, embedding size]
        # vectors.append(vector)
        X.append((vector, gadget['xfg_id'], gadget['flip']))
        labels.append(gadget["val"])

    data = BPC_sys.create_from_lists(list(X), list(labels))
    X, s = [i[0] for i in data], [i[1] for i in data]

    accuracy = my_cv(
    np.array(data), np.array(s), cv_n_folds=5, clf=MY_SYS_BGRU(config=config, data=data, no_cuda=False))
   
    return accuracy

def cv_vuldeepecker(config, ws, noisy_rate = 0):
    """
    @description  : cross-validation
    ---------
    @param  :
    -------
    @Returns  :
    -------
    """
    
    
    print_config(config)
    dataset_dir = join(config.data_folder, config.name,
                                 config.dataset.name)
    w2v_path = os.path.join(dataset_dir, 'w2v.model')
    vectorizer = GadgetVectorizer(config)
    vectorizer.load_model(w2v_path=w2v_path)

    X = []
    labels = []
    count = 0
    for gadget in ws:
        count += 1
        # print("Processing gadgets...", count, end="\r")
        vector, backwards_slice = vectorizer.vectorize2(
            gadget["gadget"])  # [word len, embedding size]
        # vectors.append(vector)
        X.append((vector, backwards_slice, gadget['xfg_id'], gadget['flip']))
        labels.append(gadget["val"])

    data = BPC_vdp.create_from_lists(list(X), list(labels))
    X, s = [i[0] for i in data], [i[1] for i in data]

    accuracy = my_cv(
    np.array(data), np.array(s), cv_n_folds=5, clf=MY_VDP_BLSTM(config=config, data=data, no_cuda=False))
   
    return accuracy


if __name__ == "__main__":
    
    
    # python train.py token --dataset CWE119
    arg_parser = ArgumentParser()
    # arg_parser.add_argument("model", type=str)
    # arg_parser.add_argument("--dataset", type=str, default=None)
    arg_parser.add_argument("--offline", action="store_true")
    arg_parser.add_argument("--resume", type=str, default=None)
    args = arg_parser.parse_args()
    _config = get_config_dwk('CWE119','deepwukong' ,log_offline=args.offline)

    # ds_counts = [3000, 3500, 4000, 4500, 5000, 5500, 6000]
    # vote_rates = [0.6, 0.7, 0.8, 0.9]
    # n_epochs = [10, 20, 30, 40, 50]
    

    # for n in n_epochs:
    #     for vote_rate in vote_rates:
    #         for ds_count in ds_counts:
    #             _config.dt.ds_count = ds_count
    #             _config.dt.vote_rate = vote_rate
    #             _config.dt.n_epochs = n
    #             sys_dt(_config, noisy_rate=0.1)
    _config.dt.ds_count = 10000
    _config.dt.vote_rate = 0.8
    _config.dt.n_epochs = 20
    _config.res_folder = 'res'
    _config.noise_set = 'all'
    _config.gpu = 1
    noisy_rate = 0.3
    print('noise_rate: ', noisy_rate)
    dwk_dt(_config, noisy_rate)
 
    # _config = get_config_dwk('INTEGER_OVERFLOW','dtt' ,log_offline=args.offline)
    # sys_dt(_config, noisy_rate=0.3)
    # sys_dt(_config, noisy_rate=0.2)
    # sys_dt(_config, noisy_rate=0.3)

    # differential_training(_config)
    # differential_training(_config, 0.2)
    # differential_training(_config, 0.3)
    # accuracy = cv_dwk(_config, 0.1)
    # print(accuracy)
    