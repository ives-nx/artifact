import os
from os.path import join, isdir
import csv
import networkx as nx
from typing import List, Set, Dict
import sys
sys.path.append("..")

from real_world_symbolic import clean_gadget,  tokenize_gadget_tolist
import xml.etree.ElementTree as ET
import json
import copy
import jsonlines


ROOT_DIR = os.path.abspath(os.path.dirname(__file__))

def extract_line_number(idx, nodes):
    while idx >= 0:
        c_node = nodes[idx]
        if 'location' in c_node.keys():
            location = c_node['location']
            if location.strip() != '':
                try:
                    ln = int(location.split(':')[0])
                    return ln
                except:
                    pass
        idx -= 1
    return -1


def read_csv(csv_file_path):
    data = []
    with open(csv_file_path) as fp:
        header = fp.readline()
        header = header.strip()
        h_parts = [hp.strip() for hp in header.split('\t')]
        for line in fp:
            line = line.strip()
            instance = {}
            lparts = line.split('\t')
            for i, hp in enumerate(h_parts):
                if i < len(lparts):
                    content = lparts[i].strip()
                else:
                    content = ''
                instance[hp] = content
            data.append(instance)
        return data


def extract_nodes_with_location_info(nodes):
    # Will return an array identifying the indices of those nodes in nodes array,
    # another array identifying the node_id of those nodes
    # another array indicating the line numbers
    # all 3 return arrays should have same length indicating 1-to-1 matching.
    node_indices = []
    node_ids = []
    line_numbers = []
    node_id_to_line_number = {}
    functions = set()  # function line number
    functions_name = dict()
    for node_index, node in enumerate(nodes):
        assert isinstance(node, dict)
        if 'location' in node.keys():
            location = node['location']
            if location == '':
                continue
            line_num = int(location.split(':')[0])

            if node['type'] == "Function":
                functions.add(line_num)
                functions_name[str(line_num)] = node['code']
            node_id = node['key'].strip()
            node_indices.append(node_index)
            node_ids.append(node_id)
            line_numbers.append(line_num)
            node_id_to_line_number[node_id] = line_num
    return node_indices, node_ids, line_numbers, node_id_to_line_number, functions, functions_name


class BB:
    '''
    basic block
    '''
    def __init__(self):
        self.pred: Set[BB] = set()
        self.succ: Set[BB] = set()
        self.lines: Set[str] = set()


def dfs_merge_cfg(cur_node_ln, ICFG, cur_bb, visited, bb_list):

    succ_nodes = ICFG._succ[cur_node_ln]

    for succ_node_ln in succ_nodes:
        if succ_node_ln not in visited:
            if (len(succ_nodes) > 1 or len(ICFG._pred[succ_node_ln]) > 1):
                n_bb = BB()
                bb_list.append(n_bb)
                visited[succ_node_ln] = n_bb
                n_bb.lines.add(succ_node_ln)
                cur_bb.succ.add(n_bb)
                n_bb.pred.add(cur_bb)
                dfs_merge_cfg(succ_node_ln, ICFG, n_bb, visited, bb_list)
            else:
                visited[succ_node_ln] = cur_bb

                cur_bb.lines.add(succ_node_ln)
                dfs_merge_cfg(succ_node_ln, ICFG, cur_bb, visited, bb_list)
        else:
            cur_bb.succ.add(visited[succ_node_ln])
            visited[succ_node_ln].pred.add(cur_bb)


def extract_cfgs(csv_path, src):
    r"""
    extract cfgs of the file specified by file_path

    Args:
        file_path (str): file path to be extracted

    Return:
        cfgs (List[Dict[str, List[List[int]]]])

    Examples:
        .. code-block:: python
            cfgs = extract_cfgs("test_cfg.cpp")

    Note:
        XXX
    """
   
    print(csv_path)
    nodes_path = join(csv_path, "nodes.csv")
    edges_path = join(csv_path, "edges.csv")
    nodes = read_csv(nodes_path)
    edges = read_csv(edges_path)
    node_indices, node_ids, line_numbers, node_id_to_ln, functions, functions_name = extract_nodes_with_location_info(
        nodes)
    ICFG_edges = set()
    for edge in edges:
        edge_type = edge['type'].strip()
        if True:  # edge_type in ['IS_AST_PARENT', 'FLOWS_TO']:
            start_node_id = edge['start'].strip()
            end_node_id = edge['end'].strip()
            if start_node_id not in node_id_to_ln.keys(
            ) or end_node_id not in node_id_to_ln.keys():
                continue
            start_ln = node_id_to_ln[start_node_id]
            end_ln = node_id_to_ln[end_node_id]

            if edge_type == 'FLOWS_TO':  # Control Flow edges
                ICFG_edges.add((start_ln, end_ln))

    ICFG = nx.DiGraph()
    ICFG.add_edges_from(ICFG_edges)
    cfgs = list()
    # for each cfg entry
    functions = sorted(functions)
    if len(ICFG._node.keys()) == 0:
        return cfgs
    max_ln = max(ICFG._node.keys())
    for idx, entry_ln in enumerate(functions):
        
        is_empty = False
        while entry_ln not in ICFG._node:
            if (idx + 1 < len(functions) and entry_ln >= functions[idx + 1]
                ) or entry_ln > max_ln:
                is_empty = True
                break
            entry_ln += 1

        if (is_empty):
            continue
        bb_list = list()

        entry_bb = BB()
        bb_list.append(entry_bb)
        entry_bb.lines.add(entry_ln)
        visited = dict()
        visited[entry_ln] = entry_bb
        dfs_merge_cfg(entry_ln, ICFG, entry_bb, visited, bb_list)
        bb_to_idx = dict()
        cfg = dict()
        cfg["nodes"] = list()
        cfg["edges"] = list()
        # remove empty basic block
        bb_list_cp = bb_list.copy()
        for bb in bb_list_cp:
            if len(bb.lines) == 0:
                bb_list.remove(bb)
        for pos, bb in enumerate(bb_list):
            bb_to_idx[bb] = pos
            cfg["nodes"].append(list(bb.lines))
        for pos, bb in enumerate(bb_list):
            for succ_bb in bb.succ:
                if succ_bb in bb_to_idx:
                    cfg["edges"].append([pos, bb_to_idx[succ_bb]])
        cfg['function_name'] = functions_name[str(functions[idx])]
        cfg['function_start'] = functions[idx]
        if idx+1 == len(functions):
            cfg['function_end'] = max_ln+1
        else:
            cfg['function_end'] = functions[idx+1]-1
        cfg['filePath'] = src
        cfgs.append(cfg)
    cfgs = get_code_and_sym(cfgs, src)
    return cfgs

def get_code_and_sym(cfgs, src):

    sensi_api_path = "../resources/sensiAPI.txt"    
    with open(sensi_api_path, "r", encoding="utf-8") as f:
        sensi_api_set = set([api.strip() for api in f.read().split(",")])
    
    file_path = os.path.join(ROOT_DIR, src)
    with open(file_path, 'r', encoding='utf8') as f:

        file_content = f.readlines()
    for cfg in cfgs:
        nodes = cfg['nodes']
        nodes_line = list()
        nodes_line_sym = list()
        for bb in nodes:
            bb_line = list()
            for line in bb:
                bb_line.append(file_content[line-1])
            nodes_line.append(bb_line)
            nodes_line_sym.append(tokenize_gadget_tolist(clean_gadget(bb_line, sensi_api_set)))
        cfg['nodes-line'] = nodes_line
        cfg['nodes-line-sym'] = nodes_line_sym
    return cfgs

def getFlist(file_dir):
    file_list = []
    for root, dirs, files in os.walk(file_dir):
        for file in files:
            if file.endswith('.c') or file.endswith('.cpp'):
                file_list.append(os.path.join(root, file))
                
    return file_list


def get_cfgs(data_path):
    """
    @description  : use joern to parse c/cpp
    ---------
    @param  : data_path: c/cpp dir
    -------
    @Returns  : xfg_list
    -------
    """
    
    cfg_list = []
    workspace = 'joern'
    os.chdir(workspace)
    cmd = './joern-parse output/ '+data_path
    print('CMD: '+cmd)
    os.system(cmd)
    current_path = os.path.abspath(data_path)
    print(current_path)
    c_files = getFlist(current_path)
    print(c_files)
    csv_dir = './output'
    for c_file in c_files:
        csv_path = csv_dir + c_file
        rel_path = '/'.join(c_file.split('/')[len(ROOT_DIR.split('/')):])
        print(rel_path)
        cfgs = extract_cfgs(csv_path, rel_path)
        cfg_list.extend(cfgs)
    return cfg_list






if __name__ == "__main__":
    # sys.setrecursionlimit(10000)  # ?????????????????????????????????3000
    # root = 'joern/d2a_resources'
    # for project in os.listdir(root):
    #     # if project in  ['httpd','nginx']:
    #     #     continue
    #     try:
    #         generate_cfg_d2a(project)
    #     except Exception as e:
    #         with open('generate_cfg_d2a_error.log', 'a') as f:
    #             f.write(project+'\n')
    #             f.write(str(e)+'\n')
    #             f.close()
    # merge_cfg_from_jsonl()
    src = '/home/niexu/project/python/preprocess/joern_slicer/test'
    cfgs = get_cfgs(src)
    json.dump(cfgs, open('../cfgs.json','w'),indent=2)
    