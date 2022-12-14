#!/usr/bin/env python
# -*- encoding: utf-8 -*-
'''
@Description:       :
@Date     :2022/05/19 13:57:26
@Author      :ives-nx
@version      :1.0
'''
from __future__ import with_statement
import configparser
import json
from posixpath import join

import random
import numpy as np
from utils.vectorize_gadget import GadgetVectorizer
from utils.common import print_config, get_config
from argparse import ArgumentParser
from models.cl.dataset_build import PGDataset
from models.cl.my_cl_model import MY_VGD_GNN , MY_SYS_BGRU, MY_VDP_BLSTM, MY_REVEAL_GGNN, VGD_GNN
from cleanlab import latent_estimation
from cleanlab.pruning import get_noise_indices
from utils.json_ops import read_json, write_json
import os

from models.sysevr.buffered_path_context import BufferedPathContext as BPC_sys
from models.vuldeepecker.buffered_path_context import BufferedPathContext as BPC_vdp
from models.reveal.reveal_dataset_build import RevealDataset
from models.stacking.cv_ensemble_dwk import CV_ENSEMBLE_DWK , CL_CV_ENSEMBLE_DWK  
def get_data_json(data_path):
    with open(data_path,'r',encoding = 'utf8') as f:
        data_json = json.load(f)
        for key in data_json:           
            for idx,xfg in enumerate(data_json[key], start=0):
                xfg['xfg_id'] = idx
        f.close()
    return data_json

def cl_dwk_d2a_manualay(config):
    """
    @description  : confident learning with manually flipped noise dataset of d2a
    ---------
    @param  :
    -------
    @Returns  :
    -------
    """
    
    
    print_config(config)

    
    # confident learning for unfliped dataset
    true_vul_path = os.path.join(config.data_folder, 'CWES', config.dataset.name, '{}.json'.format('true_vul'))
    data_path = os.path.join(config.data_folder, 'CWES', config.dataset.name, '{}.json'.format(config.dataset.name))
    true_vul = read_json(true_vul_path)
    data_json = get_data_json(data_path)
    for data in data_json:
        for vul in true_vul:
            if data['target'] == vul['target'] \
                and data['vul_line'] == vul['vul_line'] \
                and data['filePath'] == vul['filePath']:
                data['target'] = data['target'] ^ 1
                data['flip'] = True

    data_geo = os.path.join(config.data_folder, 'cl', config.dataset.name, 'manual_noise')
    output_path = join(config.res_folder, config.name ,'cl_result', config.dataset.name, 'manual_noise.json')
    
    d2v_path = os.path.join(config.data_folder, 'CWES', config.dataset.name, 'd2v_model/{}.model'.format(config.dataset.name))
    # sz = len(data_json)
    # train_slice = slice(sz // 5, sz)
    # print(train_slice)
    
    
    print(d2v_path)
    dataset = PGDataset(data_json, data_geo, d2v_path=d2v_path)

    X, s, flipped, xfg_id = [data.x.tolist()[0] for data in dataset ], [data.y.tolist()[0] for data in dataset],[data.flip.tolist()[0] for data in dataset ], [data.xfg_id.tolist()[0] for data in dataset]

   
    
    result = dict()
    result['s'] = s
    result['flip'] = flipped
    result['xfg_id'] = xfg_id 

    psx = latent_estimation.estimate_cv_predicted_probabilities(
    np.array(X), np.array(s), clf=MY_VGD_GNN(config, dataset=dataset, no_cuda = False))
    result['psx'] = psx.tolist()

    ordered_label_errors = get_noise_indices(
        s=np.array(s),
        psx=psx
        # sorted_index_method='normalized_margin', # Orders label errors
    )
    error_labels = ordered_label_errors.tolist()
    result['error_label'] = error_labels
    print('cl_result', np.sum(np.array(flipped)[error_labels]), len(np.array(flipped)[error_labels]))
    if not os.path.exists(os.path.dirname(output_path)):
        os.makedirs(os.path.dirname(output_path))
    write_json(result, output=output_path)

def flip_data(method, src_data, noise_ids):
    if method in ['deepwukong', 'reveal']:
        key = 'target'
    else:
        key = 'val'
    for xfg in src_data:
        xfg_id = xfg['xfg_id']
        if xfg_id in noise_ids:
            xfg[key] = xfg[key] ^ 1
            xfg['flip'] = not xfg['flip']
    return src_data


def confident_learn_reveal(config, noise_rate = 0):
    """
    @description  : confident learning with different noise dataset for reveal model
    ---------
    @param  :
    -------
    @Returns  :
    -------
    """
    noise_key = '{}_percent'.format(int(noise_rate * 100))
    data_path = os.path.join(config.data_folder, config.name, config.dataset.name, '{}.json'.format(config.dataset.name))
    
    data_json = read_json(data_path)
    if config.noise_set not in ['training', 'all']:
        raise RuntimeError("False noise set !!")
    if config.noise_set == 'all':
        noise_info_path = join(config.data_folder, config.name, config.dataset.name, 'noise_info.json')
    elif config.noise_set == 'training':
        sz = len(data_json)
        train_slice = slice(sz // 5, sz)
        data_json = data_json[train_slice]
        noise_info_path = join(config.data_folder, config.name, config.dataset.name, 'training_noise_info.json')
    if noise_rate != 0:
        noise_info = read_json(noise_info_path)
        noise_xfg_ids = noise_info[noise_key]['noise_xfg_ids']
        flip_data(config.name, data_json, noise_xfg_ids)
    output_path = join(config.res_folder, config.name ,'cl_result', config.dataset.name, str(int(noise_rate * 100)) + '_percent_res.json')
    
    print(data_path)
    print('sample_count', len(data_json))
    geo_dir = join(config.geo_folder, config.name, config.dataset.name, 'geo')
    dataset = RevealDataset(config, geo_dir, data_json)
        

    X, s, flipped, xfg_id = [data.x.tolist()[0] for data in dataset ], [data.y.tolist()[0] for data in dataset],[data.flip.tolist()[0] for data in dataset ], [data.xfg_id.tolist()[0] for data in dataset]
    result = dict()
    result['s'] = s
    result['flip'] = flipped
    result['xfg_id'] = xfg_id 
    class_rate = (len(s) - np.array(s).sum()) / np.array(s).sum()
    confident_joint, psx = latent_estimation.estimate_confident_joint_and_cv_pred_proba(
    np.array(X), np.array(s), cv_n_folds=config.cl.cv_n_folds, thresholds=[0.6, 0.6], clf=MY_REVEAL_GGNN(config, dataset=dataset, no_cuda = False, class_rate = class_rate))
    result['psx'] = psx.tolist()

    print(confident_joint)
    ordered_label_errors = get_noise_indices(
        s=np.array(s),
        confident_joint=confident_joint,
        psx=psx
    )
    error_labels = ordered_label_errors.tolist()
    result['error_label'] = error_labels
    print('cl_result', np.sum(np.array(flipped)[error_labels]), len(np.array(flipped)[error_labels]), np.sum(np.array(flipped)))
    if not os.path.exists(os.path.dirname(output_path)):
        os.makedirs(os.path.dirname(output_path))
    write_json(result, output=output_path)
    
def ls(config, noise_rate = 0):
    from models.loss_selection.LS import MY_LS
    print_config(config)

    noise_key = '{}_percent'.format(int(noise_rate * 100))
    data_path = os.path.join(config.data_folder, 'CWES', config.dataset.name, '{}.json'.format(config.dataset.name))
    
    data_json = read_json(data_path)
    if config.noise_set not in ['training', 'all']:
        raise RuntimeError("False noise set !!")
    if config.noise_set == 'all':
        noise_info_path = join(config.data_folder, 'CWES', config.dataset.name, 'noise_info.json')
    elif config.noise_set == 'training':
        sz = len(data_json)
        train_slice = slice(sz // 5, sz)
        data_json = data_json[train_slice]
        noise_info_path = join(config.data_folder, 'CWES', config.dataset.name, 'training_noise_info.json')

    noise_info = read_json(noise_info_path)
    noise_xfg_ids = noise_info[noise_key]['noise_xfg_ids']
    flip_data(config.name, data_json, noise_xfg_ids)
    data_geo = os.path.join(config.data_folder, 'ls', config.dataset.name, '{}_{}_percent'.format(config.dataset.name, str(int(noise_rate*100))))
    output_path = join(config.res_folder, config.name ,'ls_result', config.dataset.name, str(int(noise_rate * 100)) + '_percent_res.json')

    print(data_path)
    d2v_path = os.path.join(config.data_folder, 'CWES', config.dataset.name, 'd2v_model/{}.model'.format(config.dataset.name))

    dataset = PGDataset(data_json, data_geo, d2v_path=d2v_path)
    X, s, flipped, xfg_id = [data.x.tolist()[0] for data in dataset ], [data.y.tolist()[0] for data in dataset],[data.flip.tolist()[0] for data in dataset ], [data.xfg_id.tolist()[0] for data in dataset]

   
    
    result = dict()
    result['s'] = s
    result['flip'] = flipped
    result['xfg_id'] = xfg_id 
    clf = MY_LS(config, dataset=dataset, no_cuda = False)
    confident_joint, psx = latent_estimation.estimate_confident_joint_and_cv_pred_proba(
    np.array(X), np.array(s), cv_n_folds=config.cl.cv_n_folds, thresholds=[0.6, 0.6], clf=clf)
    result['psx'] = psx.tolist()

    print(confident_joint)
    ordered_label_errors = get_noise_indices(
        s=np.array(s),
        confident_joint=confident_joint,
        psx=psx
    )
    error_labels = ordered_label_errors.tolist()
    result['error_label'] = error_labels
    result['cnt'] = clf.get_cnt_dict()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    write_json(result, output_path)
    
    
def confident_learn_dwk(config, noise_rate = 0):
    """
    @description  : confident learning with different noise dataset
    ---------
    @param  :
    -------
    @Returns  :
    -------
    """
    
    
    print_config(config)

    noise_key = '{}_percent'.format(int(noise_rate * 100))
    data_path = os.path.join(config.data_folder, 'CWES', config.dataset.name, '{}.json'.format(config.dataset.name))
    
    data_json = read_json(data_path)
    if config.noise_set not in ['training', 'all']:
        raise RuntimeError("False noise set !!")
    if config.noise_set == 'all':
        noise_info_path = join(config.data_folder, 'CWES', config.dataset.name, 'noise_info.json')
    elif config.noise_set == 'training':
        sz = len(data_json)
        train_slice = slice(sz // 5, sz)
        data_json = data_json[train_slice]
        noise_info_path = join(config.data_folder, 'CWES', config.dataset.name, 'training_noise_info.json')

    noise_info = read_json(noise_info_path)
    noise_xfg_ids = noise_info[noise_key]['noise_xfg_ids']
    flip_data(config.name, data_json, noise_xfg_ids)
    data_geo = os.path.join(config.data_folder, 'cl', config.dataset.name, '{}_{}_percent'.format(config.dataset.name, str(int(noise_rate*100))))
    output_path = join(config.res_folder, config.name ,'cl_result', config.dataset.name, str(int(noise_rate * 100)) + '_percent_res.json')

    print(data_path)
    d2v_path = os.path.join(config.data_folder, 'CWES', config.dataset.name, 'd2v_model/{}.model'.format(config.dataset.name))
    

        

    dataset = PGDataset(data_json, data_geo, d2v_path=d2v_path)

    X, s, flipped, xfg_id = [data.x.tolist()[0] for data in dataset], [data.y.tolist()[0] for data in dataset],[data.flip.tolist()[0] for data in dataset ], [data.xfg_id.tolist()[0] for data in dataset]

   
    
    result = dict()
    result['s'] = s
    result['flip'] = flipped
    result['xfg_id'] = xfg_id 

    confident_joint, psx = latent_estimation.estimate_confident_joint_and_cv_pred_proba(
    np.array(X), np.array(s), cv_n_folds=config.cl.cv_n_folds, thresholds=[0.6, 0.6], clf=MY_VGD_GNN(config, dataset=dataset, no_cuda = False))
    result['psx'] = psx.tolist()

    print(confident_joint)
    ordered_label_errors = get_noise_indices(
        s=np.array(s),
        confident_joint=confident_joint,
        psx=psx
    )
    error_labels = ordered_label_errors.tolist()
    result['error_label'] = error_labels
    print('cl_result', np.sum(np.array(flipped)[error_labels]), len(np.array(flipped)[error_labels]), np.sum(np.array(flipped)))
    if not os.path.exists(os.path.dirname(output_path)):
        os.makedirs(os.path.dirname(output_path))
    write_json(result, output=output_path)


def confident_learn_cv_ensemble_dwk(config, noise_rate = 0):
    """
    @description  : confident learning with different noise dataset
    ---------
    @param  :
    -------
    @Returns  :
    -------
    """
    
    
    print_config(config)
    model_config = get_config(config.dataset.name, 'deepwukong')
    noise_key = '{}_percent'.format(int(noise_rate * 100))
    data_path = os.path.join(config.data_folder, 'CWES', config.dataset.name, '{}.json'.format(config.dataset.name))
    
    data_json = read_json(data_path)
    if config.noise_set not in ['training', 'all']:
        raise RuntimeError("False noise set !!")
    if config.noise_set == 'all':
        noise_info_path = join(config.data_folder, 'CWES', config.dataset.name, 'noise_info.json')
    elif config.noise_set == 'training':
        sz = len(data_json)
        train_slice = slice(sz // 5, sz)
        data_json = data_json[train_slice]
        noise_info_path = join(config.data_folder, 'CWES', config.dataset.name, 'training_noise_info.json')

    noise_info = read_json(noise_info_path)
    noise_xfg_ids = noise_info[noise_key]['noise_xfg_ids']
    flip_data(model_config.name, data_json, noise_xfg_ids)
    data_geo = os.path.join(config.data_folder, 'cl', config.dataset.name, '{}_{}_percent'.format(config.dataset.name, str(int(noise_rate*100))))
    output_path = join(config.res_folder, config.name ,'cl_cv_dwk', config.dataset.name, str(int(noise_rate * 100)) + '_percent_res.json')

    print(data_path)
    d2v_path = os.path.join(config.data_folder, 'CWES', config.dataset.name, 'd2v_model/{}.model'.format(config.dataset.name))
    

        

    dataset = PGDataset(data_json, data_geo, d2v_path=d2v_path)

    X, s, flipped, xfg_id = [data.x.tolist()[0] for data in dataset], [data.y.tolist()[0] for data in dataset],[data.flip.tolist()[0] for data in dataset ], [data.xfg_id.tolist()[0] for data in dataset]

   
    
    result = dict()
    result['s'] = s
    result['flip'] = flipped
    result['xfg_id'] = xfg_id 

    confident_joint, psx = latent_estimation.estimate_confident_joint_and_cv_pred_proba(
    np.array(X), np.array(s), cv_n_folds=config.cl.cv_n_folds, thresholds=[0.6, 0.6], clf=CL_CV_ENSEMBLE_DWK(model_config,dataset=dataset, config=config, no_cuda = False))
    result['psx'] = psx.tolist()

    print(confident_joint)
    ordered_label_errors = get_noise_indices(
        s=np.array(s),
        confident_joint=confident_joint,
        psx=psx
    )
    error_labels = ordered_label_errors.tolist()
    result['error_label'] = error_labels
    print('cl_result', np.sum(np.array(flipped)[error_labels]), len(np.array(flipped)[error_labels]), np.sum(np.array(flipped)))
    if not os.path.exists(os.path.dirname(output_path)):
        os.makedirs(os.path.dirname(output_path))
    write_json(result, output=output_path)

def select_noise_from_cl_result(method, cwe_id, noise_rate):
    data_path = 'res/{}/cl_result/{}/{}_percent_res.json'.format(method, cwe_id, int(noise_rate*100))
    result = read_json(data_path)

    if method == 'deepwukong':
        id_key = 'xfg_id'
        flip_key = 'flip'
    else:
        id_key = 'idx'
        flip_key = 'flips'
    s = np.array(result['s'])
    psx = np.array(result['psx'])
    flipped = result[flip_key]
    ordered_label_errors = get_noise_indices(
        num_to_remove_per_class = (noise_rate * len(s) /2 ),
        s=np.array(s),
        psx=psx
    )
    error_labels = ordered_label_errors.tolist()


    xfg_ids = np.array(result['xfg_id'])

    
    rm_xfg_list = xfg_ids[error_labels].tolist()
    rm_xfg_list.sort()
    print('cl_result', np.sum(np.array(flipped)[error_labels]), len(np.array(flipped)[error_labels]), np.sum(np.array(flipped)))
    return rm_xfg_list


def confident_learn_sysevr(config, noise_rate = 0):
    """
    @description  : confident learning with different noise dataset
    ---------
    @param  :
    -------
    @Returns  :
    -------
    """
    
    
    print_config(config)
    dataset_dir = join(config.data_folder, config.name,
                                 config.dataset.name)
    data_path = os.path.join(dataset_dir, '{}.json'.format(config.dataset.name))
    all_data = read_json(data_path)
    w2v_path = os.path.join(dataset_dir, 'w2v.model')
    if config.noise_set not in ['training', 'all']:
        raise RuntimeError("False noise set !!")
    if config.noise_set == 'all':
        noise_info_path = join(config.data_folder, config.name, config.dataset.name, 'noise_info.json')
    elif config.noise_set == 'training':
        sz = len(all_data)
        train_slice = slice(sz // 5, sz)
        all_data = all_data[train_slice]
        noise_info_path = join(config.data_folder, config.name, config.dataset.name, 'training_noise_info.json')
    output_path = os.path.join(config.res_folder, config.name ,'cl_result', config.dataset.name, str(int(noise_rate * 100)) + '_percent_res.json')

    vectorizer = GadgetVectorizer(config)

    vectorizer.load_model(w2v_path=w2v_path)
    noise_key = '{}_percent'.format(int(noise_rate * 100))
    noise_info = read_json(noise_info_path)
    noise_xfg_ids = noise_info[noise_key]['noise_xfg_ids']
    
    
    all_data = flip_data(config.name, all_data, noise_xfg_ids)
    random.shuffle(all_data)
    X = []
    labels = []
    count = 0
    for gadget in all_data:
        count += 1
        # print("Processing gadgets...", count, end="\r")
        vector, backwards_slice = vectorizer.vectorize2(
            gadget["gadget"])  # [word len, embedding size]
        # vectors.append(vector)
        X.append((vector, gadget['xfg_id'], gadget['flip']))
        labels.append(gadget["val"])

    data = BPC_sys.create_from_lists(list(X), list(labels))
    
    
    X, s, idxs, flips = [i[0] for i in data], [i[1] for i in data], [i[3] for i in data], [i[4] for i in data]
    result = dict()
    

    # psx = latent_estimation.estimate_cv_predicted_probabilities(
    # np.array(data), np.array(s), cv_n_folds=config.cl.cv_n_folds, clf=MY_SYS_BGRU(config=config, data=data, no_cuda=False))
    confident_joint, psx = latent_estimation.estimate_confident_joint_and_cv_pred_proba(
    np.array(data), np.array(s), cv_n_folds=config.cl.cv_n_folds, thresholds=[0.6, 0.6], clf=MY_SYS_BGRU(config=config, data=data, no_cuda=False))
   

    ordered_label_errors = get_noise_indices(
        s=np.array(s),
        confident_joint=confident_joint,
        psx=psx
        # sorted_index_method='normalized_margin', # Orders label errors
    )
    error_labels = ordered_label_errors.tolist()
    all_info = list()
    for label, flip, idx, pre, el in zip(s, flips, idxs, psx.tolist(), error_labels):
        all_info.append((label, flip, idx, pre, el))
    result['all_info'] = all_info
    result['s'] = s
    result['flips'] = flips
    result['idx'] = idxs
    result['psx'] = psx.tolist()
    result['error_label'] = error_labels
    
    print('cl_result', np.sum(np.array(flips)[error_labels]), len(np.array(flips)[error_labels]), np.sum(np.array(flips)))
    if not os.path.exists(os.path.dirname(output_path)):
        os.makedirs(os.path.dirname(output_path))
    write_json(result, output=output_path)
    

    
    
def confident_learn_vdp(config, noise_rate = 0):
    """
    @description  : confident learning with different noise dataset
    ---------
    @param  :
    -------
    @Returns  :
    -------
    """
    
    
    
    print_config(config)
    dataset_dir = join(config.data_folder, config.name,
                                 config.dataset.name)
    data_path = os.path.join(dataset_dir, '{}.json'.format(config.dataset.name))
    all_data = read_json(data_path)
    w2v_path = os.path.join(dataset_dir, 'w2v.model')
    if config.noise_set not in ['training', 'all']:
        raise RuntimeError("False noise set !!")
    if config.noise_set == 'all':
        noise_info_path = join(config.data_folder, config.name, config.dataset.name, 'noise_info.json')
    elif config.noise_set == 'training':
        sz = len(all_data)
        train_slice = slice(sz // 5, sz)
        all_data = all_data[train_slice]
        noise_info_path = join(config.data_folder, config.name, config.dataset.name, 'training_noise_info.json')
    output_path = os.path.join(config.res_folder, config.name ,'cl_result', config.dataset.name, str(int(noise_rate * 100)) + '_percent_res.json')

    vectorizer = GadgetVectorizer(config)

    vectorizer.load_model(w2v_path=w2v_path)
    noise_key = '{}_percent'.format(int(noise_rate * 100))
    noise_info = read_json(noise_info_path)
    noise_xfg_ids = noise_info[noise_key]['noise_xfg_ids']
    
    
    all_data = flip_data(config.name, all_data, noise_xfg_ids)

    X = []
    labels = []
    count = 0
    for gadget in all_data:
        count += 1
        # print("Processing gadgets...", count, end="\r")
        vector, backwards_slice = vectorizer.vectorize2(
            gadget["gadget"])  # [word len, embedding size]
        # vectors.append(vector)
        X.append((vector, backwards_slice, gadget['xfg_id'], gadget['flip']))
        labels.append(gadget["val"])

    data = BPC_vdp.create_from_lists(list(X), list(labels))
    
    X, s, idxs, flips = [i[0] for i in data], [i[1] for i in data], [i[4] for i in data], [i[5] for i in data]
    result = dict()
    

    confident_joint, psx = latent_estimation.estimate_confident_joint_and_cv_pred_proba(
    np.array(data), np.array(s), cv_n_folds=config.cl.cv_n_folds, thresholds=[0.6, 0.6], clf=MY_VDP_BLSTM(config=config, data=data, no_cuda=False))
    

    ordered_label_errors = get_noise_indices(
        s=np.array(s),
        confident_joint=confident_joint,
        psx=psx
        # sorted_index_method='normalized_margin', # Orders label errors
    )
    error_labels = ordered_label_errors.tolist()

    all_info = list()

    for label, flip, idx, pre, el in zip(s, flips, idxs, psx.tolist(), error_labels):
        all_info.append((label, flip, idx, pre, el))
    result['all_info'] = all_info
    result['s'] = s
    result['flips'] = flips
    result['idx'] = idxs
    result['psx'] = psx.tolist()
    result['error_label'] = error_labels
    print('cl_result', np.sum(np.array(flips)[error_labels]), len(np.array(flips)[error_labels]), np.sum(np.array(flips)))
    if not os.path.exists(os.path.dirname(output_path)):
        os.makedirs(os.path.dirname(output_path))
    write_json(result, output=output_path)


def statistic(name, cl_result):
    xfg_ids = cl_result['xfg_id']
    flip = cl_result['flip']
    error_label = cl_result['error_label']
    r_count = 0
    fliped_count = 0
    all = len(error_label)
    xfg_id_list = []
    for idx in error_label:
        if flip[idx]:
            r_count += 1
            xfg_id_list.append(xfg_ids[idx])
    for id, f in zip(xfg_ids, flip):
        if f:
            fliped_count += 1
    print(name + ' r_count: {} r_rate: {} all {} flipped {}'.format(r_count, r_count/all, all, fliped_count) )
    return xfg_id_list

def write_json(json_dict, output):
    with open(output, 'w', encoding='utf8') as f:
        json.dump(json_dict,f,indent=2)
        f.close()

def get_cl_fun(method):
    funs = {
        'reveal': confident_learn_reveal,
        'deepwukong': confident_learn_dwk,
        'sysevr': confident_learn_sysevr,
        'vuldeepecker': confident_learn_vdp
    }

    return funs[method]


if __name__=="__main__":
    
    
    # python train.py token --dataset CWE119
    arg_parser = ArgumentParser()
    # arg_parser.add_argument("model", type=str)
    # arg_parser.add_argument("--dataset", type=str, default=None)
    arg_parser.add_argument("--offline", action="store_true")
    arg_parser.add_argument("--resume", type=str, default=None)
    args = arg_parser.parse_args()
    stack_config = get_config('CWE119','stack' ,log_offline=args.offline)
    # confident_learn_cv_ensemble_dwk(stack_config, noise_rate=0.1)
    confident_learn_cv_ensemble_dwk(stack_config, noise_rate=0.1)
    # confident_learn_cv_ensemble_dwk(stack_config, noise_rate=0.3)
    
    # config.res_folder = 'res'
    # config.noise_set = 'training'
    # cl_dwk_d2a_manualay(config)
    # CWES = [ 'CWE020', 'CWE022', 'CWE078', 'CWE125', 'CWE190', 'CWE400', 'CWE787']
    # for cwe in CWES:
    #     for method in ['vuldeepecker', 'sysevr']:
    #         for noise in [0.1,0.2,0.3]:
    #             print('Start cl {} with {} noise of {}...'.format(method, noise, cwe))

    #             config = getconfig_dwk(cwe, method, log_offline=args.offline)
    #             get_cl_fun(method)(config, noise_rate=noise)
                
    #             print('End cl {} with {} noise of {}...'.format(method, noise, cwe))
    # method = 'sysevr'
    # cwe = 'CWE078'
    # noise = 0.1
    # config = getconfig_dwk(cwe, method, log_offline=args.offline)
    # get_cl_fun(method)(config, noise_rate=noise)
    # confident_learn_vdp(config, 0.1)
    # confident_learn_vdp(config, 0.2)
    # confident_learn_vdp(config, 0.3)
    
    # cwe_ids = ['CWE119','CWE020',  'CWE125', 'CWE190', 'CWE400', 'CWE787']
    # cwe_ids = ['Devign']
    # for cwe_id in cwe_ids:
    #     for method in ['reveal']:
    #         try:
    #             config = get_config(cwe_id, method, log_offline=args.offline)
    #             config.res_folder = 'res1'
    #             config.noise_set = 'training'
    #             config.gpu = 0
    #             for noise_rate in [0.1, 0.2, 0.3]:
    #                 get_cl_fun(method)(config, noise_rate)
    #         except Exception as e:
    #             with open('log/error.log', 'a', encoding='utf8') as f:
    #                 f.write('{} {} {} \n'.format(cwe_id, method, e))
    # config = get_config('Devign', 'reveal', log_offline=args.offline)
    # config.res_folder = 'res1'
    # config.noise_set = 'training'
    # config.gpu = 1
    # confident_learn_reveal(config, 0.1)
    # ls(config, 0.2)
    
    # config = get_config('CWE125', 'sysevr', log_offline=args.offline)
    # confident_learn_sysevr(config,0)

    # confident_learn_sysevr(config, 0.1)
    # confident_learn_sysevr(config, 0.2)
    # confident_learn_sysevr(config, 0.3)
    # select_noise_from_cl_result('deepwukong', 'CWE119', 0.1)
    # select_noise_from_cl_result('deepwukong', 'CWE119', 0.2)
    # select_noise_from_cl_result('deepwukong', 'CWE119', 0.3)
    # select_noise_from_cl_result('deepwukong', 'CWE119', 0.4)