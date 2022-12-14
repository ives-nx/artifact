

import re
from numpy.lib.stride_tricks import _maybe_view_as_subclass
from sklearn.utils import resample
from utils.json_ops import get_data_json, read_json, write_json
from models.cl.SYS_create_noisy_data import  sys_cdg_duplicate,sys_create_noise, sys_gen_cdg_test
import jsonlines
from models.sysevr.buffered_path_context import BufferedPathContext as sys_bf
from models.vuldeepecker.buffered_path_context import BufferedPathContext as vdp_bf
from models.sysevr.SYS_dataset import SYSDataset
from argparse import ArgumentParser
from cleanlab import latent_estimation
from cleanlab.pruning import get_noise_indices
import numpy as np
from utils.plot_result import plot_approach_f1
from utils.common import print_config, filter_warnings, get_config
from models.cl.my_cl_model import MY_SYS_BGRU
from models.cl.VDP_create_noisy_data import vdp_cdg_duplicate, vdp_create_noise, vdp_gen_cdg_test
from utils.common import get_config_dwk
from tools.joern_slicer.d2a_src_parse import d2a_cdg_label, d2a_xfg_label, d2a_cdg_test_label, d2a_xfg_test_label
# from pre_train import divide_big_json, doc2vec
from utils.vectorize_gadget import GadgetVectorizer
from sklearn.utils import resample
import os
from utils.gen_noise import gen_noise_for_cdg_d2a
# holdout_dir = '/home/niexu/dataset/CWES'

# data_path = '/home/niexu/project/python/noise_reduce/data/sysevr/CWE020/train.pkl'
# data = BufferedPathContext.load(data_path)
# print(data)
# dataset = SYSDataset(data, _config.hyper_parameters.seq_len, _config.hyper_parameters.shuffle_data)
# vectors = []
# label = []
# for i in range(len(data)):
#     vectors.append(data[i][0])
#     label.append(data[i][1])
# # print(vectors)
# # print(label)
# psx = latent_estimation.estimate_cv_predicted_probabilities(
# np.array(vectors), np.array(label), clf=MY_SYS_BGRU(_config, data_path, False))

# ordered_label_errors = get_noise_indices(
#         s=np.array(label),
#         psx=psx,
#         sorted_index_method='normalized_margin', # Orders label errors
#     )
# print(ordered_label_errors)

from utils.xml_parser import get_all_label_list, get_sard_vul_info_list
from tools.joern_slicer.joern_parse import xfg_label, get_cdg_label, create_noise_pair, xfg_label_for_noise_reduce, xfg_label_from_vul_info_list
from tools.joern_slicer.d2a_src_parse import d2a_xfg_label, d2a_classify_as_bug_type
import random


def get_funs(method):
    duplicated_funs = {
        'sysevr':sys_cdg_duplicate,
        'vuldeepecker':vdp_cdg_duplicate
    }

    create_noise_funs = {
        'sysevr':sys_create_noise,
        'vuldeepecker':vdp_create_noise
    }

    return duplicated_funs[method], create_noise_funs[method]

def gen_dwk_raw_data(cwe_id, gen_csv=False):

    print('Start process {} ...'.format(cwe_id))
    # cwe_id = 'CWE119'
    # raw_data_path = '/home/niexu/project/python/noise_reduce/data/CWES/{}/{}_raw.json'.format(cwe_id, cwe_id)

    #label from source_code
    # vul_info_list = get_sard_vul_info_list(cwe_id)
    # xfgs = xfg_label_from_vul_info_list(cwe_id, vul_info_list, gen_csv)
    # write_json(xfgs, raw_data_path)

    #cp from dwk
    raw_data_path = '/home/niexu/dataset/DeepWukong/data/{}/xfg-sym-unique/bigJson.json'.format(cwe_id)

    data = read_json(raw_data_path)
    vul = []
    safe = []
    for xfg in data:
        if xfg['target'] == 1:
            vul.append(xfg)
        else:
            safe.append(xfg)
    if len(safe) >= len(vul)*2:
        sub_safe = np.random.choice(safe, len(vul) * 2, False)
    else:
        sub_safe = np.array(safe)
    xfgs = []
    xfgs.extend(vul)
    xfgs.extend(sub_safe.tolist())
    random.shuffle(xfgs)
    print(len(vul), len(sub_safe), len(xfgs))
    data_path = '/home/niexu/project/python/noise_reduce/data/CWES/{}/{}.json'.format(cwe_id, cwe_id)

    # data = read_json(data_path)
    for idx, xfg in enumerate(xfgs):
        xfg['xfg_id'] = idx
        xfg['flip'] = False
    if not os.path.exists(os.path.dirname(data_path)):
        os.makedirs(os.path.dirname(data_path))
    write_json(xfgs, data_path)
    print('End process {} ...'.format(cwe_id))
    return xfgs


def gen_dwk_raw_data_d2a(cwe_id):    
    d2a_dir = '/home/public/rmt/niexu/projects/python/noise_reduce/data/d2a/dwk'
    # bug_type = 'BUFFER_OVERRUN'
    data_path = os.path.join(d2a_dir, cwe_id + '.json')
    data = read_json(data_path)
    vul = []
    safe = []
    for xfg in data:
        if xfg['target'] == 1:
            vul.append(xfg)
        else:
            safe.append(xfg)

    sub_safe = np.random.choice(safe, len(vul) * 2, False)

    xfgs = []
    xfgs.extend(vul)
    xfgs.extend(sub_safe.tolist())
    random.shuffle(xfgs)
    print(len(vul), len(sub_safe), len(xfgs))
    data_path = '/home/niexu/project/python/noise_reduce/data/CWES/{}/{}.json'.format(cwe_id, cwe_id)

    # data = read_json(data_path)
    for idx, xfg in enumerate(xfgs):
        xfg['xfg_id'] = idx
        xfg['flip'] = False
    if not os.path.exists(os.path.dirname(data_path)):
        os.makedirs(os.path.dirname(data_path))
    write_json(xfgs, data_path)



def gen_cdg_raw_data(cwe_id, method, gen_csv=False):
    arg_parser = ArgumentParser()
    # arg_parser.add_argument("model", type=str)
    # arg_parser.add_argument("--dataset", type=str, default=None)
    arg_parser.add_argument("--offline", action="store_true")
    arg_parser.add_argument("--resume", type=str, default=None)
    args = arg_parser.parse_args()

    config = get_config_dwk(cwe_id, method ,log_offline=args.offline)

    raw_data_path = os.path.join(config.data_folder, config.name,
                           config.dataset.name, "{}_raw.json".format(config.dataset.name))
    # generate raw data
    vul_info_list = get_sard_vul_info_list(config.dataset.name)
    gadgets = get_cdg_label(cwe_id, vul_info_list, config.name, gen_csv)
    if not os.path.exists(os.path.dirname(raw_data_path)):
        os.makedirs(os.path.dirname(raw_data_path))
    write_json(gadgets, raw_data_path)
    
    #unique
    # cdg_duplicate, create_noise = get_funs(config.name)
    # cdg_duplicate(config, holdout_data_path=raw_data_path)
    # create_noise(cwe_id)
#

def gen_cdg_raw_data_d2a(cwe_id, method):
    arg_parser = ArgumentParser()
    # arg_parser.add_argument("model", type=str)
    # arg_parser.add_argument("--dataset", type=str, default=None)
    arg_parser.add_argument("--offline", action="store_true")
    arg_parser.add_argument("--resume", type=str, default=None)
    args = arg_parser.parse_args()

    config = get_config_dwk(cwe_id, method ,log_offline=args.offline)

    raw_data_path = '/home/public/rmt/niexu/projects/python/noise_reduce/data/d2a/{}/{}.json'.format(config.name, config.dataset.name)
    # generate raw data

    # gadgets = d2a_cdg_label(cwe_id, config.name, False)
    # write_json(gadgets, raw_data_path)
    print("end")
    # unique
    print('unique')
    cdg_duplicate, create_noise = get_funs(config.name)
    cdg_duplicate(config, holdout_data_path=raw_data_path)
    create_noise(cwe_id)

def gen_cdg_test_raw_data_d2a(cwe_id, method):
    arg_parser = ArgumentParser()
    # arg_parser.add_argument("model", type=str)
    # arg_parser.add_argument("--dataset", type=str, default=None)
    arg_parser.add_argument("--offline", action="store_true")
    arg_parser.add_argument("--resume", type=str, default=None)
    args = arg_parser.parse_args()

    config = get_config_dwk(cwe_id, method ,log_offline=args.offline)

    raw_data_path = 'data/{}/{}/{}/{}.json'.format(config.name, config.dataset.name, 'raw', 'test')
    # generate raw data
    if not os.path.exists(os.path.dirname(raw_data_path)):
        os.makedirs(os.path.dirname(raw_data_path))

    gadgets = d2a_cdg_test_label(cwe_id, config.name, False)
    write_json(gadgets, raw_data_path)

def gen_cwe190_d2a_raw(method):
    
    if method == 'deepwukong':
        tmp = 'CWES'
        key = 'target'
    else:
        w2v_path = os.path.join('data', method, 'CWE190_d2a',
                         "w2v.model")
        vocab_path = os.path.join('data', method, 'CWE190_d2a', "vocab.pkl") 
        tmp = method
        key = 'val'
    arg_parser = ArgumentParser()
    # arg_parser.add_argument("model", type=str)
    # arg_parser.add_argument("--dataset", type=str, default=None)
    arg_parser.add_argument("--offline", action="store_true")
    arg_parser.add_argument("--resume", type=str, default=None)
    args = arg_parser.parse_args()

    config = get_config_dwk('CWE190_d2a', method ,log_offline=args.offline)
    cwe_path = os.path.join('data', tmp, 'CWE190', 'CWE190.json')
    io_flip_path = os.path.join('data', tmp, 'INTEGER_OVERFLOW_flip', 'INTEGER_OVERFLOW_flip.json')
    cwe_d2a_path = os.path.join('data', tmp, 'CWE190_d2a', 'CWE190_d2a.json')
    cwe_data = read_json(cwe_path)
    io_flip_data = read_json(io_flip_path)
    flipped_item = []
    for item in io_flip_data:
        if item['flip'] == True:
            flipped_item.append(item)
    all_data = []
    all_data.extend(cwe_data)
    all_data.extend(flipped_item)
    random.shuffle(all_data)

    vectorizer = GadgetVectorizer(config)
    
    
    
    if method == 'deepwukong':
        for index, item in enumerate(all_data):
            item['xfg_id'] = index
        
    else:
        for index, item in enumerate(all_data):
            item['xfg_id'] = index
            vectorizer.add_gadget(item['gadget'])
        vectorizer.train_model(w2v_path)
        vectorizer.build_vocab(vocab_path) 
    write_json(all_data, cwe_d2a_path)



def gen_cwe119_d2a_raw(method):
    
    if method == 'deepwukong':
        tmp = 'CWES'
        key = 'target'
    else:
        w2v_path = os.path.join('data', method, 'CWE119_d2a',
                         "w2v.model")
        vocab_path = os.path.join('data', method, 'CWE119_d2a', "vocab.pkl") 
        tmp = method
        key = 'val'
    arg_parser = ArgumentParser()
    # arg_parser.add_argument("model", type=str)
    # arg_parser.add_argument("--dataset", type=str, default=None)
    arg_parser.add_argument("--offline", action="store_true")
    arg_parser.add_argument("--resume", type=str, default=None)
    args = arg_parser.parse_args()

    config = get_config_dwk('CWE119_d2a', method ,log_offline=args.offline)
    cwe_path = os.path.join('data', tmp, 'CWE119', 'CWE119.json')
    io_flip_path = os.path.join('data', tmp, 'BUFFER_OVERRUN_flip', 'BUFFER_OVERRUN_flip.json')
    cwe_d2a_path = os.path.join('data', tmp, 'CWE119_d2a', 'CWE119_d2a.json')
    cwe_data = read_json(cwe_path)
    io_flip_data = read_json(io_flip_path)
    flipped_item = []
    for item in io_flip_data:
        if item['flip'] == True:
            flipped_item.append(item)
    all_data = []
    all_data.extend(cwe_data)
    all_data.extend(flipped_item)
    random.shuffle(all_data)

    vectorizer = GadgetVectorizer(config)
    
    
    
    if method == 'deepwukong':
        for index, item in enumerate(all_data):
            item['xfg_id'] = index
        
    else:
        for index, item in enumerate(all_data):
            item['xfg_id'] = index
            vectorizer.add_gadget(item['gadget'])
        vectorizer.train_model(w2v_path)
        vectorizer.build_vocab(vocab_path) 
    write_json(all_data, cwe_d2a_path)
#  gen_raw_data('CWE119')

# gen_sys_raw_data('CWE119')

# gen_vdp_raw_data('CWE119')
# plot_approach_f1('deepwukong')
# plot_approach_f1('sysevr')
# plot_approach_f1('vuldeepecker')
# cwe_ids = ['CWE078', 'CWE020', 'CWE022', 'CWE125', 'CWE190', 'CWE400', 'CWE787']
# for cwe_id in cwe_ids:
#     # gen_dwk_raw_data(cwe_id)
#     # divide_big_json(cwe_id)
#     # doc2vec(cwe_id)
#     gen_cdg_raw_data(cwe_id, 'sysevr', True)
#     gen_cdg_raw_data(cwe_id, 'vuldeepecker', False)

# gen_dwk_raw_data_d2a('INTEGER_OVERFLOW')
# gen_dwk_raw_data_d2a('BUFFER_OVERRUN')

# gen_cdg_raw_data_d2a('INTEGER_OVERFLOW', 'vuldeepecker')
# gen_cdg_raw_data_d2a('INTEGER_OVERFLOW', 'sysevr')

# d2a_xfg_label('BUFFER_OVERRUN')
# d2a_xfg_label('INTEGER_OVERFLOW')
# gen_cdg_test_raw_data_d2a('INTEGER_OVERFLOW_test', 'sysevr')
# gen_cdg_test_raw_data_d2a('INTEGER_OVERFLOW_test', 'vuldeepecker')

# d2a_xfg_test_label('BUFFER_OVERRUN_test')
# arg_parser = ArgumentParser()
# arg_parser.add_argument("--offline", action="store_true")
# arg_parser.add_argument("--resume", type=str, default=None)
# args = arg_parser.parse_args()

# config = get_config_dwk('INTEGER_OVERFLOW', 'sysevr' ,log_offline=args.offline)
# sys_gen_cdg_test(config)

# config = get_config_dwk('INTEGER_OVERFLOW_test', 'vuldeepecker' ,log_offline=args.offline)
# vdp_gen_cdg_test(config)

# plot_approach_f1('buffer_overrun_raw')

# gen_cwe119_d2a_raw('deepwukong')
# gen_cwe119_d2a_raw('vuldeepecker')
# gen_cwe119_d2a_raw('sysevr')
# gen_noise_for_cdg_d2a(config)
CWES = ['CWE078', 'CWE119', 'CWE190', 'CWE020', 'CWE125', 'CWE400', 'CWE022', 'CWE787']
methods = ['sysevr', 'vuldeepecker']
for cwe in CWES:
    for m in methods:
        try:       
            gen_cdg_raw_data(cwe, m, False)
        except Exception as e:
            print(e)