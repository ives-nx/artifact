#!/usr/bin/env python
# -*- encoding: utf-8 -*-
'''
@Description:       :  create noisy data for vdp and other tool function
@Date     :2021/08/14 19:14:07
@Author      :ives-nx
@version      :1.0
'''

from os import path
from utils.clean_gadget import clean_gadget
from sklearn.model_selection import train_test_split
import numpy
import os
import json
from omegaconf import DictConfig
from models.vuldeepecker.buffered_path_context import BufferedPathContext
from utils.vectorize_gadget import GadgetVectorizer
import hashlib
from utils.unique import getMD5
from utils.json_ops import read_json, write_json
from sklearn.utils import shuffle as sk_shuffle
def parse_file(cgd_txt: str):
    """
    Parses gadget file to find individual gadgets
    Yields each gadget as list of strings, where each element is code line
    Has to ignore first line of each gadget, which starts as integer+space
    At the end of each code gadget is binary value
        This indicates whether or not there is vulnerability in that gadget

    :param cgd_txt: code gadget in txt format
    :return:
    """
    sensi_api_path = 'models/sysevr/resources/sensiAPI.txt'
    with open(cgd_txt, "r", encoding="utf8") as file:
        gadget = []
        gadget_val = 0
        pair_id = 0
        for line in file:
            stripped = line.strip()
            if '|vul_line:' in line and not gadget:
                pair_id = int(line.split('|')[-1].split(':')[-1])
                continue
            if "-" * 33 in line and gadget:
                yield clean_gadget(gadget, sensi_api_path), gadget_val, pair_id
                gadget = []
            elif stripped.split()[0].isdigit():
                if gadget:
                    # Code line could start with number (somehow)
                    if stripped.isdigit():
                        gadget_val = int(stripped)
                    else:
                        gadget.append(stripped)
            else:
                gadget.append(stripped)

def statistic_samples(config: DictConfig):
    holdout_data_path = path.join(
        config.data_folder,
        config.name,
        config.dataset.name,
        "all.txt",
    )

    if (not os.path.exists(holdout_data_path)):
        print(f"there is no file named: {holdout_data_path}")
        return
    sample_count_1 = 0
    sample_count_0 = 0
    for gadget, val in parse_file(holdout_data_path):
        if int(val) == 1:
            sample_count_1 += 1
        else:
            sample_count_0 += 1
    print('sample_count_1: '+str(sample_count_1)+ ' ' +'sample_count_0: '+str(sample_count_0))

def vdp_statistic_cdg_duplicate(config, holdout_data_path):
    if (not os.path.exists(holdout_data_path)):
        print(f"there is no file named: {holdout_data_path}")
        return
    sensi_api_path = 'models/sysevr/resources/sensiAPI.txt'
    
    gadgets = dict()  # {md5:}
    count = 0
    dulCount = 0
    mulCount = 0
    vectorizer = GadgetVectorizer(config)
    cdg_list = read_json(holdout_data_path)
    for cdg in cdg_list:
        gadget = clean_gadget(cdg['content'], sensi_api_path)
        val = cdg['target']
        count += 1
        print("Collecting gadgets...", count, end="\r")
        tokenized_gadget, backwards_slice = GadgetVectorizer.tokenize_gadget(
            gadget)
        tokenized_gadget_md5 = getMD5(str(tokenized_gadget))
        if (tokenized_gadget_md5 not in gadgets):
            row = {"gadget": gadget, "val": val, "count": 0, "file_path": cdg['file_path']}
            gadgets[tokenized_gadget_md5] = row
        else:
            dulCount += 1
            if (gadgets[tokenized_gadget_md5]["val"] != -1):
                if (gadgets[tokenized_gadget_md5]["val"] != val):
                    gadgets[tokenized_gadget_md5]["val"] = -1
                    mulCount += 1
            else:
                mulCount += 1
        gadgets[tokenized_gadget_md5]["count"] += 1
    print('\n')
    print("Find multiple...", mulCount)
    print("Find dulplicate...", dulCount)

def vdp_cdg_duplicate(config, holdout_data_path):
    if (not os.path.exists(holdout_data_path)):
        print(f"there is no file named: {holdout_data_path}")
        return
    vocab_path = path.join(config.data_folder, config.name,
                           config.dataset.name, "vocab.pkl")   
    data_path = path.join(config.data_folder, config.name,
                           config.dataset.name, "{}.json".format(config.dataset.name))   
    if (not os.path.exists(os.path.dirname(data_path))):
        os.makedirs(os.path.dirname(data_path))
    gadgets = dict()  # {md5:}
    count = 0
    dulCount = 0
    mulCount = 0
    vectorizer = GadgetVectorizer(config)
    cdg_list = read_json(holdout_data_path)
    for cdg in cdg_list:
        gadget = clean_gadget(cdg['content'], sensi_api_path)
        val = cdg['target']
        count += 1
        print("Collecting gadgets...", count, end="\r")
        tokenized_gadget, backwards_slice = GadgetVectorizer.tokenize_gadget(
            gadget)
        tokenized_gadget_md5 = getMD5(str(tokenized_gadget))
        if (tokenized_gadget_md5 not in gadgets):
            row = {"gadget": gadget, "val": val, "count": 0, "file_path": cdg['file_path'], "vul_line": cdg['vul_line']}
            gadgets[tokenized_gadget_md5] = row
        else:
            if (gadgets[tokenized_gadget_md5]["val"] != -1):
                if (gadgets[tokenized_gadget_md5]["val"] != val):
                    dulCount += 1
                    gadgets[tokenized_gadget_md5]["val"] = -1
            mulCount += 1
        gadgets[tokenized_gadget_md5]["count"] += 1
    print('\n')
    print("Find multiple...", mulCount)
    print("Find dulplicate...", dulCount)
    gadgets_unique = list()
    for gadget_md5 in gadgets:
        if (gadgets[gadget_md5]["val"] != -1):  # remove dulplicated
            vectorizer.add_gadget(gadgets[gadget_md5]["gadget"])
            gadgets_unique.append(gadgets[gadget_md5])
            # for i in range(gadgets[gadget_md5]["count"]):# do not remove mul
            #     vectorizer.add_gadget(gadgets[gadget_md5]["gadget"])
    # print('Found {} forward slices and {} backward slices'.format(
    #     vectorizer.forward_slices, vectorizer.backward_slices))

    print("Training word2vec model...", end="\r")
    w2v_path = path.join(config.data_folder, config.name, config.dataset.name,
                         "w2v.model")
    
    vectorizer.train_model(w2v_path)
    vectorizer.build_vocab(vocab_path)    
    
    gadget_vul = list()
    gadget_safe = list()
    for gadget in gadgets_unique:
        if gadget['val'] == 1:
            gadget_vul.append(gadget)
        else:
            gadget_safe.append(gadget)
    numpy.random.seed(7)
    
    
    if len(gadget_safe) >= len(gadget_vul) * 2:
        sub_safe = numpy.random.choice(gadget_safe, len(gadget_vul)*2, replace=False)
    else:
        sub_safe = gadget_safe
    all_gadgets = []
    all_gadgets.extend(gadget_vul)
    all_gadgets.extend(sub_safe)
    numpy.random.shuffle(all_gadgets)
    print(len(gadget_vul), len(sub_safe), len(all_gadgets))

    for idx, xfg in enumerate(all_gadgets):
        xfg['xfg_id'] = idx
        xfg['flip'] = False

    write_json(all_gadgets, data_path)



def vdp_gen_cdg_test(config):

    #path
    raw_data_path = os.path.join(config.data_folder, config.name, config.dataset.name,
                    'raw', 'raw.json')
    test_data_path = os.path.join(config.data_folder, config.name, config.dataset.name,
                    'raw', 'test.json')
    true_label_info_path = os.path.join(config.data_folder, config.name, config.dataset.name,
                    'raw', 'true_label_info.json')
    sensi_api_path = 'models/sysevr/resources/sensiAPI.txt'

    w2v_path = path.join(config.data_folder, config.name, config.dataset.name,
                         "w2v.model")
    vocab_path = path.join(config.data_folder, config.name,
                           config.dataset.name, "vocab.pkl") 
    train_data_out_path = path.join(config.data_folder, config.name,
                           config.dataset.name, "{}.json".format(config.dataset.name))
    true_test_out_path =  path.join(config.data_folder, config.name,
                           config.dataset.name, "true_test.json")                      
    #read
    raw_data = read_json(raw_data_path)
    test_data = read_json(test_data_path)
    true_label_info = read_json(true_label_info_path)

    #remove true label xfg from raw data
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

    #test data duplicated
    gadgets = dict()  # {md5:}
    count = 0
    dulCount = 0
    mulCount = 0
    vectorizer = GadgetVectorizer(config)
    
    for cdg in test_data:
        gadget = clean_gadget(cdg['content'], sensi_api_path)
        val = cdg['target']
        count += 1
        print("Collecting gadgets...", count, end="\r")
        tokenized_gadget, backwards_slice = GadgetVectorizer.tokenize_gadget(
            gadget)
        tokenized_gadget_md5 = getMD5(str(tokenized_gadget))
        if (tokenized_gadget_md5 not in gadgets):
            row = {"gadget": gadget, "val": val, "count": 0, "file_path": cdg['file_path'], "vul_line": cdg['vul_line']}
            gadgets[tokenized_gadget_md5] = row
        else:
            if (gadgets[tokenized_gadget_md5]["val"] != -1):
                if (gadgets[tokenized_gadget_md5]["val"] != val):
                    dulCount += 1
                    gadgets[tokenized_gadget_md5]["val"] = -1
            mulCount += 1
        gadgets[tokenized_gadget_md5]["count"] += 1
    print('\n')
    print("Find multiple...", mulCount)
    print("Find dulplicate...", dulCount)
    test_gadgets_unique = list()
    for gadget_md5 in gadgets:
        if (gadgets[gadget_md5]["val"] != -1):  # remove dulplicated
            # vectorizer.add_gadget(gadgets[gadget_md5]["gadget"])
            test_gadgets_unique.append(gadgets[gadget_md5])

    #resample test data
    gadget_vul = list()
    gadget_safe = list()
    for gadget in test_gadgets_unique:
        if gadget['val'] == 1:
            gadget_vul.append(gadget)
        else:
            gadget_safe.append(gadget)
    numpy.random.seed(7)
    if len(gadget_safe) >= len(gadget_vul) * 2:
        sub_safe = numpy.random.choice(gadget_safe, len(gadget_vul)*2, replace=False)
    else:
        sub_safe = gadget_safe
    all_test_gadgets = []
    all_test_gadgets.extend(gadget_vul)
    all_test_gadgets.extend(sub_safe)
    numpy.random.shuffle(all_test_gadgets)
    print(len(gadget_vul), len(sub_safe), len(all_test_gadgets))

    #train w2v model
    print("Training word2vec model...", end="\r")

    #### add new raw data
    xfg_idx = 0
    for xfg in new_raw_data:
        xfg['xfg_id'] = xfg_idx
        xfg['flip'] = False
        xfg_idx += 1
        vectorizer.add_gadget(xfg['gadget'])
    
    #### add test data

    for xfg in all_test_gadgets:
        xfg['xfg_id'] = xfg_idx
        xfg['flip'] = False
        xfg_idx += 1
        vectorizer.add_gadget(xfg['gadget'])

    vectorizer.train_model(w2v_path)
    vectorizer.build_vocab(vocab_path) 

    # write data
    write_json(new_raw_data, train_data_out_path)
    write_json(all_test_gadgets, true_test_out_path)
    print('end!')

def vdp_create_noise(cwe_id):

    data_path = '/home/niexu/project/python/noise_reduce/data/vuldeepecker/{}/{}.json'.format(cwe_id, cwe_id)
    out_path = '/home/niexu/project/python/noise_reduce/data/vuldeepecker/{}/noise_info.json'.format(cwe_id)
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
        numpy.random.seed(7)
        noise_xfg_ids = numpy.random.choice(xfg_ids, int(len(xfg_ids) * noise_rate), replace=False).tolist()

        
        print(len(noise_xfg_ids))
        noise_info[noise_key]['noise_xfg_ids'] = noise_xfg_ids
    write_json(noise_info, out_path)  


def vdp_preprocess(config: DictConfig, holdout_data_path):
    '''
    key function

    '''
    # holdout_data_path = path.join(
    #     config.data_folder,
    #     config.name,
    #     config.dataset.name,
    #     "all.txt",
    # )
    if (not os.path.exists(holdout_data_path)):
        print(f"there is no file named: {holdout_data_path}")
        return
    output_train_path = path.join(config.data_folder, config.name,
                                  config.dataset.name, "train.pkl")
    if (not os.path.exists(os.path.dirname(output_train_path))):
        os.makedirs(os.path.dirname(output_train_path))
    output_test_path = path.join(config.data_folder, config.name,
                                 config.dataset.name, "test.pkl")
    output_val_path = path.join(config.data_folder, config.name,
                                config.dataset.name, "val.pkl")
    # if (os.path.exists(output_train_path)):
    #     print(f"{output_train_path} exists!")

    cdg_list = read_json(holdout_data_path)
    #??????
    gadgets_unique, vectorizer = vdp_cdg_duplicate(config, cdg_list)
    
    # write_json(gadgets_unique, path.join(config.data_folder, config.name,
    #                             config.dataset.name, "unique.json"))

    X = []
    labels = []
    count = 0
    pair_id = list()
    for idx,gadget in enumerate(gadgets_unique):
        count += 1
        print("Processing gadgets...", count, end="\r")
        vector, backwards_slice = vectorizer.vectorize2(
            gadget["gadget"])  # [word len, embedding size]
        X.append((vector, backwards_slice, idx, False))
        pair_id.append(gadget['pair_id'])
        labels.append(gadget["val"])
    print('\n')
    # numpy.random.seed(52)
    # numpy.random.shuffle(vectors)
    # numpy.random.seed(52)
    # numpy.random.shuffle(labels)
    # numpy.random.seed(52)
    # numpy.random.shuffle(is_back)
    

    X = numpy.array(X)
    labels = numpy.array(labels)
    positive_idxs = numpy.where(labels == 1)[0]
    negative_idxs = numpy.where(labels == 0)[0]
    print(len(positive_idxs))
    print(len(negative_idxs))
    # undersampled_negative_idxs = numpy.random.choice(negative_idxs,
    #                                                  len(positive_idxs),
    #                                                  replace=False)
    # resampled_idxs = numpy.concatenate(
    #     [positive_idxs, undersampled_negative_idxs])
    if len(positive_idxs) > len(negative_idxs):
        positive_idxs = numpy.random.choice(positive_idxs,
                                            len(negative_idxs),
                                            replace=False)
    elif len(negative_idxs) > len(positive_idxs):
        negative_idxs = numpy.random.choice(negative_idxs,
                                            len(positive_idxs),
                                            replace=False)
    else:
        pass
    resampled_idxs = numpy.concatenate([positive_idxs, negative_idxs])

    X = X[resampled_idxs]
    labels = labels[resampled_idxs]

    X_train, X_test, Y_train, Y_test = train_test_split(
        X,
        labels,
        test_size=0.2,
        stratify=labels)
    X_test, X_val, Y_test, Y_val = train_test_split(
        X_test, Y_test, test_size=0.5, stratify=Y_test)

    train_xfg_ids = [i[2] for i in X_train]
    val_xfg_ids = [i[2] for i in X_val]
    test_xfg_ids = [i[2] for i in X_test]

    train_pair_ids = []
    val_pair_ids = []
    test_pair_ids = []
    

    
   

    noise_info = dict()
    noisy_rate_list = [0,0.05,0.06,0.07,0.08,0.09,0.1,0.2,0.3]  
    for noisy_rate in noisy_rate_list:
        noise_key = '{}_percent'.format(int(100*noisy_rate))

        noise_info[noise_key] = dict()

        noisy_pair_ids = []

        noisy_xfg_ids = numpy.random.choice(train_xfg_ids, int(noisy_rate*len(train_xfg_ids)), replace=False)


        noise_info[noise_key]['train_pair_ids'] = train_pair_ids
        noise_info[noise_key]['train_xfg_ids'] = train_xfg_ids
        noise_info[noise_key]['val_pair_ids'] = val_pair_ids
        noise_info[noise_key]['val_xfg_ids'] = val_xfg_ids
        noise_info[noise_key]['test_pair_ids'] = test_pair_ids
        noise_info[noise_key]['test_xfg_ids'] = test_xfg_ids
        noise_info[noise_key]['noisy_pair_ids'] = noisy_pair_ids
        noise_info[noise_key]['noisy_xfg_ids'] = noisy_xfg_ids.tolist()
        # print(noise_info)
        print(len(train_pair_ids))
        print(len(train_xfg_ids))
        print(len(val_pair_ids))
        print(len(val_xfg_ids))
        print(len(test_pair_ids))
        print(len(test_xfg_ids))
        print(len(noisy_pair_ids))
        print(len(noisy_xfg_ids))

    write_json(noise_info, os.path.join(config.data_folder, config.name, config.dataset.name, config.dataset.name+'_noise_info.json'))

    bpc = BufferedPathContext.create_from_lists(list(X_train), list(Y_train))
    bpc.joblib_dump(output_train_path)
    print('dump train.pkl end !')
    bpc = BufferedPathContext.create_from_lists(list(X_test), list(Y_test))
    bpc.joblib_dump(output_test_path)
    print('dump test.pkl end !')
    bpc = BufferedPathContext.create_from_lists(list(X_val), list(Y_val))
    bpc.joblib_dump(output_val_path)
    print('dump val.pkl end !')
    
    return


def vdp_preprocess_with_pair(config: DictConfig, holdout_data_path):
    '''
    key function

    '''
    # holdout_data_path = path.join(
    #     config.data_folder,
    #     config.name,
    #     config.dataset.name,
    #     "all.txt",
    # )
    
    if (not os.path.exists(holdout_data_path)):
        print(f"there is no file named: {holdout_data_path}")
        return
    output_train_path = path.join(config.data_folder, config.name,
                                  config.dataset.name, "train.pkl")
    if (not os.path.exists(os.path.dirname(output_train_path))):
        os.makedirs(os.path.dirname(output_train_path))
    output_test_path = path.join(config.data_folder, config.name,
                                 config.dataset.name, "test.pkl")

    output_val_path = path.join(config.data_folder, config.name,
                                config.dataset.name, "val.pkl")

    cdg_list = read_json(holdout_data_path)
    #??????
    gadgets_unique, vectorizer = vdp_cdg_duplicate(config, cdg_list)

    X = []
    labels = []
    count = 0
    pair_id = list()
    for idx,gadget in enumerate(gadgets_unique):
        count += 1
        print("Processing gadgets...", count, end="\r")
        vector, backwards_slice = vectorizer.vectorize2(
            gadget["gadget"])  # [word len, embedding size]
        # vectors.append(vector)
        X.append((vector, backwards_slice, idx, False))
        pair_id.append(gadget['pair_id'])
        labels.append(gadget["val"])
    # numpy.random.seed(52)
    # numpy.random.shuffle(vectors)
    # numpy.random.seed(52)
    # numpy.random.shuffle(labels)
    # numpy.random.seed(52)
  
    # return
    # vectors = numpy.array(vectors)

    X = numpy.array(X)
    labels = numpy.array(labels)
    pair_id = numpy.array(pair_id)
    positive_idxs = numpy.where(labels == 1)[0]
    negative_idxs = numpy.where(labels == 0)[0]
    # undersampled_negative_idxs = numpy.random.choice(negative_idxs,
    #                                                  len(positive_idxs),
    #                                                  replace=False)
    # resampled_idxs = numpy.concatenate(
    #     [positive_idxs, undersampled_negative_idxs])
    if len(positive_idxs) > len(negative_idxs):
        positive_idxs = numpy.random.choice(positive_idxs,
                                            len(negative_idxs),
                                            replace=False)
    elif len(negative_idxs) > len(positive_idxs):
        negative_idxs = numpy.random.choice(negative_idxs,
                                            len(positive_idxs),
                                            replace=False)
    else:
        pass
    resampled_idxs = numpy.concatenate([positive_idxs, negative_idxs])

    X = X[resampled_idxs]
    labels = labels[resampled_idxs]


    pair_id = pair_id[resampled_idxs]


    shuffle_x, shuffle_y, shuffle_pair_id = sk_shuffle(X, labels, pair_id, random_state=0)


    pair_id_set = set(shuffle_pair_id.tolist())
    pair_ids = list(pair_id_set)
    sz = len(pair_ids)

    train_pair_ids = pair_ids[slice(sz // 5, sz)]
    val_pair_ids = pair_ids[slice(0, sz//10)]
    test_pair_ids = pair_ids[slice(sz // 10, sz // 5)]

    train_xfg_ids = []
    val_xfg_ids = []
    test_xfg_ids = []

    X_train = []
    Y_train = []
    X_val = []
    Y_val = []
    X_test = []
    Y_test = []
    
   

    noise_info = dict()
    for x, y, pid in zip(shuffle_x, shuffle_y, shuffle_pair_id):
        if pid in train_pair_ids:
            X_train.append(x)
            Y_train.append(y)
            train_xfg_ids.append(x[2])
        if pid in test_pair_ids:
            X_test.append(x)
            Y_test.append(y)
            test_xfg_ids.append(x[2])
        if pid in val_pair_ids:
            X_val.append(x)
            Y_val.append(y)
            val_xfg_ids.append(x[2])
    noisy_rate_list = [0,0.05,0.06,0.07,0.08,0.09,0.1,0.2,0.3] 
    for noisy_rate in noisy_rate_list:
        noise_key = '{}_percent'.format(int(100*noisy_rate))

        noise_info[noise_key] = dict()

        noisy_xfg_ids = []

       
        noisy_pair_ids = numpy.random.choice(train_pair_ids, int(noisy_rate*len(train_pair_ids)), replace=False).tolist()
        for x, y, pid in zip(X, labels, pair_id):
            if pid in noisy_pair_ids:
                noisy_xfg_ids.append(x[2])
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

    write_json(noise_info, os.path.join(config.data_folder, config.name, config.dataset.name, config.dataset.name+'_noise_info.json'))   
    
    bpc = BufferedPathContext.create_from_lists(list(X_train), list(Y_train))
    bpc.joblib_dump(output_train_path)
    print('dump train.pkl end !')
    bpc = BufferedPathContext.create_from_lists(list(X_test), list(Y_test))
    bpc.joblib_dump(output_test_path)
    print('dump test.pkl end !')
    bpc = BufferedPathContext.create_from_lists(list(X_val), list(Y_val))
    bpc.joblib_dump(output_val_path)
    print('dump val.pkl end !')
    # load_data_from_json(config)
    return

def flip_label(noisy_xfg_ids, src_data: BufferedPathContext):
    """
    @description  : create noisy data randomly by noisy rate
    ---------
    @param  :
        noisy_rate : 0.1 , 0.3 , 0.5
        src_data: BufferedPathContext data 
    -------
    @Returns  :
    -------
    """
    
    
    re_data = dict()
   
    vectors = []
    labels = []
    is_backs = []
    words_per_label = []
    idxs = []
    flips = []
    for data in src_data:
        xfg_id = int(data[4])
        if xfg_id in noisy_xfg_ids:
            label = data[1] ^ 1
            flip = True
        else:
            label = data[1]
            flip = data[5]
        vectors.append(data[0])
        labels.append(label)
        is_backs.append(data[2])
        words_per_label.append(data[3])
        idxs.append(data[4])
        flips.append(flip)

    re_data['vectors'] = vectors
    re_data['labels'] = labels
    re_data['is_backs'] = is_backs
    re_data['words_per_label'] = words_per_label
    re_data['idxs'] = idxs
    re_data['flips'] = flips
    
    return BufferedPathContext.create_from_dict(re_data)

def vdp_create_noisy_data(config):
    """
    @description  : 
    ---------
    @param  : data_path : the path of pkl file for sysevr training
    -------
    @Returns  :
    -------
    """
    
    data_dir = os.path.join(config.data_folder, config.name, config.dataset.name)
    noisy_rates = [0,0.05,0.06,0.07,0.08,0.09,0.1,0.2,0.3] 
    noise_info = read_json(os.path.join(config.data_folder, config.name, config.dataset.name, config.dataset.name+'_noise_info.json')) 
    

    data_path = os.path.join(data_dir, 'train.pkl')
    if not os.path.exists(data_path):
        raise FileNotFoundError("pickled file not found !")
    src_data = BufferedPathContext.joblib_load(data_path)

    
    for noisy_rate in noisy_rates:
        noise_key = '{}_percent'.format(int(100*noisy_rate))
        info = noise_info[noise_key]
        noisy_xfg_ids = info['noisy_xfg_ids']
        re_data = flip_label(noisy_xfg_ids, src_data)
        out_path = os.path.join(data_dir, 
        '{}_{}_percent.pkl'.format(config.dataset.name, int(noisy_rate * 100)))
        re_data.joblib_dump(out_path)