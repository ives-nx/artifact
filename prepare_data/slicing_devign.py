from multiprocessing.connection import wait
import os
import json
import pwd
import sys
sys.path.append('../')
from utils.print_log import start_process, end_process
from tools.joern_slicer.slicing import get_data_label_devign
from tools.joern_slicer.uniqueJson import unique_xfgs, getMD5, writeBigJson_d2a
from utils.json_ops import read_json, write_json
import shutil
import subprocess

JOERN = '/home/niexu/project/python/noise_reduce/tools/joern_slicer/joern/'
CUR_DIR = os.path.abspath(os.path.dirname(__file__))
print(CUR_DIR)



def write_func_to_c(data_path:str, target_dir:str):
    with open(data_path, 'r', encoding='utf8') as f:
        data = json.load(f)
    for file_id, info in enumerate(data, start=1):
        commit_id = info['commit_id']
        func = info['function']
        target = info['target']
        file_name = '{}_{}_{}'.format(file_id, commit_id, target)
        file_dir = os.path.join(target_dir, file_name)
        file_path = os.path.join(file_dir, file_name+'.cpp')
        info['file_path'] = file_path
        os.makedirs(file_dir, exist_ok=True)
        
        with open(file_path, 'w', encoding='utf8') as f:
            f.writelines([line + '\n' for line in func])
    with open(data_path, 'w', encoding='utf8') as f:
        json.dump(data, f, indent=2)
# write_func_to_c('FFmpeg_0.json', '/home/public/rmt/niexu/datasets/devign/devign_c_files/FFmpeg')
# write_func_to_c('qemu_1.json', '/home/public/rmt/niexu/datasets/devign/devign_c_files/qemu')
def joern_parse(data_path, project_name, gen_csv:bool=False):
    """
    @description  : use joern to parse c/cpp
    ---------
    @param  : data_path: c/cpp dir
    -------
    @Returns  : 
    output: joern/output
    os.path.abspath(data_path) : data_path absolute path 
    note: output + os.path.abspath(data_path) is csv_path
    -------
    """
    
    output = f'/home/public/rmt/niexu/datasets/devign/cpg_csv/{project_name}'

    os.chdir(JOERN)
    cmd =  './joern-parse {} {}'.format(output, data_path)
    print('CMD: '+cmd)
    if gen_csv:
        start_process('joern parse generate csv')
        os.system(cmd)
        end_process('joern parse generate csv')
    os.chdir(CUR_DIR)
    return output, os.path.abspath(data_path)




# print(5, os.path.exists('/home/public/rmt/niexu/datasets/devign/cpg_csv/ffmpeg'))
# ffmpeg 1179,2673,2815,3153
##  Joern parse ??????joern ??????file??????????????????????????????????????????????????????????????????????????????

# joern_parse('/home/public/rmt/niexu/datasets/devign/devign_c_files/FFmpeg', True)


def devign_xfg_label(project_name, data_path, info_type='flaw', gen_csv:bool=False):
    """
    @description  : use joern to parse c/cpp
    ---------
    @param  : data_path: c/cpp dir
    -------
    @Returns  : xfg_list with label
    -------
    """
    
    # output_dir = CUR_DIR + '/joern/output_{}'.format('d2a')
    all_xfgs = []
    with open(data_path, 'r', encoding='utf8') as f:
        data = json.load(f)
    source_code_dir = f'/home/public/rmt/niexu/datasets/devign/devign_c_files/{project_name}'
    output_dir, abs_data_path = joern_parse(source_code_dir, project_name,  gen_csv)
    for info in data:
        flaw_info = dict()
        flaw_info['path'] = info['file_path']
        if info_type == 'flaw':
            flaw_info['line'] = info['vul_lines']
        else: flaw_info['line'] = []
        flaw_xfgs = get_data_label_devign(flaw_info, output_dir, abs_data_path, type=info_type)
        # print(flaw_xfgs)
        flaw_md5Dict = unique_xfgs(flaw_xfgs)
        flaw_xfgs = writeBigJson_d2a(flaw_md5Dict)
        if len(flaw_xfgs) == 0:
            continue
        len_to_idx = [[len(xfg['nodes-line']), idx]for idx, xfg in enumerate(flaw_xfgs)]
        len_to_idx.sort(key=lambda x:x[0], reverse=True)
        
        ## ??????????????????xfg???????????????
        print('max len idx xfg is :', len_to_idx[0][1])
        all_xfgs.append(flaw_xfgs[len_to_idx[0][1]])

    #??????
    md5Dict = unique_xfgs(all_xfgs)
    
    xfgs = writeBigJson_d2a(md5Dict)
    print('finished')
    # out_path = 'ffmpeg.json'
    # write_json(json_dict=xfgs, output=out_path)
    return xfgs

project_name = 'qemu'
data_path = f'/home/public/rmt/niexu/datasets/devign/devign_c_files/{project_name}'
joern_parse(data_path=data_path, project_name=project_name, gen_csv = True)

vul = devign_xfg_label(project_name, f'{project_name}_1.json', 'flaw')
print(len(vul))
benign = devign_xfg_label(project_name, f'{project_name}_0.json', 'benign')
print(len(benign))
vul.extend(benign)

out_path = f'{project_name}.json'
write_json(json_dict=vul, output=out_path)

# /home/public/rmt/niexu/datasets/devign/cpg_csv/FFmpeg/home/public/rmt/niexu/datasets/devign/devign_c_files/FFmpeg/4788_7104c23bd1a1dcb8a7d9e2c8838c7ce55c30a331_0/4788_7104c23bd1a1dcb8a7d9e2c8838c7ce55c30a331_0.cpp 
# /home/public/rmt/niexu/datasets/devign/cpg_csv/FFmpeg/home/public/rmt/niexu/datasets/devign/devign_c_files/qemu/5140_28143b409f698210d85165ca518235ac7e7c5ac5_0/5140_28143b409f698210d85165ca518235ac7e7c5ac5_0.cpp