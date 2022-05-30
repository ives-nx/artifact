from distutils.command.config import config
import random
from math import e
from posixpath import join
from turtle import write
from unittest import result
from cleanlab import latent_estimation
from cleanlab.pruning import get_noise_indices
from numpy.core.numeric import load
from numpy.lib.function_base import vectorize
from tqdm.std import tqdm


from result_analysis.extract import extract
import numpy as np
import os
from utils.plot_result import plot_approach_f1
from utils.json_ops import read_json, write_json
from utils.common import get_config, print_config
import numpy as np
from sklearn.model_selection import train_test_split
import json
import numpy
from models.cl.VDP_create_noisy_data import vdp_statistic_cdg_duplicate 

from utils.vectorize_gadget import GadgetVectorizer

def merge_vul_and_safe_data(config, is_resample=False):
    positive_path = os.path.join(config.data_folder, config.name, config.dataset.name, 'positive.json')
    negative_path = os.path.join(config.data_folder, config.name, config.dataset.name, 'negative.json')
    all_path = os.path.join(config.data_folder, config.name, config.dataset.name, f'{config.dataset.name}.json')
    positive = read_json(positive_path)
    negative = read_json(negative_path)
    
    all_data = []
    id = 0
    vul_funs = []
    safe_funs = []
    for p in positive:
        if len(p['node-line-content']) > 3:
            p['xfg_id'] = id
            p['flip'] = False
            p['target'] = 1
            vul_funs.append(p)
            
            id += 1
    for n in negative:
        if len(n['node-line-content']) > 3 and 'bad' not in n['functionName']:
            n['xfg_id'] = id
            n['flip'] = False
            n['target'] = 0
            safe_funs.append(n)
            id += 1
            
    np.random.seed(config.seed)
    if is_resample:
        safe_funs = np.random.choice(safe_funs, min(2 * len(vul_funs), len(safe_funs)), False)
    print(f'positive sample count {len(vul_funs)}')
    print(f'negative sample count {len(safe_funs)}') 
    
    all_data.extend(vul_funs)
    all_data.extend(safe_funs)
    np.random.shuffle(all_data)
       
    write_json(all_data, all_path) 
    print(len(all_data))
    
def gen_noise(config):
    data_path = os.path.join(config.data_folder, config.name, config.dataset.name, f'{config.dataset.name}.json')
    noise_info_path = os.path.join(config.data_folder, config.name, config.dataset.name, 'noise_info.json')
    training_noise_info_path = os.path.join(config.data_folder, config.name, config.dataset.name, 'training_noise_info.json')
    if config.noise_set not in ['training', 'all']:
        raise RuntimeError("noise set error")
    all_data = read_json(data_path)
    sz = len(all_data)
    train_data = all_data[slice(sz // 5, sz)]
    all_xfgids, training_xfgids = [xfg['xfg_id'] for xfg in all_data], [xfg['xfg_id'] for xfg in train_data]
    noise_rates = [0, 0.1, 0.2, 0.3]
    noise_info = dict()
    training_noise_info = dict()
    print('all ', len(all_xfgids))
    print('training ', len(training_xfgids))
    np.random.seed(config.seed)
    for noise_rate in noise_rates:
        noise_key = '{}_percent'.format(int(noise_rate * 100))
        noise_info[noise_key] = dict()
        training_noise_info[noise_key] = dict()
        noise_info[noise_key]['noise_xfg_ids'] = np.random.choice(all_xfgids, 
                                                                  int(len(all_xfgids) * noise_rate), 
                                                                  replace=False).tolist()
        training_noise_info[noise_key]['noise_xfg_ids'] = np.random.choice(training_xfgids, 
                                                                  int(len(training_xfgids) * noise_rate), 
                                                                  replace=False).tolist()
        print('all ', noise_rate, len(noise_info[noise_key]['noise_xfg_ids']))
        print('training ', noise_rate, len(training_noise_info[noise_key]['noise_xfg_ids']))
        
    write_json(noise_info, noise_info_path)
    write_json(training_noise_info, training_noise_info_path)
    
def merge_reveal_and_Devign():
    
    data_folder = '/home/public/rmt/niexu/projects/python/noise_reduce/data/'
    reveal_positive_path = os.path.join(data_folder, 'reveal', 'ReVeal', 'positive.json')
    reveal_negative_path = os.path.join(data_folder, 'reveal', 'ReVeal', 'negative.json')   
    devign_positive_path = os.path.join(data_folder, 'reveal', 'Devign', 'positive.json')
    devign_negative_path = os.path.join(data_folder, 'reveal', 'Devign', 'negative.json')   
    
    RAD_test_path = os.path.join(data_folder, 'reveal', 'RAD', 'true_test.json')
    RAD_train_path = os.path.join(data_folder, 'reveal', 'RAD', 'RAD.json')
    
    reveal_positive = read_json(reveal_positive_path)
    reveal_negative = read_json(reveal_negative_path)
    
    devign_positive = read_json(devign_positive_path)
    devign_negative = read_json(devign_negative_path)
    
    for cpg in reveal_positive:
        cpg['source'] = 'ReVeal'
    for cpg in reveal_negative:
        cpg['spurce'] = 'ReVeal'
    for cpg in devign_positive:
        cpg['source'] = 'Devign'
    for cpg in devign_negative:
        cpg['source'] = 'Devign'
        
    RAD_vul_count = len(reveal_positive) + len(devign_positive)
    RAD_safe_count = RAD_vul_count * 2
    RAD_true_test_vul_count = int(RAD_vul_count * 0.2)
    RAD_true_test_safe_count = RAD_true_test_vul_count * 2
    np.random.seed(7)
    
    devign_positive_indices = np.array(list(range(len(devign_positive))))
    devign_negative_indices = np.array(list(range(len(devign_negative))))
    # print(len(devign_negative_indices), devign_negative_indices)
    # print(len(devign_positive_indices), devign_positive_indices)
    
    RAD_true_train_positive_indices,  RAD_true_test_positive_indices  = \
    train_test_split(devign_positive_indices, test_size=RAD_true_test_vul_count / len(devign_positive), random_state=7, shuffle=True)
    
    RAD_true_train_negative_indices, RAD_true_test_negative_indices = \
    train_test_split(devign_negative_indices, test_size=RAD_true_test_safe_count / len(devign_negative), random_state=7, shuffle=True)
   
    # print(len(devign_positive_indices), devign_positive_indices)
    RAD_true_test_positives = np.array(devign_positive)[RAD_true_test_positive_indices]
    RAD_true_test_negatives = np.array(devign_negative)[RAD_true_test_negative_indices]
    
    for xfg in RAD_true_test_positives:
        xfg['target'] = 1
        xfg['flip'] = False
    
    for xfg in RAD_true_test_negatives:
        xfg['target'] = 0
        xfg['flip'] = False

    RAD_true_test = RAD_true_test_positives.tolist() + RAD_true_test_negatives.tolist()
    
    print(len(RAD_true_test_positives), len(RAD_true_test_negatives), len(RAD_true_test))
    
    
    RAD_train_positives = np.array(devign_positive)[RAD_true_train_positive_indices].tolist() + reveal_positive
    RAD_true_train_neagtives = np.array(devign_negative)[RAD_true_train_negative_indices].tolist()
    RAD_train_negatives = RAD_true_train_neagtives + np.random.choice(reveal_negative, 
                                                                      len(RAD_train_positives) * 2 - len(RAD_true_train_neagtives),
                                                                     replace=False).tolist()
    for xfg in RAD_train_positives:
        xfg['target'] = 1
        xfg['flip'] = False
    
    for xfg in RAD_train_negatives:
        xfg['target'] = 0
        xfg['flip'] = False 
        
    RAD_train = RAD_train_positives + RAD_train_negatives
    
    print(len(RAD_train_positives), len(RAD_train_negatives), len(RAD_train))
    
    
    id = 0
    for xfg in RAD_train:
        xfg['xfg_id'] = id
        id += 1
        
    for xfg in RAD_true_test:
        xfg['xfg_id'] = id
        id += 1
        
    #乱序
    np.random.shuffle(RAD_true_test)
    np.random.shuffle(RAD_train)
    
    
    write_json(RAD_train, RAD_train_path, is_mkdirs=True)
    write_json(RAD_true_test, RAD_test_path)
    
    
def flip_data(src_data, noise_ids):
    key = 'target'
    for xfg in src_data:
        xfg_id = xfg['xfg_id']
        if xfg_id in noise_ids:
            xfg[key] = xfg[key] ^ 1
            xfg['flip'] = not xfg['flip']
    return src_data    
    
    
    
    
# for cwe in ['CWE020', 'CWE022', 'CWE078', 'CWE190', 'CWE119', 'CWE787', 'CWE400', 'CWE125'] :
# config = get_config('RAD', 'reveal')  
# merge_reveal_data(config=config, is_resample=False)
# gen_noise(config=config)
# from pre_train import train_w2v_model_for_reveal

# train_w2v_model_for_reveal(config=config)
# from utils.plot_result import plot_approach_f1
# plot_approach_f1('reveal_RAD', 'res')
# plot_approach_f1('reveal_ReVeal', 'res1')
# from tools.joern_slicer.reveal_src_parse import generate_cpgs
# generate_cpgs('/home/public/rmt/niexu/dataset/vul/devign_data/source_code', True)
# merge_reveal_data(config=config)

# merge_reveal_and_Devign()
# merge_reveal_and_Devign()
def stack_pre_train(CWE_ID):
    from models.stacking.stacking_dataset import StackingDataset
    from models.stacking.Stacking import VGD_GNN
    from models.stacking.Stacking import VDP_BLSTM
    from models.stacking.Stacking import SYS_BGRU
    from models.stacking.Stacking import My_Stacking
    from torch_geometric.data import DataLoader
    import torch

    config = get_config(CWE_ID, 'stack')
    StackingDataset.pre_train(config=config)
# stack_pre_train('CWE787')
# stack_pre_train('CWE020')
    
def stack_train(CWE_ID):
    from models.stacking.stacking_dataset import StackingDataset
    from models.stacking.Stacking import VGD_GNN
    from models.stacking.Stacking import VDP_BLSTM
    from models.stacking.Stacking import SYS_BGRU
    from models.stacking.Stacking import My_Stacking
    from torch_geometric.data import DataLoader
    import torch

    config = get_config(CWE_ID, 'stack')
    # StackingDataset.pre_train(config=config)
    stack_dataset = StackingDataset(config)

    sz = len(stack_dataset)

    train_silce = slice(sz//5, sz)
    test_slice = slice(0, sz//5)
    train_dataset = stack_dataset[train_silce]
    test_dataset = stack_dataset[test_slice]

    dwk_config = get_config(CWE_ID, 'deepwukong')
    sys_config = get_config(CWE_ID, 'sysevr')
    vdp_config = get_config(CWE_ID, 'vuldeepecker')
    configs = [dwk_config, sys_config, vdp_config]
    # configs = [sys_config]

    dwk_model = VGD_GNN(dwk_config)
    sys_model = SYS_BGRU(sys_config)
    vdp_model = VDP_BLSTM(vdp_config)
    models = [dwk_model, sys_model, vdp_model]
    # models = [sys_model]

    stacking = My_Stacking(models=models, configs=configs, config=config)

    stacking.k_fold_train(train_dataset, 5)
    # stacking.train_split(stack_dataset)

    stacking.test(test_dataset) 
    
# stack_train('CWE125')
# stack_train('CWE119')

def train_cl(CWE_ID, noise_rate = 0):
    from models.stacking.stacking_dataset import StackingDataset
    from models.stacking.Stacking import VGD_GNN
    from models.stacking.Stacking import VDP_BLSTM
    from models.stacking.Stacking import SYS_BGRU
    from models.stacking.Stacking import My_Stacking, MY_CL_Stacking
    config = get_config(CWE_ID, 'stack')
    # StackingDataset.pre_train(config=config)
    

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

    noise_info = read_json(noise_info_path)
    noise_xfg_ids = noise_info[noise_key]['noise_xfg_ids']
    flip_data(data_json, noise_xfg_ids)

    dwk_config = get_config(CWE_ID, 'deepwukong')
    sys_config = get_config(CWE_ID, 'sysevr')
    vdp_config = get_config(CWE_ID, 'vuldeepecker')
    configs = [dwk_config, sys_config, vdp_config]

    dwk_model = VGD_GNN(dwk_config)
    sys_model = SYS_BGRU(sys_config)
    vdp_model = VDP_BLSTM(vdp_config)
    models = [dwk_model, sys_model, vdp_model]
    
    stack_dataset = StackingDataset(config, data_json)
    stacking = MY_CL_Stacking(models=models, configs=configs, dataset=stack_dataset, config=config, no_cuda=False)
    X, s, flipped, xfg_id = [data.x.tolist()[0] for data in stack_dataset], [data.y.tolist()[0] for data in stack_dataset], [data.flip.tolist()[0] for data in stack_dataset], [data.xfg_id.tolist()[0] for data in stack_dataset]
    
    result = dict()
    result['s'] = s
    result['flip'] = flipped
    result['xfg_id'] = xfg_id 

    confident_joint, psx = latent_estimation.estimate_confident_joint_and_cv_pred_proba(
    np.array(X), np.array(s), cv_n_folds=config.cl.cv_n_folds, thresholds=[0.6, 0.6], clf=stacking)
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
    
    output_path = join(config.res_folder, config.name ,'cl_result', config.dataset.name, str(int(noise_rate * 100)) + '_percent_res.json')
    if not os.path.exists(os.path.dirname(output_path)):
        os.makedirs(os.path.dirname(output_path))
    write_json(result, output=output_path)

# train_cl('CWE020', 0.1)
# train_cl('CWE020', 0.2)
# train_cl('CWE020', 0.3)
# train_cl('CWE190', 0.1)
# train_cl('CWE190', 0.2)
# train_cl('CWE190', 0.3)
# train_cl('CWE125', 0.1)
# train_cl('CWE125', 0.2)
# train_cl('CWE125', 0.3)
# train_cl('CWE119', 0.1)
# train_cl('CWE119', 0.2)
# train_cl('CWE119', 0.3)
# train_cl('CWE400', 0.1)
# train_cl('CWE400', 0.2)
# train_cl('CWE400', 0.3)
# train_cl('CWE787', 0.1)
# train_cl('CWE787', 0.2)
# train_cl('CWE787', 0.3)
# def stack_train_cl(CWE_ID, noisy_rate):
#     from models.stacking.stacking_dataset import StackingDataset
#     from models.stacking.Stacking import VGD_GNN
#     from models.stacking.Stacking import VDP_BLSTM
#     print(np.sum(flipped))
#     rm_xfg_list = xfg_ids[error_labels].tolist()
#     # rm_xfg_list = rm_xfg_list[flipped == True].tolist()
#     print(len(rm_xfg_list))
#     rm_xfg_list.sort()
#     # rm_xfg_list = statistic_cl_and_dt('deepwukong', 'CWE119_v1', 0.1)
#     # rm_xfg_list = select_noise_from_cl_result(_config.name, _config.dataset.name, noisy_rate)
#     train(_config, data_json, 'cl', noisy_rate, rm_xfg_list=rm_xfg_list)


def trans_data(CWE_ID):
    dwk_data_path = '/home/niexu/project/python/noise_reduce/data/CWES/{}/{}.json'.format(CWE_ID, CWE_ID)
    config = get_config(CWE_ID, 'sysevr')
    sys_data_path = os.path.join(config.data_folder, config.name, f'{CWE_ID}_test', f'{CWE_ID}_test.json')
    dwk_data = read_json(dwk_data_path)
    sys_data = []
    for data in dwk_data:
        nodes_lineNo = data['nodes-lineNo']
        nodes_line_sym = data['nodes-line-sym']
        
        zipped = zip(nodes_lineNo, nodes_line_sym)
        sort_zipped = sorted(zipped,key=lambda x:(x[0]))
        nodes_line_sys_sorted = [node  for _, node in sort_zipped]
        sys = dict()
        sys['gadget'] = nodes_line_sys_sorted
        sys['val'] = data['target']
        sys['xfg_id'] = data['xfg_id']
        sys['flip'] = data['flip']
        sys_data.append(sys)
    os.makedirs(os.path.dirname(sys_data_path), exist_ok=True)
    write_json(sys_data, sys_data_path)
        
# train("CWE125")
# trans_data('CWE125')
def train_w2v(CWE_ID):
    config = get_config(CWE_ID, 'sysevr')
    vectorizer = GadgetVectorizer(config=config)
    w2v_path = os.path.join(config.data_folder, config.name, config.dataset.name,
                         "w2v.model")
    vocab_path = os.path.join(config.data_folder, config.name,
                           config.dataset.name, "vocab.pkl")  
    data_path = os.path.join(config.data_folder, config.name,
                           config.dataset.name, "{}.json".format(config.dataset.name))
    data_json = read_json(data_path)
    for data in data_json:
        vectorizer.add_gadget(data["gadget"])
    vectorizer.train_model(w2v_path)
    vectorizer.build_vocab(vocab_path) 

# train_w2v('CWE125_test')
# train('CWE125_test')

def confident_learn_sysevr(CWE_ID, noise_rate = 0):
    """
    @description  : confident learning with different noise dataset
    ---------
    @param  :
    -------
    @Returns  :
    -------
    """
    
    config = get_config(CWE_ID, 'stack')
    sys_config = get_config(CWE_ID, 'sysevr')
    dataset_dir = join(config.data_folder, config.name,
                                 config.dataset.name)
    data_path = os.path.join(dataset_dir, '{}.json'.format(config.dataset.name))
    all_data = read_json(data_path)
    w2v_path = os.path.join(dataset_dir, 'w2v', 'w2v.model')
    if config.noise_set not in ['training', 'all']:
        raise RuntimeError("False noise set !!")
    if config.noise_set == 'all':
        noise_info_path = join(config.data_folder, config.name, config.dataset.name, 'noise_info.json')
    elif config.noise_set == 'training':
        sz = len(all_data)
        train_slice = slice(sz // 5, sz)
        all_data = all_data[train_slice]
        noise_info_path = join(config.data_folder, config.name, config.dataset.name, 'training_noise_info.json')
    output_path = os.path.join(config.res_folder, config.name ,'cl_result_sys', config.dataset.name, str(int(noise_rate * 100)) + '_percent_res.json')

    vectorizer = GadgetVectorizer(config)

    vectorizer.load_model(w2v_path=w2v_path)
    noise_key = '{}_percent'.format(int(noise_rate * 100))
    noise_info = read_json(noise_info_path)
    noise_xfg_ids = noise_info[noise_key]['noise_xfg_ids']
    
    
    all_data = flip_data(all_data, noise_xfg_ids)
    random.shuffle(all_data)
    
    # from models.stacking.stacking_dataset import StackingDataset
    from models.cl.my_cl_model import MY_SYS_BGRU
    from models.sysevr.buffered_path_context import BufferedPathContext as BPC_sys
    
    X = []
    labels = []
    for gadget in all_data:
        xfg_nodes = gadget["nodes-line-sym"]
        nodes_lineNo = gadget['nodes-lineNo']
        # print("Processing gadgets...", count, end="\r")
        zipped = zip(nodes_lineNo, xfg_nodes)
        sort_zipped = sorted(zipped,key=lambda x:(x[0]))
        nodes_line_sys_sorted = [node  for _, node in sort_zipped]
        vector, backwards_slice = vectorizer.vectorize2(nodes_line_sys_sorted)
        X.append((vector, gadget['xfg_id'], gadget['flip']))
        labels.append(gadget["target"])

    data = BPC_sys.create_from_lists(list(X), list(labels))
    
    
    X, s, xfg_id, flipped = [i[0] for i in data], [i[1] for i in data], [i[3] for i in data], [i[4] for i in data]
    result = dict()
    

    # psx = latent_estimation.estimate_cv_predicted_probabilities(
    # np.array(data), np.array(s), cv_n_folds=config.cl.cv_n_folds, clf=MY_SYS_BGRU(config=config, data=data, no_cuda=False))
    confident_joint, psx = latent_estimation.estimate_confident_joint_and_cv_pred_proba(
    np.array(data), np.array(s), cv_n_folds=sys_config.cl.cv_n_folds, thresholds=[0.6, 0.6], clf=MY_SYS_BGRU(config=sys_config, data=data, no_cuda=False))
   

    ordered_label_errors = get_noise_indices(
        s=np.array(s),
        confident_joint=confident_joint,
        psx=psx
        # sorted_index_method='normalized_margin', # Orders label errors
    )
    error_labels = ordered_label_errors.tolist()
    all_info = list()
    for label, flip, idx, pre, el in zip(s, flipped, xfg_id, psx.tolist(), error_labels):
        all_info.append((label, flip, idx, pre, el))
    result['all_info'] = all_info
    result['s'] = s
    result['flip'] = flipped
    result['xfg_id'] = xfg_id
    result['psx'] = psx.tolist()
    result['error_label'] = error_labels
    
    print('cl_result', np.sum(np.array(flipped)[error_labels]), len(np.array(flipped)[error_labels]), np.sum(np.array(flipped)))
    if not os.path.exists(os.path.dirname(output_path)):
        os.makedirs(os.path.dirname(output_path))
    write_json(result, output=output_path)
    
# confident_learn_sysevr('CWE125', 0.1)    
# confident_learn_sysevr('CWE125', 0.2)
# confident_learn_sysevr('CWE125', 0.3)
# confident_learn_sysevr('CWE190', 0.1)
# confident_learn_sysevr('CWE190', 0.2)
# confident_learn_sysevr('CWE190', 0.3)
# confident_learn_sysevr('CWE119', 0.1)
# confident_learn_sysevr('CWE119', 0.2)
# confident_learn_sysevr('CWE119', 0.3)
# confident_learn_sysevr('CWE400', 0.1)
# confident_learn_sysevr('CWE400', 0.2)
# confident_learn_sysevr('CWE400', 0.3)
# confident_learn_sysevr('CWE787', 0.1)
# confident_learn_sysevr('CWE787', 0.2)
# confident_learn_sysevr('CWE787', 0.3)
# confident_learn_sysevr('CWE020', 0.1)
# confident_learn_sysevr('CWE020', 0.2)
# confident_learn_sysevr('CWE020', 0.3)

def confident_learn_vdp(CWE_ID, noise_rate = 0):
    """
    @description  : confident learning with different noise dataset
    ---------
    @param  :
    -------
    @Returns  :
    -------
    """
    config = get_config(CWE_ID, 'stack')
    vdp_config = get_config(CWE_ID, 'vuldeepecker')
    
    dataset_dir = join(config.data_folder, config.name,
                                 config.dataset.name)
    data_path = os.path.join(dataset_dir, '{}.json'.format(config.dataset.name))
    all_data = read_json(data_path)
    w2v_path = os.path.join(dataset_dir, 'w2v', 'w2v.model')
    if config.noise_set not in ['training', 'all']:
        raise RuntimeError("False noise set !!")
    if config.noise_set == 'all':
        noise_info_path = join(config.data_folder, config.name, config.dataset.name, 'noise_info.json')
    elif config.noise_set == 'training':
        sz = len(all_data)
        train_slice = slice(sz // 5, sz)
        all_data = all_data[train_slice]
        noise_info_path = join(config.data_folder, config.name, config.dataset.name, 'training_noise_info.json')
    output_path = os.path.join(config.res_folder, config.name ,'cl_result_vdp', config.dataset.name, str(int(noise_rate * 100)) + '_percent_res.json')

    
    vectorizer = GadgetVectorizer(config)

    vectorizer.load_model(w2v_path=w2v_path)
    noise_key = '{}_percent'.format(int(noise_rate * 100))
    noise_info = read_json(noise_info_path)
    noise_xfg_ids = noise_info[noise_key]['noise_xfg_ids']
    
    all_data = flip_data(all_data, noise_xfg_ids)
    random.shuffle(all_data)

    # from models.stacking.stacking_dataset import StackingDataset
    from models.cl.my_cl_model import MY_VDP_BLSTM
    from models.vuldeepecker.buffered_path_context import BufferedPathContext as BPC_vdp
    

    X = []
    labels = []
    for gadget in all_data:
        xfg_nodes = gadget["nodes-line-sym"]
        nodes_lineNo = gadget['nodes-lineNo']
        # print("Processing gadgets...", count, end="\r")
        zipped = zip(nodes_lineNo, xfg_nodes)
        sort_zipped = sorted(zipped,key=lambda x:(x[0]))
        nodes_line_sys_sorted = [node  for _, node in sort_zipped]
        vector, backwards_slice = vectorizer.vectorize2(nodes_line_sys_sorted)
        X.append((vector, backwards_slice, gadget['xfg_id'], gadget['flip']))
        labels.append(gadget["target"])

    data = BPC_vdp.create_from_lists(list(X), list(labels))
    

    X, s, xfg_id, flipped = [i[0] for i in data], [i[1] for i in data], [i[4] for i in data], [i[5] for i in data]
    result = dict()
    

    confident_joint, psx = latent_estimation.estimate_confident_joint_and_cv_pred_proba(
    np.array(data), np.array(s), cv_n_folds=vdp_config.cl.cv_n_folds, thresholds=[0.6, 0.6], clf=MY_VDP_BLSTM(config=vdp_config, data=data, no_cuda=False))
    

    ordered_label_errors = get_noise_indices(
        s=np.array(s),
        confident_joint=confident_joint,
        psx=psx
        # sorted_index_method='normalized_margin', # Orders label errors
    )
    error_labels = ordered_label_errors.tolist()

    all_info = list()

    for label, flip, idx, pre, el in zip(s, flipped, xfg_id, psx.tolist(), error_labels):
        all_info.append((label, flip, idx, pre, el))
    result['all_info'] = all_info
    result['s'] = s
    result['flip'] = flipped
    result['xfg_id'] = xfg_id
    result['psx'] = psx.tolist()
    result['error_label'] = error_labels
    print('cl_result', np.sum(np.array(flipped)[error_labels]), len(np.array(flipped)[error_labels]), np.sum(np.array(flipped)))
    if not os.path.exists(os.path.dirname(output_path)):
        os.makedirs(os.path.dirname(output_path))
    write_json(result, output=output_path)

# confident_learn_vdp('CWE125', 0.1)
# confident_learn_vdp('CWE125', 0.2)
# confident_learn_vdp('CWE125', 0.3)
# confident_learn_vdp('CWE190', 0.1)
# confident_learn_vdp('CWE190', 0.2)
# confident_learn_vdp('CWE190', 0.3)
# confident_learn_vdp('CWE119', 0.1)
# confident_learn_vdp('CWE119', 0.2)
# confident_learn_vdp('CWE119', 0.3)
# confident_learn_vdp('CWE400', 0.1)
# confident_learn_vdp('CWE400', 0.2)
# confident_learn_vdp('CWE400', 0.3)
# confident_learn_vdp('CWE787', 0.1)
# confident_learn_vdp('CWE787', 0.2)
# confident_learn_vdp('CWE787', 0.3)
# confident_learn_vdp('CWE020', 0.1)
# confident_learn_vdp('CWE020', 0.2)
# confident_learn_vdp('CWE020', 0.3)


def statistic_dwk(CWE_ID, cl_result):
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
    print(CWE_ID + ' r_count: {} all {} flipped {}'.format(r_count, all, fliped_count) )
    return xfg_id_list


def calc_dwk(CWE_ID, noise_rate):
    config = get_config(CWE_ID, 'deepwukong')
    dwk_res_path = os.path.join(config.res_folder, config.name ,'cl_result', config.dataset.name, str(int(noise_rate * 100)) + '_percent_res.json')
    cl_result_dwk = read_json(dwk_res_path)
    all_info_dwk = list()
    s = cl_result_dwk['s']
    flipped = cl_result_dwk['flip']
    xfg_id = cl_result_dwk['xfg_id']
    psx = cl_result_dwk['psx']
    error_labels = cl_result_dwk['error_label']
    
    for label, flip, idx, pre, el in zip(s, flipped, xfg_id, psx, error_labels):
        all_info_dwk.append((label, flip, idx, pre, el))
    
    all_info_dwk.sort(key=lambda x:x[2])
    
    return all_info_dwk
    

def calc(CWE_ID, noise_rate):
    config = get_config(CWE_ID, 'stack')
    
    sys_res_path = os.path.join(config.res_folder, config.name ,'cl_result_sys', config.dataset.name, str(int(noise_rate * 100)) + '_percent_res.json')
    vdp_res_path = os.path.join(config.res_folder, config.name ,'cl_result_vdp', config.dataset.name, str(int(noise_rate * 100)) + '_percent_res.json')
    output_path = os.path.join(config.res_folder, config.name ,'cl_result_sum', config.dataset.name, str(int(noise_rate * 100)) + '_percent_res.json')
    res_path = os.path.join(config.res_folder, config.name ,'cl_result_sum', config.dataset.name, str(int(noise_rate * 100)) + '_percent_res_stat.json')
    
    cl_result_sys = read_json(sys_res_path)
    cl_result_vdp = read_json(vdp_res_path)
    
    all_info_sys = cl_result_sys['all_info']
    all_info_vdp = cl_result_vdp['all_info']
    
    result = dict()
    info = list()
    
    stat = dict()
    all_tp = list()
    all_tn = list()
    all_fp = list()
    all_fn = list()
    diff_tp = list()
    diff_tn = list()
    posi = list()
    nega = list()
    diff_tp_p = list()
    diff_tp_n = list()
    diff_tn_p = list()
    diff_tn_n = list()
    
    all_info_sys.sort(key=lambda x:x[2])
    all_info_vdp.sort(key=lambda x:x[2])

    all_info_dwk = calc_dwk(CWE_ID, noise_rate)
    
    for dwk_info, sys_info, vdp_info in zip(all_info_dwk, all_info_sys,all_info_vdp):
        id = sys_info[2]
        
        if (not dwk_info[1]) and (not dwk_info[4]):
            dwk_tag=0
        elif dwk_info[1] and dwk_info[4]:
            dwk_tag=1
        elif (not dwk_info[1]) and dwk_info[4]:
            dwk_tag=2
        elif dwk_info[1] and (not dwk_info[4]):
            dwk_tag=3
        
        if (not sys_info[1]) and (not sys_info[4]):
            sys_tag=0
        elif sys_info[1] and sys_info[4]:
            sys_tag=1
        elif (not sys_info[1]) and sys_info[4]:
            sys_tag=2
        elif (sys_info[1]) and (not sys_info[4]):
            sys_tag=3
        
        if (not vdp_info[1]) and (not vdp_info[4]):
            vdp_tag = 0
        elif vdp_info[1] and vdp_info[4]:
            vdp_tag = 1
        elif (not vdp_info[1]) and vdp_info[4]:
            vdp_tag = 2
        elif vdp_info[1] and (not vdp_info[4]):
            vdp_tag = 3
        
        info.append((id, dwk_tag, sys_tag, vdp_tag))
        
        if dwk_tag == sys_tag and sys_tag == vdp_tag:
            if dwk_tag == 1:
               all_tp.append(id)
            elif dwk_tag == 0:
                all_tn.append(id)
            elif dwk_tag ==2:
                all_fp.append(id)
            elif dwk_tag == 3:
                all_fn.append(id)
        
        elif dwk_tag == 0 or sys_tag == 0 or vdp_tag == 0:
            diff_tp.append(id)
        elif dwk_tag == 1 or sys_tag == 1 or vdp_tag == 1:
            diff_tn.append(id)
    
    # dwk_weight=0.4
    # sys_weight=0.3
    # vdp_weight=0.3
    
    # for inf in info:
        
    #     weight = inf[1]*dwk_weight+inf[2]*sys_weight+inf[3]*vdp_weight
    
    for inf in info:
        tag = [inf[1], inf[2], inf[3]]
        tag.sort()
        if tag == [0,0,2]:
            diff_tp_p.append(inf[0])
        elif tag == [0,2,2]:
            diff_tp_n.append(inf[0])
        elif tag == [1,1,3]:
            diff_tn_p.append(inf[0])
        elif tag == [1,3,3]:
            diff_tn_n.append(inf[0])
    print(len(diff_tp_p), len(diff_tp_n), len(diff_tn_p), len(diff_tn_n))
    print('all_tp:{} all_tn:{} diff_tp:{} diff_tn:{} all_fp:{} all_fn:{}'.format(len(all_tp), len(all_tn), len(diff_tp), len(diff_tn), len(all_fp), len(all_fn)))
    print(len(all_tp), len(all_tn), len(all_fp), len(all_fn), len(diff_tp), len(diff_tn))
    stat['all_tp'] = all_tp
    stat['all_tn'] = all_tn
    stat['all_fp'] = all_fp
    stat['all_fn'] = all_fn
    stat['diff_tp'] = diff_tp
    stat['diff_tn'] = diff_tn
    # stat['count'] = (len(all_tp), len(all_tn), len(all_fp), len(all_fn), len(diff_tp), len(diff_tn))
    
    write_json(stat, res_path)
    
    result['info'] = info
    # result['dwk'] = all_info_dwk
    # result['sys'] = all_info_sys
    # result['vdp'] = all_info_vdp
    write_json(result, output_path)
    
# calc('CWE125', 0.1)
# calc('CWE125', 0.2)
# calc('CWE125', 0.3)
# calc('CWE190', 0.1)
# calc('CWE190', 0.2)
# calc('CWE190', 0.3)
# calc('CWE119', 0.1)
# calc('CWE119', 0.2)
# calc('CWE119', 0.3)
# calc('CWE400', 0.1)
# calc('CWE400', 0.2)
# calc('CWE400', 0.3)
# calc('CWE787', 0.1)
# calc('CWE787', 0.2)
# calc('CWE787', 0.3)
# calc('CWE020', 0.1)
# calc('CWE020', 0.2)
# calc('CWE020', 0.3)

def statistic_cl_result(CWEID, noisy_rate:float = None):
    """
    @description  : statistic confident learning result
    ---------
    @param  :
    -------
    @Returns  :
    -------
    """
    config = get_config(CWEID, 'stack')
    method = config.name
    cwe_id = config.dataset.name
    res = config.res_folder
    if method not in ['deepwukong', 'sysevr', 'vuldeepecker', 'reveal', 'stack']:
        raise RuntimeError('{} name error !'.format(method))

    # if noisy_rate not in [0.1, 0.2, 0.3, 0.4]:
    #     raise RuntimeError('{} noisy rate error !'.format(noisy_rate))
    data_path = '{}/{}/cl_result_sum/{}/{}_percent_res.json'.format(res, method, cwe_id, int(noisy_rate*100))
    
    data = read_json(data_path)
    info = data['info']
    fliped = list()
    error_label = list()
    xfg_ids = list()
    
    for inf in info:
        xfg_ids.append(inf[0])
        xfg_ids.sort()
        
        tag = [inf[1], inf[2], inf[3]]
        tag.sort()

        if tag == [0,0,0] or tag ==[0,0,2]:
            fliped.append(False)
            error_label.append(False)
        elif tag == [1,1,1] or tag == [1,1,3]:
            fliped.append(True)
            error_label.append(True)
        elif tag == [2,2,2] or tag == [0,2,2]:
            fliped.append(False)
            error_label.append(True)
        elif tag == [3,3,3] or tag == [1,3,3]:
            fliped.append(True)
            error_label.append(False)
    # labels = data['s']
    # error_label = data['error_label']
    # fliped = data['flip']
    # idxs = data['xfg_id']
    data['xfg_id'] = xfg_ids
    data['flip'] = fliped
    data['error_labels'] = error_label
    
    # write_json(data, data_path)
    
    fliped = np.array(fliped)
    # print(fliped)
    # print(fliped[error_label])
    found_noise_count = len(fliped[error_label])
    found_true_count = np.sum(fliped[error_label])
    # found_labels = np.array(labels)[error_label]
    # found_1_count = found_labels.sum()
    # found_0_count = len(found_labels) - found_labels.sum()
    flipped = np.sum(fliped)
    
    # idxs = np.array(idxs)
    

    
    result = dict()
    result['title'] = '{}_{}_{}_{}_percent'.format(method, 'cl', cwe_id, int(noisy_rate * 100))
    result['sample_count'] = len(fliped)
    result['flipped'] = flipped
    result['found_noisy_count'] = found_noise_count
    # result['found_1_count'] = found_1_count
    # result['found_0_count'] = found_0_count
    result['TP_count'] = found_true_count
    result['FP_count'] = found_noise_count - found_true_count
    result['recall'] = round(found_true_count / flipped ,2)
    result['precision'] = round( found_true_count / found_noise_count ,2)
    # result['noisy_rate_after_cl'] = round((flipped - found_true_count) 
    #  / (len(fliped) - found_noise_count), 2)
    print(result)
    return result

# statistic_cl_result('CWE125', 0.1)
# statistic_cl_result('CWE125', 0.2)
# statistic_cl_result('CWE125', 0.3)
# statistic_cl_result('CWE190', 0.1)
# statistic_cl_result('CWE190', 0.2)
# statistic_cl_result('CWE190', 0.3)
# statistic_cl_result('CWE119', 0.1)
# statistic_cl_result('CWE119', 0.2)
# statistic_cl_result('CWE119', 0.3)
# statistic_cl_result('CWE400', 0.1)
# statistic_cl_result('CWE400', 0.2)
# statistic_cl_result('CWE400', 0.3)
# statistic_cl_result('CWE787', 0.1)
# statistic_cl_result('CWE787', 0.2)
# statistic_cl_result('CWE787', 0.3)
# statistic_cl_result('CWE020', 0.1)
# statistic_cl_result('CWE020', 0.2)
# statistic_cl_result('CWE020', 0.3)

def dwk_cl_train(CWEID, noisy_rate):
    """
    @description  : train deepwukong after removing noisy samples found by cl 
    ---------
    @param  :
    -------
    @Returns  :
    -------
    """
    
    _config = get_config(CWEID, 'deepwukong')
    _config.res_folder = 'res1'
    _config.noise_set = 'training'
    # print_config(_config)
    # ws_fliped_path = '/home/niexu/project/python/deepwukong/data/diff_train/CWE119/flipped/bigjson_flip.json'
    noise_key = '{}_percent'.format(int(noisy_rate * 100))
    data_path = os.path.join(_config.data_folder, 'CWES', _config.dataset.name, '{}.json'.format(_config.dataset.name))
    data_json = read_json(data_path)
    
    cl_result_path = join(_config.res_folder, 'stack' ,'cl_result_sum', _config.dataset.name, str(int(noisy_rate * 100)) + '_percent_res.json')
    result = read_json(cl_result_path)
    xfg_ids = np.array(result['xfg_id'])
    # print(xfg_ids)
    flipped = np.array(result['flip'])
    error_labels = result['error_labels']
    # print(error_labels)
    flipped = flipped[error_labels]
    # print(flipped)
    # print(np.sum(flipped))
    
    # fliped = result['flip']
    # fl_xfg_list = xfg_ids[fliped].tolist()
    # # print(fl_xfg_list)
    # err_xfg_list = xfg_ids[error_labels].tolist()
    # # print(err_xfg_list)
    # # print(len(rm_xfg_list))
    
    # rv_xfg_list = list()
    # for fl_xfg in fl_xfg_list:
    #     if fl_xfg in err_xfg_list:
    #         rv_xfg_list.append(fl_xfg)    
    rv_xfg_list = xfg_ids[error_labels].tolist()
    rv_xfg_list.sort()
    # print(rv_xfg_list)
    # rm_xfg_list = statistic_cl_and_dt('deepwukong', 'CWE119_v1', 0.1)
    # rm_xfg_list = select_noise_from_cl_result(_config.name, _config.dataset.name, noisy_rate)
    
    from dwk_train import train
    train(_config, data_json, 'cl', noisy_rate, rv_xfg_list=rv_xfg_list)
    # from sysevr_train import train
    # train(_config, data_json, 'cl', noisy_rate=noisy_rate, rm_id_list=rv_xfg_list)

# dwk_cl_train('CWE125',0.1)
# dwk_cl_train('CWE125',0.2)
# dwk_cl_train('CWE125',0.3)
# dwk_cl_train('CWE190',0.1)
# dwk_cl_train('CWE190',0.2)
# dwk_cl_train('CWE190',0.3)
# dwk_cl_train('CWE119',0.1)
# dwk_cl_train('CWE119',0.2)
# dwk_cl_train('CWE119',0.3)
# dwk_cl_train('CWE400',0.1)
# dwk_cl_train('CWE400',0.2)
# dwk_cl_train('CWE400',0.3)
# dwk_cl_train('CWE787',0.1)
# dwk_cl_train('CWE787',0.2)
# dwk_cl_train('CWE787',0.3)
# dwk_cl_train('CWE020',0.1)
# dwk_cl_train('CWE020',0.2)
# dwk_cl_train('CWE020',0.3)
import jsonlines
def statistic_dt_result(CWEID, noisy_rate):
    _config = get_config(CWEID, 'vuldeepecker')
    noise_key = '{}_percent'.format(int(noisy_rate * 100))
    data_path = os.path.join(_config.data_folder, 'CWES', _config.dataset.name, '{}.json'.format(_config.dataset.name))
    data_json = read_json(data_path)

    noise_info_path = join(_config.data_folder, 'CWES', _config.dataset.name, 'noise_info.json')
    noise_info = read_json(noise_info_path)
    noise_xfg_ids = noise_info[noise_key]['noise_xfg_ids']

    dt_result_path = join(_config.res_folder, _config.name ,'dt_result', _config.dataset.name, str(int(noisy_rate * 100)) + '_percent_res.jsonl')
    # result = read_json(dt_result_path)
    outlier_list = []
    with jsonlines.open(dt_result_path) as reader:
        for obj in reader:
            outlier_list.extend(obj['outlier_list']) 
    

    # dds_loss = read_json('dds_loss.json')
    # wds_loss = read_json('wds_loss.json')
    info_list = list()
    id_list = list()
    # flip_list = list()
    for outlier in outlier_list:
        xfg_id = outlier[0]
        label = outlier[1]
        flip = outlier[2]
        id_list.append(xfg_id)
        # info_list.add(xfg_id)
        # flip_list.append(flip)

    all_list = list()
    for xfg in data_json:
        xfg_id = xfg['xfg_id']
        label = xfg['target']
        if xfg_id in noise_xfg_ids:
            flip = True
        else: 
            flip = False
        if xfg_id in id_list:
            error_label = True
        else:
            error_label = False
        all_list.append((xfg_id, label, flip, error_label))
    
    tp_list = list()
    tn_list = list()
    fp_list = list()
    fn_list = list()
    for info in all_list:
        xfg_id = info[0]
        label = info[1]
        flip = info[2]
        error_label = info[3]
        if flip == error_label:
            if flip == True:
                tp_list.append(xfg_id)
            else: tn_list.append(xfg_id)
        elif flip == True:
            fp_list.append(xfg_id)
        else: fn_list.append(xfg_id)
    all = dict()
    all['tp_list'] = tp_list
    all['tn_list'] = tn_list
    all['fp_list'] = fp_list
    all['fn_list'] = fn_list
    out_path = join('analysis', _config.name, 'dt_result', _config.dataset.name, str(int(noisy_rate * 100)) + '_percent_res.json')
    write_json(all, out_path)
    # outlier_xfg_id = list()
    # import jsonlines
    # with jsonlines.open(dt_result_path) as f:
    #     for line in f:
    #         outlier_list = line['outlier_list']
            
    #         for outlier in outlier_list:
    #             xfg_id = int(outlier[0])
    #             outlier_xfg_id.append(xfg_id)
    
    # lier_list = list()
    # for xfg in data_json:
    #     xfg_id = xfg['xfg_id']
    #     flip = xfg['flip']
    #     target = xfg['target']
    #     if xfg_id in outlier_xfg_id:
    #         lier_list.append([xfg_id, target, flip])
    # write_json(lier_list, 'test.json')
# statistic_dt_result('CWE125', 0.1)
# statistic_dt_result('CWE125', 0.2)
# statistic_dt_result('CWE125', 0.3)
# statistic_dt_result('CWE119', 0.1)
# statistic_dt_result('CWE119', 0.2)
# statistic_dt_result('CWE119', 0.3)
# statistic_dt_result('CWE190', 0.1)
# statistic_dt_result('CWE190', 0.2)
# statistic_dt_result('CWE190', 0.3)
# statistic_dt_result('CWE400', 0.1)
# statistic_dt_result('CWE400', 0.2)
# statistic_dt_result('CWE400', 0.3)
# statistic_dt_result('CWE020', 0.1)
# statistic_dt_result('CWE020', 0.2)
# statistic_dt_result('CWE020', 0.3)
# statistic_dt_result('CWE787', 0.1)
# statistic_dt_result('CWE787', 0.2)
# statistic_dt_result('CWE787', 0.3)

def statistic_dwk_cl_result(CWEID, noisy_rate):
    _config = get_config(CWEID, 'vuldeepecker')
    noise_key = '{}_percent'.format(int(noisy_rate * 100))
    data_path = os.path.join(_config.data_folder, 'CWES', _config.dataset.name, '{}.json'.format(_config.dataset.name))
    data_json = read_json(data_path)
    
    noise_info_path = join(_config.data_folder, 'CWES', _config.dataset.name, 'noise_info.json')
    noise_info = read_json(noise_info_path)
    noise_xfg_ids = noise_info[noise_key]['noise_xfg_ids']
    
    cl_result_path = join(_config.res_folder, _config.name ,'cl_result', _config.dataset.name, str(int(noisy_rate * 100)) + '_percent_res.json')
    cl_data = read_json(cl_result_path)

    xfg_id_list = cl_data['idx']
    
    flip_list = cl_data['flips']
    error_label_list = cl_data['error_label']
    all_list = list()
    for idx, xfg_id in enumerate(xfg_id_list):
        all_list.append((xfg_id, flip_list[idx], error_label_list[idx]))

    tp_list = list()
    tn_list = list()
    fp_list = list()
    fn_list = list()
    for info in all_list:
        xfg_id = info[0]
        flip = info[1]
        error_label = info[2]
        if flip == error_label:
            if flip == True:
                tp_list.append(xfg_id)
            else: tn_list.append(xfg_id)
        elif flip == True:
            fp_list.append(xfg_id)
        else: fn_list.append(xfg_id)
    all = dict()
    all['tp_list'] = tp_list
    all['tn_list'] = tn_list
    all['fp_list'] = fp_list
    all['fn_list'] = fn_list
    out_path = join('analysis', _config.name, 'cl_result', _config.dataset.name, str(int(noisy_rate * 100)) + '_percent_res.json')
    write_json(all, out_path)
# statistic_dwk_cl_result('CWE125', 0.1)
# statistic_dwk_cl_result('CWE125', 0.2)
# statistic_dwk_cl_result('CWE125', 0.3)
# statistic_dwk_cl_result('CWE119', 0.1)
# statistic_dwk_cl_result('CWE119', 0.2)
# statistic_dwk_cl_result('CWE119', 0.3)
# statistic_dwk_cl_result('CWE190', 0.1)
# statistic_dwk_cl_result('CWE190', 0.2)
# statistic_dwk_cl_result('CWE190', 0.3)
# statistic_dwk_cl_result('CWE400', 0.1)
# statistic_dwk_cl_result('CWE400', 0.2)
# statistic_dwk_cl_result('CWE400', 0.3)
# statistic_dwk_cl_result('CWE020', 0.1)
# statistic_dwk_cl_result('CWE020', 0.2)
# statistic_dwk_cl_result('CWE020', 0.3)
# statistic_dwk_cl_result('CWE787', 0.1)
# statistic_dwk_cl_result('CWE787', 0.2)
# statistic_dwk_cl_result('CWE787', 0.3)

def analysis_cl_dt_result(CWEID, noisy_rate):
    _config = get_config(CWEID, 'vuldeepecker')
    cl_path = join('analysis', _config.name, 'cl_result', _config.dataset.name, str(int(noisy_rate * 100)) + '_percent_res.json')
    dt_path = join('analysis', _config.name, 'dt_result', _config.dataset.name, str(int(noisy_rate * 100)) + '_percent_res.json')
    
    cl_data = read_json(cl_path)
    dt_data = read_json(dt_path)

    cl_tp_list = cl_data['tp_list']
    cl_tn_list = cl_data['tn_list']
    cl_fp_list = cl_data['fp_list']
    cl_fn_list = cl_data['fn_list']

    dt_tp_list = dt_data['tp_list']
    dt_tn_list = dt_data['tn_list']
    dt_fp_list = dt_data['fp_list']
    dt_fn_list = dt_data['fn_list']

    both_tp = set(cl_tp_list) & set(dt_tp_list)
    both_tn = set(cl_tn_list) & set(dt_tn_list)
    both_fp = set(cl_fp_list) & set(dt_fp_list)
    both_fn = set(cl_fn_list) & set(dt_fn_list)
    all = dict()
    all['both_tp'] = list(both_tp)
    all['both_tn'] = list(both_tn)
    all['both_fp'] = list(both_fp)
    all['both_fn'] = list(both_fn)
    print(len(both_tp))
    print(len(both_tn))
    print(len(both_fp))
    print(len(both_fn))
    data_path = os.path.join(_config.data_folder, 'CWES', _config.dataset.name, '{}.json'.format(_config.dataset.name))
    data_json = read_json(data_path)
    mixed_list = all['both_tp']+all['both_tn']+all['both_fp']+all['both_fn']
    xfg_id = list()
    flip = list()
    error_labels = list()
    for xfg in data_json:
        if xfg['xfg_id'] in mixed_list:
            xfg_id.append(xfg['xfg_id'])
            if xfg['xfg_id'] in all['both_tp']:
                flip.append(True)
                error_labels.append(True)
            elif xfg['xfg_id'] in all['both_tn']:
                flip.append(False)
                error_labels.append(False)
            elif xfg['xfg_id'] in all['both_fp']:
                flip.append(False)
                error_labels.append(True)
            elif xfg['xfg_id'] in all['both_fn']:
                flip.append(True)
                error_labels.append(False)
    fliped = np.array(flip)
    found_noise_count = len(fliped[error_labels])
    found_true_count = np.sum(fliped[error_labels])
    
    flipped = np.sum(fliped)

    result = dict()
    result['title'] = '{}_{}_{}_percent'.format('mixed', CWEID, int(noisy_rate * 100))
    result['sample_count'] = len(fliped)
    result['flipped'] = flipped
    result['found_noisy_count'] = found_noise_count
    result['TP_count'] = found_true_count
    result['FP_count'] = found_noise_count - found_true_count
    result['recall'] = round(found_true_count / flipped ,2)
    result['precision'] = round( found_true_count / found_noise_count ,2)
    result['noisy_rate_after_cl'] = round((flipped - found_true_count) 
     / (len(fliped) - found_noise_count), 2)
    print(result)
    # out_path = join('analysis',  _config.dataset.name + '_' + str(int(noisy_rate * 100)) + '_percent_res.json')
    # write_json(all, out_path)

# analysis_cl_dt_result('CWE125', 0.1)
# analysis_cl_dt_result('CWE125', 0.2)
# analysis_cl_dt_result('CWE125', 0.3)
# analysis_cl_dt_result('CWE119', 0.1)
# analysis_cl_dt_result('CWE119', 0.2)
# analysis_cl_dt_result('CWE119', 0.3)
# analysis_cl_dt_result('CWE190', 0.1)
# analysis_cl_dt_result('CWE190', 0.2)
# analysis_cl_dt_result('CWE190', 0.3)
# analysis_cl_dt_result('CWE400', 0.1)
# analysis_cl_dt_result('CWE400', 0.2)
# analysis_cl_dt_result('CWE400', 0.3)
# analysis_cl_dt_result('CWE787', 0.1)
# analysis_cl_dt_result('CWE787', 0.2)
# analysis_cl_dt_result('CWE787', 0.3)
# analysis_cl_dt_result('CWE020', 0.1)
# analysis_cl_dt_result('CWE020', 0.2)
# analysis_cl_dt_result('CWE020', 0.3)

def dwk_mixed_train(CWEID, noisy_rate):
    """
    @description  : train deepwukong after removing noisy samples found by cl 
    ---------
    @param  :
    -------
    @Returns  :
    -------
    """
    
    _config = get_config(CWEID, 'deepwukong')
    data_path = os.path.join(_config.data_folder, 'CWES', _config.dataset.name, '{}.json'.format(_config.dataset.name))
    data_json = read_json(data_path)
    
    # noise_info_path = join(_config.data_folder, 'CWES', _config.dataset.name, 'noise_info.json')
    # noise_info = read_json(noise_info_path)

    mixed_path = join('analysis',  _config.dataset.name + '_' + str(int(noisy_rate * 100)) + '_percent_res.json')
    mixed_data = read_json(mixed_path)
    mixed_list = mixed_data['both_tp']+mixed_data['both_tn']+mixed_data['both_fp']+mixed_data['both_fn']
    false_list = mixed_data['both_fp']+mixed_data['both_fn']
    # rm_list = random.sample(false_list, 0)
    # rm_list = random.sample(false_list, len(false_list))
    # rm_list = random.sample(false_list, (int)(len(false_list)/2))
    # rm_list = random.sample(false_list, (int)(len(false_list)/3))
    # rm_list = random.sample(false_list, (int)(len(false_list)/5))
    rm_list = random.sample(false_list, (int)(len(false_list)/3*2))

    xfg_id = list()
    flip = list()
    error_labels = list()
    for xfg in data_json:
        if xfg['xfg_id'] in mixed_list:
            xfg_id.append(xfg['xfg_id'])
            if xfg['xfg_id'] in mixed_data['both_tp']:
                flip.append(True)
                error_labels.append(True)
            elif xfg['xfg_id'] in mixed_data['both_tn']:
                flip.append(False)
                error_labels.append(False)
            elif xfg['xfg_id'] in false_list:
                if xfg['xfg_id'] in rm_list:
                    flip.append(False)
                    error_labels.append(False)
                else: 
                    flip.append(False)
                    error_labels.append(True)

            # elif xfg['xfg_id'] in mixed_data['both_fp']:
            #     flip.append(False)
            #     error_labels.append(False)
            # elif xfg['xfg_id'] in mixed_data['both_fn']:
            #     flip.append(True)
            #     error_labels.append(False)
                
    xfg_ids = np.array(xfg_id)
    # print(xfg_ids)
    flipped = np.array(flip)
    error_labels = error_labels
    # print(error_labels)
    flipped = flipped[error_labels]
    rm_xfg_list = xfg_ids[error_labels].tolist()
    rm_xfg_list.sort()
    
    # print(rv_xfg_list)
    # rm_xfg_list = statistic_cl_and_dt('deepwukong', 'CWE119_v1', 0.1)
    # rm_xfg_list = select_noise_from_cl_result(_config.name, _config.dataset.name, noisy_rate)
    
    from dwk_train import train
    train(_config, data_json, 'cl', noisy_rate, rm_xfg_list=rm_xfg_list)

# dwk_mixed_train('CWE125', 0.1)
# dwk_mixed_train('CWE125', 0.2)
# dwk_mixed_train('CWE125', 0.3)
# dwk_mixed_train('CWE119', 0.1)
# dwk_mixed_train('CWE119', 0.2)
# dwk_mixed_train('CWE119', 0.3)
# dwk_mixed_train('CWE190', 0.1)
# dwk_mixed_train('CWE190', 0.2)
# dwk_mixed_train('CWE190', 0.3)
# dwk_mixed_train('CWE400', 0.1)
# dwk_mixed_train('CWE400', 0.2)
# dwk_mixed_train('CWE400', 0.3)
# dwk_mixed_train('CWE020', 0.1)
# dwk_mixed_train('CWE020', 0.2)
# dwk_mixed_train('CWE020', 0.3)
# dwk_mixed_train('CWE787', 0.1)
# dwk_mixed_train('CWE787', 0.2)
# dwk_mixed_train('CWE787', 0.3)

for method in ['vuldeepecker', 'sysevr']:
    for cwe in ["CWE190", "CWE787", "CWE400", "CWE125", "CWE119", "CWE020"]:
        print("---------------------------------------------------------------------------")
        config  = get_config(cwe, method)
        vdp_statistic_cdg_duplicate(config, f'/home/niexu/project/python/noise_reduce/data/{method}/{cwe}/{cwe}_raw.json')