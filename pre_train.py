
#!/usr/bin/env python
# -*- encoding: utf-8 -*-
'''
@Description:       : generate fliped label data and doc2vec model for each dataset
@Date     :2021/08/04 10:28:01
@Author      :ives-nx
@version      :1.0
'''
import json
import numpy as np
from numpy.lib.utils import source
from gensim.models.doc2vec import Doc2Vec, TaggedDocument
import os
import random
import shutil
from utils.json_ops import read_json, write_json, get_data_json
from argparse import ArgumentParser
from utils.gen_noise import gen_noise_for_dwk, gen_noise_for_cdg, gen_noise_for_dwk_d2a, gen_noise_for_cdg_d2a
from utils.common import print_config, filter_warnings, get_config_dwk
from tools.joern_slicer.d2a_src_parse import d2a_xfg_test_label

from gensim.models.word2vec import Word2Vec
import nltk

class Sentences:
    def __init__(self, data):
        self.datas: list = data

    def __iter__(self):
        for graph_data in self.datas:
            contents = graph_data["node-line-content"]
            for statement in contents:
                statement_after_split = nltk.word_tokenize(statement)
                yield statement_after_split





def train_w2v_model_for_reveal(config):
    src_file = os.path.join(config.data_folder, config.name, config.dataset.name, f'{config.dataset.name}.json')
    test_file = os.path.join(config.data_folder, config.name, config.dataset.name, f'true_test.json')
    d2v_model_path = os.path.join(config.data_folder, config.name, config.dataset.name,
                                  f'w2v_model/{config.dataset.name}.w2v')
    os.makedirs(os.path.dirname(d2v_model_path), exist_ok=True)
    sentences = Sentences(read_json(src_file) + read_json(test_file))
    model = Word2Vec(sentences, size=config.hyper_parameters.vector_length, window=10, hs=1, min_count=1, iter=15)
    model.save(d2v_model_path)





def flip_data_label(nosiy_rate, train_data_json):
    r_samples = np.random.choice(train_data_json,int(len(train_data_json) * nosiy_rate),replace=False)
    
    for r in train_data_json:
        if r in r_samples:
            r['target'] = r['target'] ^ 1
            r['flip'] = True
   
    print("has fliped " + str(len(r_samples)) + ' samples')





def doc2vec(cwe_id):
    data_json_path = '/home/niexu/project/python/noise_reduce/data/CWES/{}/{}.json'.format(cwe_id, cwe_id)
    doc2vec_path =  '/home/niexu/project/python/noise_reduce/data/CWES/{}/d2v_model/{}.model'.format(cwe_id, cwe_id)
    if not os.path.exists(os.path.dirname(doc2vec_path)):
        os.makedirs(os.path.dirname(doc2vec_path))
    data_json = read_json(data_json_path)
    
    documents = list()
    for idx, xfg in enumerate(data_json, start=0):
        xfg_id = xfg['xfg_id']
        xfg_nodes = xfg["nodes-line-sym"]  # ??????CFG???????????????
        for node_idx in range(len(xfg_nodes)):  # ????????????CFG??????
            node = xfg_nodes[node_idx]  # ??????node?????????
            # print(node.split())
            # print([str(idx) + "_" + str(node_idx)])
            documents.append(
                        TaggedDocument(node.split(), [str(xfg_id) + "_" + str(node_idx)]))
        # print(documents)
    model = Doc2Vec(documents, vector_size=64, min_count=5, workers=8, window=8, dm=0, alpha=0.025,
                    epochs=50)
    
    
    print("START -- saving doc2vec model......")
    model.save(doc2vec_path)
    print("END -- saving doc2vec model......")

def gen_d2v_model():
    cwes_dir = '/home/niexu/project/python/noise_reduce/data/CWES'
    for cwe in os.listdir(cwes_dir):
        print('START -- training {} doc2vec model......'.format(cwe))
        cwe_json = os.path.join(cwes_dir, cwe, cwe+'.json')
        d2v_path = os.path.join(cwes_dir, cwe, 'd2v_model/{}.model'.format(cwe))
        if not os.path.exists(os.path.dirname(d2v_path)):
            os.mkdir(os.path.dirname(d2v_path))
        doc2vec(cwe_json, d2v_path)
        print('END -- training {} doc2vec model......'.format(cwe))

def gen_d2v_model_for_d2a():
    pass

def gen_noisy_data():
    """
    @description  : generate noisy data for dwk 
        {
            '20_percent':{
                'train_pair_ids':[],
                'train_xfg_ids':[],
                'val_pair_ids':[],
                'val_xfg_ids':[],
                'test_pair_ids':[],
                'test_xfg_ids':[],
                'noisy_pair_ids':[],
                'noisy_xfg_ids':[]
            }
        }
    ---------
    @param  :
    -------
    @Returns  :
    -------
    """
    
    
    cwes_dir = '/home/niexu/project/python/noise_reduce/data/CWES' 
    # noisy_rate_list = [0.1,0.3,0.5] 
    # noisy_rate_list = [0,0.1,0.2,0.3]  
    noisy_rate_list = [0,0.1,0.2,0.3,0.4]   

    # for cwe in os.listdir(cwes_dir):
    for cwe in ['CWE119']:
        print('START -- generateing {} noisy data......'.format(cwe))
        noise_info = dict()
        for noisy_rate in noisy_rate_list:
            noise_key = '{}_percent'.format(int(100*noisy_rate))
            noise_info[noise_key] = dict()
            train_pair_ids = []
            val_pair_ids = []
            test_pair_ids = []
            train_xfg_ids = []
            val_xfg_ids = []
            test_xfg_ids = []
            noisy_pair_ids = []
            noisy_xfg_ids = []

            
            cwe_json_path = os.path.join(cwes_dir, cwe, cwe+'.json')
            cwe_json = get_data_json(cwe_json_path)
            pair_ids = set()
            for xfg in cwe_json:
                pair_ids.add(xfg['pair_id'])
            pair_ids = list(pair_ids)    
            sz = len(pair_ids)
            train_pair_ids = pair_ids[slice(sz // 5, sz)]
            val_pair_ids = pair_ids[slice(0, sz//10)]
            test_pair_ids = pair_ids[slice(sz // 10, sz // 5)]
            # np.random.seed(7)
            noisy_pair_ids = np.random.choice(train_pair_ids, int(noisy_rate*len(train_pair_ids)), replace=False).tolist()
            
            for xfg in cwe_json:
                pair_id = xfg['pair_id']
                xfg_id = xfg['xfg_id']
                if pair_id in train_pair_ids:
                    train_xfg_ids.append(xfg_id)
                if pair_id in test_pair_ids:
                    test_xfg_ids.append(xfg_id)
                if pair_id in val_pair_ids:
                    val_xfg_ids.append(xfg_id)
                if pair_id in noisy_pair_ids:
                    noisy_xfg_ids.append(xfg_id)
            noise_info[noise_key]['train_pair_ids'] = train_pair_ids
            noise_info[noise_key]['train_xfg_ids'] = train_xfg_ids
            noise_info[noise_key]['val_pair_ids'] = val_pair_ids
            noise_info[noise_key]['val_xfg_ids'] = val_xfg_ids
            noise_info[noise_key]['test_pair_ids'] = test_pair_ids
            noise_info[noise_key]['test_xfg_ids'] = test_xfg_ids
            noise_info[noise_key]['noisy_pair_ids'] = noisy_pair_ids
            noise_info[noise_key]['noisy_xfg_ids'] = noisy_xfg_ids
            # print(noise_info)
            print(len(train_pair_ids))
            print(len(train_xfg_ids))
            print(len(val_pair_ids))
            print(len(val_xfg_ids))
            print(len(test_pair_ids))
            print(len(test_xfg_ids))
            print(len(noisy_pair_ids))
            print(len(noisy_xfg_ids))
        
        write_json(noise_info, os.path.join(cwes_dir, cwe, cwe+'_noise_info.json'))
        print('END -- generateing {} noisy data......'.format(cwe))


def gen_d2v_for_xfgs(cwe_id, noise_rate):
    xfgs_json_path = os.path.join('data', 'CWES', cwe_id, '{}_percent'.format(int(noise_rate * 100)), 'xfgs.json')
    xfgs_json = read_json(xfgs_json_path)
    d2v_dir = os.path.join('data', 'CWES', cwe_id, '{}_percent'.format(int(noise_rate * 100)), 'd2v_model')
    if not os.path.exists(d2v_dir):
        os.mkdir(d2v_dir)
    doc2vec_path = os.path.join(d2v_dir, 'd2v.model')
    documents = list()
    for key in xfgs_json:
        for idx, xfg in enumerate(xfgs_json[key], start=0):
            xfg_nodes = xfg["nodes-line-sym"]  # ??????CFG???????????????
            for node_idx in range(len(xfg_nodes)):  # ????????????CFG??????
                node = xfg_nodes[node_idx]  # ??????node?????????
                # print(node.split())
                # print([str(idx) + "_" + str(node_idx)])
                documents.append(
                        TaggedDocument(node.split(), [key + '_' + str(idx) + "_" + str(node_idx)]))
    
    
        
        # print(documents)
    model = Doc2Vec(documents, vector_size=64, min_count=5, workers=8, window=8, dm=0, alpha=0.025,
                    epochs=50)
    
    
    print("START -- saving doc2vec model......")
    model.save(doc2vec_path)
    print("END -- saving doc2vec model......")    
def gen_noisy_data_without_pair():
    """
    @description  : generate noisy data for dwk 
        {
            '20_percent':{
                'train_pair_ids':[],
                'train_xfg_ids':[],
                'val_pair_ids':[],
                'val_xfg_ids':[],
                'test_pair_ids':[],
                'test_xfg_ids':[],
                'noisy_pair_ids':[],
                'noisy_xfg_ids':[]
            }
        }
    ---------
    @param  :
    -------
    @Returns  :
    -------
    """
    
    
    cwes_dir = '/home/niexu/project/python/noise_reduce/data/CWES' 
    # noisy_rate_list = [0.1,0.3,0.5] 
    # noisy_rate_list = []  
    noisy_rate_list = [0,0.1,0.2,0.3,0.4]   

    # for cwe in os.listdir(cwes_dir):
    for cwe in ['CWE119']:
        print('START -- generateing {} noisy data......'.format(cwe))
        noise_info = dict()
        for noisy_rate in noisy_rate_list:
            noise_key = '{}_percent'.format(int(100*noisy_rate))
            noise_info[noise_key] = dict()
            train_pair_ids = []
            val_pair_ids = []
            test_pair_ids = []
            train_xfg_ids = []
            val_xfg_ids = []
            test_xfg_ids = []
            noisy_pair_ids = []
            noisy_xfg_ids = []

            
            cwe_json_path = os.path.join(cwes_dir, cwe, cwe+'.json')
            cwe_json = get_data_json(cwe_json_path)
            
            sz = len(cwe_json)
            xfg_ids = list(range(sz))
            train_xfg_ids = xfg_ids[slice(sz // 5, sz)]
            val_xfg_ids = xfg_ids[slice(0, sz//10)]
            test_xfg_ids = xfg_ids[slice(sz // 10, sz // 5)]
            # np.random.seed(7)
            noisy_xfg_ids = np.random.choice(train_xfg_ids, int(noisy_rate*len(train_xfg_ids)), replace=False).tolist()
            
            noise_info[noise_key]['train_pair_ids'] = train_pair_ids
            noise_info[noise_key]['train_xfg_ids'] = train_xfg_ids
            noise_info[noise_key]['val_pair_ids'] = val_pair_ids
            noise_info[noise_key]['val_xfg_ids'] = val_xfg_ids
            noise_info[noise_key]['test_pair_ids'] = test_pair_ids
            noise_info[noise_key]['test_xfg_ids'] = test_xfg_ids
            noise_info[noise_key]['noisy_pair_ids'] = noisy_pair_ids
            noise_info[noise_key]['noisy_xfg_ids'] = noisy_xfg_ids
            # print(noise_info)
            print(len(train_pair_ids))
            print(len(train_xfg_ids))
            print(len(val_pair_ids))
            print(len(val_xfg_ids))
            print(len(test_pair_ids))
            print(len(test_xfg_ids))
            print(len(noisy_pair_ids))
            print(len(noisy_xfg_ids))
        # old_info = read_json(os.path.join(cwes_dir, cwe, cwe+'_noise_info.json'))
        # for info in old_info:
        #     noise_info[info] = old_info[info]
        write_json(noise_info, os.path.join(cwes_dir, cwe, cwe+'_noise_info.json'))
        print('END -- generateing {} noisy data......'.format(cwe))


def divide_big_json(cwe_id):

    data_path = '/home/niexu/project/python/noise_reduce/data/CWES/{}/{}.json'.format(cwe_id, cwe_id)
    out_path = '/home/niexu/project/python/noise_reduce/data/CWES/{}/noise_info.json'.format(cwe_id)
    data = read_json(data_path)
    print(len(data))
    noise_rates = [0, 0.1, 0.2, 0.3]
    noise_info = dict()
    for noise_rate in noise_rates:
        noise_key = '{}_percent'.format(int(noise_rate * 100))
        noise_info[noise_key] = dict()
        
        xfg_ids = []
        for xfg in data:
            xfg_ids.append(xfg['xfg_id'])
        np.random.seed(7)
        noise_xfg_ids = np.random.choice(xfg_ids, int(len(xfg_ids) * noise_rate), replace=False).tolist()

        
        print(len(noise_xfg_ids))
        noise_info[noise_key]['noise_xfg_ids'] = noise_xfg_ids
    write_json(noise_info, out_path)

        

def d2a_downsample(dataset):
    cout_1 = 0
    xfgs = []
    xfg_1 = []
    xfg_0 = []
    downsamples_xfgs = []
    with open('/home/niexu/dataset/d2a/data/{}/bigJson.json'.format(dataset), 'r', encoding='utf8') as f:
        xfgs = json.load(f)
        for xfg in xfgs:
            if xfg['target'] == 1:
                cout_1 += 1
                xfg_1.append(xfg)
            else:
                xfg_0.append(xfg)
        f.close()
    # 
    print(len(xfg_0))
    print(len(xfg_1))
    downsamples_xfg_0s = np.random.choice(xfg_0, 3 * len(xfg_1), replace=False).tolist()
    downsamples_xfgs.extend(xfg_1)
    downsamples_xfgs.extend(downsamples_xfg_0s)
    print(len(downsamples_xfgs))
    random.shuffle(downsamples_xfgs)
    # 
    if  not os.path.exists('data/CWES/{}/'.format(dataset)):
        os.makedirs('data/CWES/{}/'.format(dataset))
    with open('data/CWES/{}/{}.json'.format(dataset, dataset), 'w', encoding='utf8') as f:
        json.dump(downsamples_xfgs, f, indent=2)
        f.close()


def dwk_gen_xfg_test(config):
    #path
    raw_data_path = os.path.join(config.data_folder, 'CWES', config.dataset.name, 'raw', 'raw.json')
    test_data_path = os.path.join(config.data_folder, 'CWES', config.dataset.name, 'raw', 'test.json')
    true_label_info_path = os.path.join(config.data_folder, 'CWES', config.dataset.name, 'raw', 'true_label_info.json')

    doc2vec_path =  os.path.join(config.data_folder, 'CWES', config.dataset.name, "d2v_model/{}.model".format(config.dataset.name))
    train_data_out_path = os.path.join(config.data_folder, 'CWES', config.dataset.name, "{}.json".format(config.dataset.name))
    true_test_out_path = os.path.join(config.data_folder, 'CWES', config.dataset.name, "true_test.json")

    #read
    raw_data = read_json(raw_data_path)
    test_data = read_json(test_data_path)
    true_label_info = read_json(true_label_info_path)

    #remove true label xfgs from raw data 
    new_raw_data = []
    for xfg in raw_data:
        isInTrue = False
        for info in true_label_info:
            if xfg['file_path'] == info['file_path'] and xfg['vul_line'] == info['vul_line']:
                isInTrue = True
                break
        if not isInTrue:
            new_raw_data.append(xfg)
    print('raw_data', len(raw_data))
    print('new_raw_data', len(new_raw_data))

    #test data resample
    xfgs_vul = list()
    xfgs_safe = list()
    for gadget in test_data:
        if gadget['target'] == 1:
            xfgs_vul.append(gadget)
        else:
            xfgs_safe.append(gadget)
    np.random.seed(7)
    if len(xfgs_safe) >= len(xfgs_vul) * 2:
        sub_safe = np.random.choice(xfgs_safe, len(xfgs_vul)*2, replace=False)
    else:
        sub_safe = xfgs_safe
    all_test_data = []
    all_test_data.extend(xfgs_vul)
    all_test_data.extend(sub_safe)
    np.random.shuffle(all_test_data)
    print(len(xfgs_vul), len(sub_safe), len(all_test_data))

    #train d2v model
    
    print("START -- saving doc2vec model......")
    if not os.path.exists(os.path.dirname(doc2vec_path)):
        os.makedirs(os.path.dirname(doc2vec_path))
    
    
    documents = list()
    idx = 0
    for xfg in new_raw_data:
        xfg['xfg_id'] = idx
        xfg['flip'] = False
        xfg_id = idx
        idx += 1
        xfg_nodes = xfg["nodes-line-sym"]  # ??????CFG???????????????
        for node_idx in range(len(xfg_nodes)):  # ????????????CFG??????
            node = xfg_nodes[node_idx]  # ??????node?????????
            # print(node.split())
            # print([str(idx) + "_" + str(node_idx)])
            documents.append(
                        TaggedDocument(node.split(), [str(xfg_id) + "_" + str(node_idx)]))
        # print(documents)
    
    for xfg in all_test_data:
        xfg['xfg_id'] = idx
        xfg['flip'] = False
        xfg_id = idx
        idx += 1
        xfg_nodes = xfg["nodes-line-sym"]  # ??????CFG???????????????
        for node_idx in range(len(xfg_nodes)):  # ????????????CFG??????
            node = xfg_nodes[node_idx]  # ??????node?????????
            # print(node.split())
            # print([str(idx) + "_" + str(node_idx)])
            documents.append(
                        TaggedDocument(node.split(), [str(xfg_id) + "_" + str(node_idx)]))
    model = Doc2Vec(documents, vector_size=64, min_count=5, workers=8, window=8, dm=0, alpha=0.025,
                    epochs=50)
    model.save(doc2vec_path)
    print("END -- saving doc2vec model......")

    #write data
    write_json(new_raw_data, train_data_out_path)
    write_json(all_test_data, true_test_out_path)
    print('end !')


if __name__=="__main__":
    # d2a_downsample('MEMOREY_LEAK')
    # gen_d2v_model()

    # gen_noisy_data_without_pair()
    # gen_d2v_for_xfgs('CWE119', 0)
    arg_parser = ArgumentParser()
    # arg_parser.add_argument("model", type=str)
    # arg_parser.add_argument("--dataset", type=str, default=None)
    arg_parser.add_argument("--offline", action="store_true")
    arg_parser.add_argument("--resume", type=str, default=None)
    args = arg_parser.parse_args()
    cwe_ids = ['CWE125', 'CWE119', 'CWE020', 'CWE190', 'CWE400', 'CWE787']
    for cwe_id in cwe_ids:
        for method in ['reveal']:
            _config = get_config_dwk(cwe_id, method ,log_offline=args.offline)
            train_w2v_model_for_reveal(config=_config)
    # gen_dwk_raw_data_d2a(cwe_id)
    # cwe_id = 'CWE119_d2a'
    # divide_big_json(cwe_id)
    # doc2vec(cwe_id)
    # d2a_xfg_test_label('INTEGER_OVERFLOW_test')
    # _config = get_config_dwk('INTEGER_OVERFLOW_test', 'deepwukong' ,log_offline=args.offline)
    # gen_true_label_for_dwk_d2a()
    # gen_noise_for_dwk_d2a(config=_config)
    # gen_noise_for_cdg_d2a(_config)
    # dwk_gen_xfg_test(_config)
