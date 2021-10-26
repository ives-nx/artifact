#!/usr/bin/env python
# -*- encoding: utf-8 -*-
'''
@Description:       :  statistic all data 
@Date     :2021/08/15 19:46:44
@Author      :ives-nx
@version      :1.0
'''
import json
from logging import error
import os
import jsonlines
from numpy.lib.utils import info
from scipy.sparse import data
from models.sysevr.buffered_path_context import BufferedPathContext as BPC_sys
from models.vuldeepecker.buffered_path_context import BufferedPathContext as BPC_vdp
from utils.json_ops import read_json, write_json
from functools import reduce
import numpy as np
import math
from argparse import ArgumentParser
from utils.common import print_config, filter_warnings, get_config_dwk
def statistic_dwk_data(cwe_id:str, noisy_rate:float = None):
    """
    @description  : statistic data distribution for deepwukong
    ---------
    @param  :
    -------
    @Returns  :
    -------
    """
    
    
    if noisy_rate:
        data_path = 'data/CWES/{}/{}_{}_percent.json'.format(cwe_id, cwe_id, int(noisy_rate * 100))
        data = read_json(data_path)
        all_xfg_count = len(data)
        safe_count = 0
        vul_count = 0
        fliped_count = 0
        fliped_safe_count = 0
        fliped_vul_count = 0
        for xfg in data:
            if xfg['target'] == 1:
                vul_count += 1
            else:
                safe_count += 1
            if xfg['flip']:
                fliped_count += 1
                if xfg['target'] == 1:
                    fliped_safe_count += 1
                else:
                    fliped_vul_count += 1
        result = dict()
        result['title'] = 'dwk_{}_{}_percent'.format(cwe_id, int(noisy_rate * 100))
        result['all_xfg_count'] = all_xfg_count
        result['safe_count'] = safe_count
        result['vul_count'] = vul_count
        result['fliped_count'] = fliped_count
        result['fliped_safe_count'] = fliped_safe_count
        result['fliped_vul_count'] = fliped_vul_count
    else:
        data_path = 'data/CWES/{}/{}.json'.format(cwe_id, cwe_id)
        data = read_json(data_path)
        all_xfg_count = len(data)
        safe_count = 0
        vul_count = 0
        fliped_count = 0
        fliped_safe_count = 0
        fliped_vul_count = 0
        for xfg in data:
            if xfg['target'] == 1:
                vul_count += 1
            else:
                safe_count += 1
        result = dict()
        result['title'] = 'dwk_{}_{}_percent'.format(cwe_id, 0)
        result['all_xfg_count'] = all_xfg_count
        result['safe_count'] = safe_count
        result['vul_count'] = vul_count
    print(result)
    return result

def statistic_sys_data(cwe_id:str, noisy_rate:float = None):
    """
    @description  : statistic data distribution for sysevr
    ---------
    @param  :
    -------
    @Returns  :
    -------
    """
    if noisy_rate:
        data_path = 'data/sysevr/{}/{}_{}_percent.pkl'.format(cwe_id, cwe_id, int(noisy_rate * 100))
    else:
        data_path = 'data/sysevr/{}/train.pkl'.format(cwe_id)
    data = BPC_sys.joblib_load(data_path)
    all_cdg_count = len(data)
    safe_count = 0
    vul_count = 0
    fliped_count = 0
    fliped_safe_count = 0
    fliped_vul_count = 0
    for d in data:
        if d[1] == 1:
            vul_count += 1
        else:
            safe_count += 1
        if d[4]:
            fliped_count += 1
            if d[1] == 1:
                fliped_safe_count += 1
            else:
                fliped_vul_count += 1
    result = dict()
    result['title'] = 'sys_{}_{}_percent'.format(cwe_id, int(noisy_rate * 100))
    result['all_cdg_count'] = all_cdg_count
    result['safe_count'] = safe_count
    result['vul_count'] = vul_count
    result['fliped_count'] = fliped_count
    result['fliped_safe_count'] = fliped_safe_count
    result['fliped_vul_count'] = fliped_vul_count
    print(result)
    return result
def statistic_vdp_data(cwe_id:str, noisy_rate:float = None):

    if noisy_rate:
        data_path = 'data/vuldeepecker/{}/{}_{}_percent.pkl'.format(cwe_id, cwe_id, int(noisy_rate * 100))
    else:
        data_path = 'data/vuldeepecker/{}/train.pkl'.format(cwe_id)
    data = BPC_vdp.joblib_load(data_path)
    all_cdg_count = len(data)
    safe_count = 0
    vul_count = 0
    fliped_count = 0
    fliped_safe_count = 0
    fliped_vul_count = 0
    for d in data:
        if d[1] == 1:
            vul_count += 1
        else:
            safe_count += 1
        if d[5]:
            fliped_count += 1
            if d[1] == 1:
                fliped_safe_count += 1
            else:
                fliped_vul_count += 1
    result = dict()
    result['title'] = 'vdp_{}_{}_percent'.format(cwe_id, int(noisy_rate * 100))
    result['all_cdg_count'] = all_cdg_count
    result['safe_count'] = safe_count
    result['vul_count'] = vul_count
    result['fliped_count'] = fliped_count
    result['fliped_safe_count'] = fliped_safe_count
    result['fliped_vul_count'] = fliped_vul_count
    print(result)
    return result


def statistic_cl_result(config, noisy_rate:float = None):
    """
    @description  : statistic confident learning result
    ---------
    @param  :
    -------
    @Returns  :
    -------
    """
    method = config.name
    cwe_id = config.dataset.name
    res = config.res_folder
    if method not in ['deepwukong', 'sysevr', 'vuldeepecker']:
        raise RuntimeError('{} name error !'.format(method))

    # if noisy_rate not in [0.1, 0.2, 0.3, 0.4]:
    #     raise RuntimeError('{} noisy rate error !'.format(noisy_rate))
    data_path = '{}/{}/cl_result/{}/{}_percent_res.json'.format(res, method, cwe_id, int(noisy_rate*100))

    if method == 'deepwukong':
        id_key = 'xfg_id'
        flip_key = 'flip'
    else:
        id_key = 'idx'
        flip_key = 'flips'
    data = read_json(data_path)
    error_label = data['error_label']
    fliped = data[flip_key]
    idxs = data[id_key]
    fliped = np.array(fliped)
    found_noise_count = len(fliped[error_label])
    found_true_count = np.sum(fliped[error_label])
    flipped = np.sum(fliped)
    
    # idxs = np.array(idxs)
    

    
    result = dict()
    result['title'] = '{}_{}_{}_{}_percent'.format(method, 'cl', cwe_id, int(noisy_rate * 100))
    result['sample_count'] = len(fliped)
    result['flipped'] = flipped
    result['found_noisy_count'] = found_noise_count
    result['TP_count'] = found_true_count
    result['FP_count'] = found_noise_count - found_true_count
    result['recall'] = round(found_true_count / flipped ,2)
    result['FPR'] = round((found_noise_count - found_true_count) / found_noise_count ,2)
    result['noisy_rate_after_cl'] = round((flipped - found_true_count) 
     / (len(fliped) - found_noise_count), 2)
    print(result)
    return result



def statistic_dt_result(config, noisy_rate:float = None):
    """
    @description  : statistic differential training result
    ---------
    @param  :
    -------
    @Returns  :
    -------
    """
    method = config.dt.model_name
    cwe_id = config.dataset.name
    res = config.res_folder
    if method not in ['deepwukong', 'sysevr', 'vuldeepecker']:
        raise RuntimeError('{} name error !'.format(method))

    # if noisy_rate not in [0.1, 0.2, 0.3]:
    #     raise RuntimeError('{} noisy rate error !'.format(noisy_rate))
    dt_data_path = '{}/{}/dt_result/{}/{}_percent_ws.json'.format(res, method, cwe_id, int(noisy_rate*100))
    if method == 'deepwukong':
        raw_data_path = 'data/CWES/{}/{}.json'.format(cwe_id, cwe_id)
        noise_info_path = 'data/CWES/{}/noise_info.json'.format(cwe_id)
    else:
        raw_data_path = 'data/{}/{}/{}.json'.format(method, cwe_id, cwe_id)
        noise_info_path = 'data/{}/{}/noise_info.json'.format(method, cwe_id)
    noise_key = '{}_percent'.format(int(100 * noisy_rate))
    noise_info = read_json(noise_info_path)
    raw_data = read_json(raw_data_path) 
    if config.res_folder == 'res_d2a_flip':
        noise_xfg_ids = []
        for xfg in raw_data:
            if xfg['flip']:
                noise_xfg_ids.append(xfg['xfg_id'])
    else:

        noise_xfg_ids = noise_info[noise_key]['noise_xfg_ids']
    if method == 'deepwukong':
        key = 'target'
        
    else:
        key = 'val'
    dt_nosie_xfg_ids = []  
    dt_data = read_json(dt_data_path)
       
    for xfg in dt_data:
        xfg_id = xfg['xfg_id']
        if xfg['flip']:
            dt_nosie_xfg_ids.append(xfg_id)
    noise_xfg_ids = set(noise_xfg_ids)
    dt_nosie_xfg_ids = set(dt_nosie_xfg_ids)

    # dt - noise  = found false
    # noise - dt = found true 
    # dt & noise = unfound

    found_noise_count = len(noise_xfg_ids ^ dt_nosie_xfg_ids)
    found_true_count = len(noise_xfg_ids - dt_nosie_xfg_ids)
    fount_false_count = len(dt_nosie_xfg_ids - noise_xfg_ids)

    
    result = dict()
    result['title'] = '{}_{}_{}_{}_percent'.format(method, 'dt', cwe_id, int(noisy_rate * 100))
    result['sample_count'] = len(raw_data)
    result['flipped'] = len(noise_xfg_ids)
    result['found_noisy_count'] = found_noise_count
    result['TP_count'] = found_true_count
    result['FP_count'] = fount_false_count
    result['recall'] = round(found_true_count / len(noise_xfg_ids) ,2)
    result['FPR'] = round((found_noise_count - found_true_count) / found_noise_count ,2)
    result['noisy_rate_after_cl'] = round( len(dt_nosie_xfg_ids) / len(raw_data), 2)
    print(result)
    return result


def statistic_all_cl(method, cwe_id):
    data_path = 'res/{}/cl_result/{}/'.format(method, cwe_id)
    false_xfgs_list = []
    for json_file in os.listdir(data_path):
        print(data_path + json_file)
        json_dict = read_json(data_path + json_file)
        xfg_ids = np.array(json_dict['xfg_id'])
        fliped = np.array(json_dict['flip'])
        error_labels = np.array(json_dict['error_label'])
        noise_xfgs = set(xfg_ids[fliped].tolist())
        found_xfgs = set(xfg_ids[error_labels].tolist())
        tmp_list = list(noise_xfgs ^ found_xfgs)
        false_xfgs_list.append(tmp_list)
    false_xfgs = reduce(np.intersect1d, false_xfgs_list).tolist()
    write_json(false_xfgs, 'false_xfgs.json')


def statistic_cl_and_dt(method):
    cl_data_path = '/home/niexu/project/python/noise_reduce/res/deepwukong/cl_result/CWE119_0.7/10_percent_res.json'
    dt_data_path = '/home/niexu/project/python/noise_reduce/res/deepwukong/dt_result/CWE119/10_percent_res_v4.jsonl'
    if method == 'deepwukong':
        id_key = 'xfg_id'
        flip_key = 'flip'
    else:
        id_key = 'idx'
        flip_key = 'flips'
    data = read_json(cl_data_path)
    error_label = data['error_label']
    fliped = data[flip_key]
    idxs = np.array(data[id_key])
    fliped = np.array(fliped)
    cl_tp_ids = set(idxs[error_label])

    outlier_list = []
    with jsonlines.open(dt_data_path) as reader:
        for obj in reader:
            outlier_list.extend(obj['outlier_list']) 
    dt_all_ids = set()
    dt_tp_ids = set()
    print(outlier_list)
    for outlier in outlier_list:
        dt_all_ids.add(outlier[0])
        if outlier[2]:
            dt_tp_ids.add(outlier[0])
    inter_ids = dt_all_ids & cl_tp_ids
    inter_tp_ids = dt_tp_ids & cl_tp_ids
    print('dt_all', len(dt_all_ids))
    print('dt_tp', len(dt_tp_ids))


    print('dt_all_in_cl_result', len(inter_ids))
    
    print('dt_tp_in_cl_result', len(inter_tp_ids))
    return list(inter_ids)

def analysis_cl(method, cwe_id, noisy_rate):
    cl_data_path = 'res/{}/cl_result/{}/{}_percent_res.json'.format(method, cwe_id, int(noisy_rate*100))
    if method == 'deepwukong':
        id_key = 'xfg_id'
        flip_key = 'flip'
    else:
        id_key = 'idx'
        flip_key = 'flips'
    data = read_json(cl_data_path)
    error_label = data['error_label']
    fliped = data[flip_key]
    idxs = np.array(data[id_key])[error_label].tolist()
    fliped = np.array(fliped)[error_label].tolist()
    psx = np.array(data['psx'])[error_label].tolist()
    label = np.array(data['s'])[error_label].tolist()

    all_info = list()

    for idx, flip, p, y in zip(idxs, fliped, psx, label):
        all_info.append((idx, flip, p, y))
    c_true = 0
    c_false = 0
    for info in all_info:

        if info[1] and info[2][int(math.fabs(info[3]-1))] < 0.6:
            c_true += 1
        elif not info[1] and info[2][int(math.fabs(info[3]-1))] < 0.6:
            c_false += 1
    print('c_true', c_true)
    print('c_false', c_false)
    # write_json(all_info, 'sard_simple_analysis/cl_result.json')

def analysis_dt(method, cwe_id, noisy_rate):
    dt_data_path = 'res/{}/dt_result/{}/{}_percent_res.jsonl'.format(method, cwe_id, int(noisy_rate*100))
    outlier_list = []
    with jsonlines.open(dt_data_path) as reader:
        for obj in reader:
            outlier_list.extend(obj['outlier_list']) 
    

    # dds_loss = read_json('dds_loss.json')
    # wds_loss = read_json('wds_loss.json')
    info_list = set()
    flip_list = list()
    for outlier in outlier_list:
        xfg_id = outlier[0]
        label = outlier[1]
        flip = outlier[2]
        info_list.add(xfg_id)
        flip_list.append(flip)
        # info_list.append((xfg_id, label, flip, wds_loss[str(xfg_id)], dds_loss[str(xfg_id)]))
    # write_json(info_list, 'sard_simple_analysis/dt_result.json')
    print(len(info_list))
    flip_arr = np.array(flip_list)
    print(np.sum(flip_arr))

    print(len(info_list) - np.sum(flip_arr))

if __name__ == '__main__':
    from cleanlab.pruning import get_noise_indices
    import numpy as np

    # result1 = statistic_dt_result('vuldeepecker', 'CWE119', 0.05)
    # result2 = statistic_cl_result('sysevr', 'CWE119', 0.07)
    # result3 = statistic_cl_result('sysevr', 'CWE119', 0.09)
    # print(result1)
    # print(result2)
    # print(result3)
    # statistic_cl_and_dt('deepwukong')
    # statistic_dt_result('deepwukong', 'CWE119_v1', 0.1)
    # statistic_dt_result('deepwukong', 'CWE787', 0.3)
    # statistic_cl_result('deepwukong', 'CWE787', 0.3)
    # statistic_cl_result('sysevr', 'CWE119', 0.3)
    # analysis_dt('deepwukong', 'CWE119', 0.1)
    # result1 = statistic_dt_result('sysevr', 'CWE787', 0.1)
    # result2 = statistic_cl_result('sysevr', 'CWE119', 0.2)
    # result3 = statistic_cl_result('sysevr', 'CWE119', 0.3)
    # result1 = statistic_cl_result('deepwukong', 'CWE119', 0.1)
    # result2 = statistic_cl_result('deepwukong', 'CWE119', 0.2)
    # result3 = statistic_cl_result('deepwukong', 'CWE119', 0.3)
    # result4 = statistic_cl_result('deepwukong', 'CWE119', 0.4)

    # result3 = statistic_cl_result('sysevr', 'CWE119_v2_bind', 0.3)

    arg_parser = ArgumentParser()
    # arg_parser.add_argument("model", type=str)
    # arg_parser.add_argument("--dataset", type=str, default=None)
    arg_parser.add_argument("--offline", action="store_true")
    arg_parser.add_argument("--resume", type=str, default=None)
    args = arg_parser.parse_args()
    config = get_config_dwk('INTEGER_OVERFLOW_flip', 'deepwukong', log_offline=args.offline)
    config.res_folder = 'res_d2a_flip'
    # result = statistic_cl_result(config, 0)
    result = statistic_cl_result(config, 0)
    # result = statistic_dt_result(config, 0.3)
    # result = statistic_cl_result(config, 0.2)
    # result = statistic_cl_result(config, 0.3)
    # print(result)
    # result = statistic_cl_result('deepwukong', 'CWE119', 0.3)
    # print(result)
    # result = statistic_cl_result('deepwukong', 'CWE119', 0.4)
    # print(result)
    # cl_result = read_json('res/deepwukong/cl_result/CWE119/10_percent_res.json')
    # labels = cl_result['s']
    # xfg_ids = cl_result['xfg_id']
    # flip = cl_result['flip']
    # pre_labels = cl_result['psx']
    # error_labels = cl_result['error_label']
    
    
    # error_labels = get_noise_indices(np.array(labels), np.array(pre_labels), num_to_remove_per_class=1000)
    # print(np.sum(error_labels))
    # flip = np.array(flip)
    # print(np.sum(flip[error_labels]))
    # with open("statistic_res1.txt","a") as file:
    #    file.write(str(result)+"\n")
    # statistic_all_cl('deepwukong', 'CWE119')
    # data = read_json('/home/niexu/project/python/noise_reduce/data/CWES/CWE119_v2/0_percent/xfgs.json')
    # xfg_safe = []
    # for key in data:
    #     for xfg in data[key]:
    #         if xfg['target'] == 1:
    #            xfg_safe.append(xfg)
    # write_json(xfg_safe, 'xfg_vul.json')