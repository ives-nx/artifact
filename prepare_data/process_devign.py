from sklearn.utils import shuffle
import torch
import pandas as pd
import numpy as np
import os
import json


def prepare_devign(project_name = 'FFmpeg'):
    devign_path = '/home/public/rmt/niexu/datasets/devign/function.json'
    pd_data = pd.read_json(devign_path)
    qemu_data = pd_data[pd_data['project'] == 'qemu']
    qemu_1 = qemu_data[qemu_data['target'] == 1]
    qemu_0 = qemu_data[qemu_data['target'] == 0]
    ffmpeg_data = pd_data[pd_data['project'] == 'FFmpeg']
    ffmpeg_1 = ffmpeg_data[ffmpeg_data['target'] == 1]
    ffmpeg_0 = ffmpeg_data[ffmpeg_data['target'] == 0]
    from pydriller import Repository
    repo = f'/home/public/rmt/niexu/datasets/devign/sourcecode/{project_name}'
    
    qemu_1_hash = qemu_1['commit_id']
    qemu_1_func = qemu_1['func']

    ffmpeg_1_hash = ffmpeg_1['commit_id']
    ffmpeg_1_func = ffmpeg_1['func']
    if project_name == 'FFmpeg':
        _hash = ffmpeg_1_hash
        _func = ffmpeg_1_func
    elif project_name == 'qemu':
        _hash = qemu_1_hash
        _func = qemu_1_func

    vul_list = []
    for commit_hash, func in zip(_hash, _func):

        ##  目标hash
        commit_hash
        ##  目标函数
        function = func.split('\n')
        ##  目标函数声明
        print(function[0])

        for commit in Repository(repo, single=commit_hash).traverse_commits():
            ##  过滤修改文件>1的
            # if len(commit.modified_files) > 1:
            #     continue
            for md_file in commit.modified_files:
                for method in md_file.methods_before:
                    ## 过滤其他函数
                    if method.name not in function[0]:
                        continue
                    source_code = md_file.source_code_before.split('\n')
                    name = method.name
                    start_line_no = method.start_line
                    end_line_no = method.end_line
                    del_lines =  [i[0] for i in md_file.diff_parsed['deleted']]
                    vul_lines = [line for line in del_lines if line > start_line_no and line < end_line_no]
                    vul_info = dict()
                    vul_info['commit_id'] = commit_hash
                    vul_info['method_name'] = name
                    vul_info['function'] = source_code[start_line_no-1: end_line_no]
                    vul_info['vul_lines'] = [line - start_line_no for line in vul_lines]
                    vul_info['start_line_no'] = start_line_no
                    vul_info['end_line_no'] = end_line_no
                    vul_info['target'] = 1
                    if len(vul_lines) > 0:
                        vul_list.append(vul_info)
                    # print(del_lines)
                    # print(method.name, method.start_line, method.end_line)
                    # print(vul_lines)
                    # print(function)
                    # print("---------")
                    # print(source_code[start_line_no-1: end_line_no])


    with open(f'{project_name}_1.json', 'w', encoding='utf8') as f:
        json.dump(vul_list, f, indent=2)
    print(len(vul_list))
# prepare_devign(project_name = 'FFmpeg')
# prepare_devign(project_name = 'qemu')
# devign_path = '/home/public/rmt/niexu/datasets/devign/function.json'
# pd_data = pd.read_json(devign_path)
# qemu_data = pd_data[pd_data['project'] == 'qemu']
# qemu_0 = qemu_data[qemu_data['target'] == 0]
# ffmpeg_data = pd_data[pd_data['project'] == 'FFmpeg']
# ffmpeg_0 = ffmpeg_data[ffmpeg_data['target'] == 0]
# qemu_0_hash = qemu_0['commit_id']
# qemu_0_func = qemu_0['func']
# qemu_safe_list = []
# for commit_hash, func in zip(qemu_0_hash, qemu_0_func):
#     vul_dict = dict()
#     ##  目标hash
#     vul_dict['commit_id'] = commit_hash
#     ##  目标函数
#     vul_dict['function'] = func.split('\n')
#     vul_dict['target'] = 0
#     qemu_safe_list.append(vul_dict)
    
# with open('qemu_0.json', 'w', encoding='utf8') as f:
#     print('qemu json write')
#     json.dump(qemu_safe_list, f, indent=2)

# ffmpeg_0_hash = ffmpeg_0['commit_id']
# ffmpeg_0_func = ffmpeg_0['func']
# ffmpeg_safe_list = []
# for commit_hash, func in zip(ffmpeg_0_hash, ffmpeg_0_func):
#     vul_dict = dict()
#     ##  目标hash
#     vul_dict['commit_id'] = commit_hash
#     ##  目标函数
#     vul_dict['function'] = func.split('\n')
#     vul_dict['target'] = 0
#     ffmpeg_safe_list.append(vul_dict)

# with open('FFmpeg_0.json', 'w', encoding='utf8') as f:
#     print('ffmpeg json write')
#     json.dump(ffmpeg_safe_list, f, indent=2)
# import json

def read_json(file_path):
    json_dict = json.load(open(file_path, 'r', encoding='utf8'))
    return json_dict

def write_json(json_dict, file_path):
    with open(file_path, 'w', encoding='utf8') as f:
        json.dump(json_dict, f, indent=2)


def sample_data():
    qemu_data = read_json('qemu.json')
    ffmpeg_data = read_json('FFmpeg.json')

    qemu_vul_xfgs = []
    qemu_safe_xfgs = []
    ffmpeg_vul_xfgs = []
    ffmpeg_safe_xfgs= []
    for info in qemu_data:
        info['project'] = 'qemu'
        if info['target'] == 1:
            qemu_vul_xfgs.append(info)
        else:
            qemu_safe_xfgs.append(info)
    for info in ffmpeg_data:
        info['project'] = 'FFmpeg'
        if info['target'] == 1:
            ffmpeg_vul_xfgs.append(info)
        else:
            ffmpeg_safe_xfgs.append(info)
    np.random.seed(7)
    qemu_ds_safe_xfgs = np.random.choice(qemu_safe_xfgs, len(qemu_vul_xfgs), replace=False)
    print('qemu', len(qemu_ds_safe_xfgs), len(qemu_vul_xfgs))
    ffmpeg_ds_safe_xfgs = np.random.choice(ffmpeg_safe_xfgs, len(ffmpeg_vul_xfgs), replace=False)
    print('ffmpeg', len(ffmpeg_ds_safe_xfgs), len(ffmpeg_vul_xfgs))
    ## ds means downsample
    devign_data_ds = []
    qemu_data_ds = []
    ffmpeg_data_ds = []
    devign_data_ds.extend(qemu_vul_xfgs)
    devign_data_ds.extend(qemu_ds_safe_xfgs)
    devign_data_ds.extend(ffmpeg_vul_xfgs)
    devign_data_ds.extend(ffmpeg_ds_safe_xfgs)
    
    np.random.shuffle(devign_data_ds)
    print(type(devign_data_ds))
    for idx, data in enumerate(devign_data_ds):
        data['xfg_id'] = idx
        data['flip'] = False
        if data['project'] == 'qemu':
            qemu_data_ds.append(data)
        else:
            ffmpeg_data_ds.append(data)
    print(len(devign_data_ds), len(qemu_data_ds), len(ffmpeg_data_ds))
    print('writing devign json')
    write_json(devign_data_ds, 'devign_data.json')
    print('writing qemu json')
    write_json(qemu_data_ds, 'qemu_data.json')
    print('writing ffmepg json')
    write_json(ffmpeg_data_ds, 'FFmpeg_data.json')

sample_data()
    

